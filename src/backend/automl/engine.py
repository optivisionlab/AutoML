from io import BytesIO
import pandas as pd # type: ignore
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.calibration import LabelEncoder
from sklearn.discriminant_analysis import StandardScaler
from sklearn.metrics import make_scorer
from sklearn.model_selection import train_test_split
from sklearn.model_selection import GridSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering, MeanShift, SpectralClustering

import yaml
import os
import pymongo
import numpy as np
import random
from database.database import get_database
from .model import Item
from pathlib import Path

np.random.seed(42)
random.seed(42)

# Hàm chuẩn bị dữ liệu từ các thuộc tính mà người ta chọn. 
def preprocess_data(list_feature, target, data):
    for column in data.columns:
        if data[column].dtype == 'object':
            le = LabelEncoder()
            data[column] = le.fit_transform(data[column])
    
    X = data[list_feature]
    y = data[target]
    
    scaler = StandardScaler() 
    X_scaled = scaler.fit_transform(X)
    
    X, y = X_scaled, y
    
    return X, y

def choose_model_version(choose):
    if(choose == "new model") : 
        list_model_search = [0,1,2,3]
    else:
        # Gọi đến hàm để người ta chọn xem người ta muốn train lại cái model nào. hàm này sẽ return ra id của mô hình đó. 
        # id = ...
        # list_model_search = [id]
        list_model_search = [2]
    return list_model_search

def get_config(file):
    
    config = yaml.safe_load(file)

    # Trích xuất các thông tin cần thiết từ file config
    choose = config['choose']
    list_feature = config['list_feature']
    target = config['target']
    metric_sort = config['metric_sort']

    models,metric_list  = get_model()
    return choose, list_feature, target, metric_list, metric_sort, models


def get_model():
    base_dir = "assets/system_models"
    file_path = os.path.join(base_dir, "model.yml")
    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    
    models = {}
    for key, model_info in data['Classification_models'].items():
        model_class = eval(model_info['model'])
        params = model_info['params']
        models[key] = {
            "model": model_class(),
            "params": params
        }
    metric_list = data['metric_list']
    return models, metric_list


def get_data_and_config_from_MongoDB():
    client = get_database()
    db = client["AutoML"]
    csv_collection = db["file_csv"]
    yml_collection = db["file_yaml"]

    csv_data = list(csv_collection.find())
    data = pd.DataFrame(csv_data)

    if '_id' in data.columns:
        data.drop(columns=['_id'], inplace=True)

    config = yml_collection.find_one()

    if '_id' in config:
        del config['_id']
    
    choose = config['choose']
    list_feature = config['list_feature']
    target = config['target']
    metric_sort = config['metric_sort']

    models,metric_list  = get_model()
    return data, choose, list_feature, target, metric_list, metric_sort, models



def get_data_config_from_json(file_content: Item):
    data = pd.DataFrame(file_content.data)
    config = file_content.config
    
    choose = config['choose']
    list_feature = config['list_feature']
    target = config['target']
    metric_sort = config['metric_sort']

    models,metric_list  = get_model()
    return data, choose, list_feature, target, metric_list, metric_sort, models


def training(models, metric_list, metric_sort, X_train, y_train):
    best_model_id = None
    best_model = None
    best_score = -1
    best_params = {}
    model_results = []

    scoring = {}
    for metric in metric_list:
        if metric == 'accuracy':
            scoring[metric] = make_scorer(accuracy_score)
        else:
            scoring[metric] = make_scorer(globals()[f'{metric}_score'], average='macro')

    for model_id in range(len(models)):
        model_info = models[model_id]
        model = model_info['model']
        param_grid = model_info['params']
        
        
        grid_search = GridSearchCV(
            model,
            param_grid,
            cv=5,
            scoring = scoring,
            refit=metric_sort,
            error_score="raise"
        )
        grid_search.fit(X_train, y_train)

        results = {
            "model_id": model_id,
            "model_name": model.__class__.__name__,
            "best_params": grid_search.best_params_,
            "scores": {metric: grid_search.cv_results_[f"mean_test_{metric}"][grid_search.best_index_] for metric in metric_list}
        }
        model_results.append(results)
        
        if grid_search.best_score_ > best_score:
            best_model_id = model_id
            best_model = grid_search.best_estimator_
            best_score = grid_search.best_score_
            best_params = grid_search.best_params_

    return best_model_id, best_model ,best_score, best_params, model_results



def train_process(data, choose, list_feature, target, metric_list, metric_sort, models):
    X_train, y_train = preprocess_data(list_feature, target, data)
    best_model_id, best_model ,best_score, best_params, model_scores = training(models, metric_list, metric_sort, X_train, y_train)
    return best_model_id, best_model ,best_score, best_params, model_scores

def app_train_local(file_data, file_config):
    contents = file_data.file.read()
    data_file = BytesIO(contents)
    data = pd.read_csv(data_file)

    contents = file_config.file.read()
    data_file_config = BytesIO(contents)
    choose,  list_feature, target, metric_list, metric_sort , models = get_config(data_file_config)
    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        data, choose, list_feature, target, metric_list, metric_sort, models
    )
    return best_model_id, best_model, best_score, best_params, model_scores

from database.database import get_database
from fastapi.responses import JSONResponse
from fastapi import HTTPException
import time
from bson import ObjectId
# MongoDB setup
db = get_database()
job_collection = db["tbl_Job"]
data_collection = db["tbl_Data"]
user_collection = db["tbl_User"]

def serialize_mongo_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc

# Không dùng kafka
def train_json(item: Item, userId, id_data):
    data, choose, list_feature, target, metric_list, metric_sort, models = (
        get_data_config_from_json(item)
    )

    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        data, choose, list_feature, target, metric_list, metric_sort, models
    )
    
    dataset = data_collection.find_one({"_id":ObjectId(id_data)})
    if not dataset:
        raise HTTPException(status_code=404, detail="Không tìm thấy bộ dữ liệu")
    data_name = dataset.get("dataName")
    
    user = user_collection.find_one({"_id":ObjectId(userId)})
    if not user:
        raise HTTPException(status_code=400, detail="Không tìm thấy người dùng")
    user_name = user.get("username")
    job = {
        "job_id" : str(uuid4()),
        "best_model_id": best_model_id,
        "best_model": str(best_model),
        "best_params": best_params,
        "best_score": best_score,
        "orther_model_scores": model_scores,
        "config": item.config,
        "data": {
            "id": id_data,
            "name": data_name
        },
        "user": {
            "id": userId,
            "name": user_name
        },
        "create_at": time.time(),
        "status": 1
    }

    result = job_collection.insert_one(job)
    if result.inserted_id:
        serialize_mongo_doc(job)
        return JSONResponse(content=job)
    else:
        raise HTTPException(status_code=500, detail="Đã xảy ra lỗi train")
    
# Dùng với kafka
def train_json_from_job(job):
    item = job["item"]
    user_id = job["user_id"]
    data_id = job["data_id"]

    data, choose, list_feature, target, metric_list, metric_sort, models = (
        get_data_config_from_json(Item(**item))
    )

    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        data, choose, list_feature, target, metric_list, metric_sort, models
    )
    
    dataset = data_collection.find_one({"_id": ObjectId(data_id)})
    if not dataset:
        raise HTTPException(status_code=404, detail="Không tìm thấy bộ dữ liệu")
    data_name = dataset.get("dataName")

    user = user_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=400, detail="Không tìm thấy người dùng")
    user_name = user.get("username")

    job_doc = {
        "job_id": job["job_id"],
        "best_model_id": best_model_id,
        "best_model": str(best_model),
        "best_params": best_params,
        "best_score": best_score,
        "orther_model_scores": model_scores,
        "config": item["config"],
        "data": {
            "id": data_id,
            "name": data_name
        },
        "user": {
            "id": user_id,
            "name": user_name
        },
        "create_at": time.time(),
        "status": 1
    }

    result = job_collection.insert_one(job_doc)
    if result.inserted_id:
        return JSONResponse(content=serialize_mongo_doc(job_doc))
    else:
        raise HTTPException(status_code=500, detail="Đã xảy ra lỗi train")

def get_jobs(user_id):
    try:
        query = {}
        if user_id:
            query["user_id"] = user_id
        
        jobs = list(job_collection.find(query))
        for job in jobs:
            job["_id"] = str(job["_id"])  # Chuyển ObjectId thành string
        return JSONResponse(content=jobs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
def get_one_job(id_job: str):
    try:
        job = job_collection.find_one({"_id": ObjectId(id_job)})
        if not job:
            raise HTTPException(status_code=404, detail="Không tìm thấy job với ID đã cho.")
        return JSONResponse(content=serialize_mongo_doc(job))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi truy vấn job: {str(e)}")

# Push and get Kafka
from kafka import KafkaProducer
from kafka import KafkaConsumer
from uuid import uuid4
import json


producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def push_train_job(item: Item, user_id, data_id):
    job_id = str(uuid4())
    payload = {
        "job_id": job_id,
        "item": item.dict(),
        "user_id": user_id,
        "data_id": data_id,
        "status": 0
    }
    producer.send("train-job-topic", value=payload)
    producer.flush()
    return {"message": "Pushed job to Kafka", "job_id": job_id, "status": 0}

# Kafka consumer setup
consumer = KafkaConsumer(
    "train-job-topic",
    bootstrap_servers="localhost:9092",
    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    group_id="train-consumer-group",
    auto_offset_reset="earliest",
    enable_auto_commit=True
)

def run_train_consumer():
    print("Kafka consumer is running...")

    for msg in consumer:
        try:
            job = msg.value
            print(f"[Kafka] Received job: {job['job_id']}")

            train_json_from_job(job)

            print(f"[Kafka] Completed and saved job {job['job_id']} to MongoDB")

        except Exception as e:
            print(f"[Kafka] Error processing job: {e}")
