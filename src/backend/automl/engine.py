import os
import pickle
import joblib
import asyncio
import random
from datetime import datetime, timezone
from io import BytesIO

import numpy as np
import pandas as pd  # type: ignore
import yaml
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sklearn.calibration import LabelEncoder
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.metrics import make_scorer
from pymongo.asynchronous.database import AsyncDatabase

from automl.model import Item
from automl.search.factory import SearchStrategyFactory
from automl.search.strategy.base import SearchStrategy
from automl.v2.minio import minIOStorage
from database.get_dataset import preprocess_data

np.random.seed(42)
random.seed(42)

import time
from bson import ObjectId
from uuid import uuid4


async def get_dataset_and_user_info(data_id, user_id, db: AsyncDatabase):
    """
    Helper function to retrieve dataset and user information from MongoDB.

    Args:
        data_id: The ObjectId string of the dataset
        user_id: The ObjectId string of the user

    Returns:
        tuple: (data_name, user_name)

    Raises:
        HTTPException: If dataset or user not found
    """
    data_collection = db.tbl_Data
    user_collection = db.tbl_User

    dataset = await data_collection.find_one({"_id": ObjectId(data_id)})
    if not dataset:
        raise HTTPException(status_code=404, detail="Không tìm thấy bộ dữ liệu")
    data_name = dataset.get("dataName")

    user = await user_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=400, detail="Không tìm thấy người dùng")
    user_name = user.get("username")

    return data_name, user_name



def choose_model_version(choose):
    if choose == "new model":
        list_model_search = [0, 1, 2, 3]
    else:
        # Gọi đến hàm để người ta chọn xem người ta muốn train lại cái model nào. hàm này sẽ return ra id của mô hình đó. 
        # id = ...
        # list_model_search = [id]
        list_model_search = [2]
    return list_model_search

def get_config(file):
    config = yaml.safe_load(file)
    choose = config['choose']
    list_feature = config['list_feature']
    target = config['target']
    metric_sort = config['metric_sort']
    search_algorithm = config.get('search_algorithm', 'grid_search')  # Default to 'grid_search' if not specified

    models, metric_list = get_model()
    return choose, list_feature, target, metric_list, metric_sort, models, search_algorithm


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


def get_data_config_from_json(file_content: Item):
    data = pd.DataFrame(file_content.data)
    config = file_content.config

    choose = config['choose']
    list_feature = config['list_feature']
    target = config['target']
    metric_sort = config['metric_sort']
    search_algorithm = config.get('search_algorithm', 'grid_search')  # Default to 'grid_search' if not specified

    models, metric_list = get_model()
    return data, choose, list_feature, target, metric_list, metric_sort, models, search_algorithm


def training(models, metric_list, metric_sort, X_train, y_train, search_algorithm='grid_search'):
    best_model_id = None
    best_model = None
    best_score = -1
    best_params = {}
    model_results = []

    scoring = {}
    for metric in metric_list:
        if metric == 'accuracy':
            scoring[metric] = make_scorer(accuracy_score)
        elif metric == 'precision':
            scoring[metric] = make_scorer(precision_score, average='macro')
        elif metric == 'recall':
            scoring[metric] = make_scorer(recall_score, average='macro')
        elif metric == 'f1':
            scoring[metric] = make_scorer(f1_score, average='macro')
        else:
            # Try to get the score function dynamically if it's not one of the common ones
            score_func = globals().get(f'{metric}_score')
            if score_func:
                scoring[metric] = make_scorer(score_func, average='macro')
            else:
                raise ValueError(f"Unknown metric: {metric}")

    # Use the factory to create the search strategy with configuration
    strategy_config = {
        'cv': 5,
        'scoring': scoring,
        'metric_sort': metric_sort,
        'error_score': "raise",
        'return_train_score': True
    }
    
    try:
        search_strategy = SearchStrategyFactory.create_strategy(search_algorithm, strategy_config)
    except ValueError as e:
        print(f"Warning: {e}. Using default 'grid' search.")
        search_strategy = SearchStrategyFactory.create_strategy('grid', strategy_config)

    for model_id in range(len(models)):
        model_info = models[model_id]
        model = model_info['model']
        param_grid = model_info['params']

        best_params_model, best_score_model, best_all_scores_model, cv_results = search_strategy.search(
            model=model,
            param_grid=param_grid,
            X=X_train,
            y=y_train
        )
        
        # Convert all numpy types to native Python types to avoid serialization issues
        best_params_model = SearchStrategy.convert_numpy_types(best_params_model)
        best_score_model = SearchStrategy.convert_numpy_types(best_score_model)
        cv_results = SearchStrategy.convert_numpy_types(cv_results)

        # Get the best estimator with the best parameters
        best_estimator = model.set_params(**best_params_model)
        best_estimator.fit(X_train, y_train)

        # Extract scores from cv_results
        # Convert rank list to numpy array for argmin operation
        rank_key = f'rank_test_{metric_sort}'
        if rank_key in cv_results:
            rank_array = np.array(cv_results[rank_key])
        else:
            # Fallback to 'rank_test_score' if specific metric rank not found
            rank_array = np.array(cv_results.get('rank_test_score', []))
        
        best_idx = rank_array.argmin() if len(rank_array) > 0 else 0
        
        # Ensure scores are also converted to native types
        scores_dict = {}
        for metric in metric_list:
            if f"mean_test_{metric}" in cv_results:
                score_value = cv_results[f"mean_test_{metric}"][best_idx]
                # Convert to native Python float if it's a numpy type
                scores_dict[metric] = float(score_value) if hasattr(score_value, 'item') else score_value
        
        results = {
            "model_id": model_id,
            "model_name": model.__class__.__name__,
            "best_params": best_params_model,
            "scores": scores_dict
        }

        model_results.append(results)

        if best_score_model > best_score:
            best_model_id = model_id
            best_model = best_estimator
            best_score = best_score_model
            best_params = best_params_model
    
    # Final conversion to ensure all return values are native Python types
    best_params = SearchStrategy.convert_numpy_types(best_params)
    best_score = SearchStrategy.convert_numpy_types(best_score)
    model_results = SearchStrategy.convert_numpy_types(model_results)

    return best_model_id, best_model, best_score, best_params, model_results



def train_process(X_train, y_train, metric_list, metric_sort, models, search_algorithm='grid_search'):
    best_model_id, best_model, best_score, best_params, model_scores = training(models, metric_list, metric_sort,
                                                                                X_train, y_train, search_algorithm)
    return best_model_id, best_model, best_score, best_params, model_scores


def app_train_local(file_data, file_config):
    contents = file_data.file.read()
    data_file = BytesIO(contents)
    data = pd.read_csv(data_file)

    contents = file_config.file.read()
    data_file_config = BytesIO(contents)
    choose, list_feature, target, metric_list, metric_sort, models, search_algorithm = get_config(data_file_config)

    X_processed, y_processed, preprocessor, le_target = preprocess_data(list_feature, target, data)

    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        X_processed, y_processed, metric_list, metric_sort, models, search_algorithm
    )

    return best_model_id, best_model, best_score, best_params, model_scores


# chuyển đổi ObjectId sang string để trả về cho client
def serialize_mongo_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc


# Không dùng kafka
async def train_json(item: Item, userId, id_data, db: AsyncDatabase):
    job_collection = db.tbl_Job

    data, choose, list_feature, target, metric_list, metric_sort, models, search_algorithm = (
        get_data_config_from_json(item)
    )

    X_processed, y_processed, preprocessor, le_target = preprocess_data(list_feature, target, data)

    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        X_processed, y_processed, metric_list, metric_sort, models, search_algorithm
    )

    data_name, user_name = await get_dataset_and_user_info(id_data, userId, db)
    model_data = pickle.dumps(best_model)
    job_id = str(uuid4())

    # Ensure all values are properly converted to native Python types before storing
    
    job = {
        "job_id": job_id,
        "best_model_id": SearchStrategy.convert_numpy_types(best_model_id),
        "best_model": str(best_model),
        "model": model_data, # Đang lưu trực tiếp vào mongodb
        "best_params": SearchStrategy.convert_numpy_types(best_params),
        "best_score": SearchStrategy.convert_numpy_types(best_score),
        "orther_model_scores": SearchStrategy.convert_numpy_types(model_scores),
        "config": item.config,
        "data": {
            "id": id_data,
            "name": data_name
        },
        "user": {
            "id": userId,
            "name": user_name
        },
        "create_at": datetime.now(timezone.utc).timestamp(),
        "status": 1
    }

    job_result = await job_collection.insert_one(job)
    if job_result.inserted_id:
        job.pop("model")
        return JSONResponse(content=serialize_mongo_doc(job))
    else:
        raise HTTPException(status_code=500, detail="Đã xảy ra lỗi train")


async def inference_model(job_id: str, user_id: str, file_data, db: AsyncDatabase):
    """
    Chạy dự đoán trên dữ liệu mới bằng model và preprocessor đã lưu
    """
    job_collection = db.tbl_Job

    try:
        stored_model_data = await job_collection.find_one({"job_id": job_id, "status": 1})
        if not stored_model_data:
            raise ValueError("Job not found or not completed")
        if stored_model_data.get('activate') == 0:
            return {
                "job_id": job_id,
                "message": "model is deactivate"
            }
    except Exception as e:
        return {"error": f"Failed to retrieve model: {str(e)}"}
    
    list_feature = stored_model_data.get("config", {}).get("list_feature", [])

    # Lấy config để tái tạo đường dẫn
    try:
        model_url = stored_model_data.get("model")
        model_path = f"{model_url.get('object_name')}"
        preprocessor_path = f"{user_id}/{job_id}/preprocessor.joblib"
        target_path = f"{user_id}/{job_id}/target.joblib"
    except Exception as e:
        return {"error": f"Failed to construct model paths: {str(e)}"}
    
    async def load_artifact(bucket, path, type):
        """Hàm helper để tải và load file"""
        try:
            buffer = await asyncio.to_thread(minIOStorage.get_object, bucket, path)
            return await asyncio.to_thread(type.load, buffer)
        except Exception as e:
            raise ValueError(f"Failed to load artifact from {path}: {str(e)}")
        
    try:
        # Tải cả 3 file song song
        model, preprocessor, le_target = await asyncio.gather(
            load_artifact(model_url.get('bucket_name'), model_path, pickle),
            load_artifact(model_url.get('bucket_name'), preprocessor_path, joblib),
            load_artifact(model_url.get('bucket_name'), target_path, joblib)
        )
    except Exception as e:
        return {"error": f"Failed to load required model artifacts: {str(e)}"}

    try:
        contents = await file_data.read()
        data_file = BytesIO(contents)
        data = await asyncio.to_thread(pd.read_csv, data_file)

        missing_cols = set(list_feature) - set(data.columns)
        if missing_cols:
            raise ValueError(f"Uploaded file is missing required columns: {missing_cols}")

        data_to_predict = data[list_feature]
    except (ValueError, KeyError) as e:
        return {"error": f"CSV file processing error: {str(e)}"}
    except Exception as e:
        return {"error": f"Cannot read file: {str(e)}"}
    
    try:
        # Dùng preprocessor đã lưu
        X_new_transformed = await asyncio.to_thread(preprocessor.transform, data_to_predict)
        
        # Dùng model đã lưu
        y_pred_encoded = await asyncio.to_thread(model.predict, X_new_transformed)

        # Dùng le_target đã lưu
        y_pred_human = await asyncio.to_thread(le_target.inverse_transform, y_pred_encoded)
    except Exception as e:
        return {"error": f"Failed during prediction process: {str(e)}"}
    
    data['predict'] = y_pred_human
    data_json = await asyncio.to_thread(data.to_dict, orient="records")
    return data_json



# Lấy danh sách job
async def get_jobs(user_id, db: AsyncDatabase):
    job_collection = db.tbl_Job

    try:
        query = {}
        if user_id:
            query["user.id"] = user_id

        jobs = await job_collection.find(query, {"model": 0, "item": 0}).to_list(length=None)
        for job in jobs:
            if "_id" in job:
                job["_id"] = str(job["_id"])
            for key, value in job.items():
                if isinstance(value, datetime):
                    job[key] = value.timestamp()

        return JSONResponse(content=jobs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# Lấy job theo job_id
async def get_one_job(id_job: str, db: AsyncDatabase):
    job_collection = db.tbl_Job
    try:
        job = await job_collection.find_one({"job_id": id_job}, {"model": 0, "item": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Không tìm thấy job với ID đã cho.")
        for key, value in job.items():
            if isinstance(value, datetime):
                job[key] = value.timestamp()
        return JSONResponse(content=serialize_mongo_doc(job))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi truy vấn job: {str(e)}")



async def update_activate_model(job_id, db: AsyncDatabase, activate=0):
    job_collection = db.tbl_Job

    result = await job_collection.update_one(
        {"job_id": job_id},
        {"$set": {"activate": int(activate)}}
    )
    return JSONResponse(
        content={
            "job_id": job_id,
            "message": "cập nhập trạng thái mô hình thành công",
            "activate": int(activate)
        },
        status_code=200
    )
