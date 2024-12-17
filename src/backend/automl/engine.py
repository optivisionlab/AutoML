from io import BytesIO
import pandas as pd # type: ignore
from sklearn.calibration import LabelEncoder
from sklearn.discriminant_analysis import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.model_selection import GridSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
import yaml
import json
import pymongo
import numpy as np
import random
from database.database import get_database
from .model import Item

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
    matrix = config['matrix']
    
    #Lấy ra danh sách id của model từ MôngDB
    client = get_database()
    db = client["AutoML"]
    model_collection = db["Classification_models"]
    document = model_collection.find_one(sort=[('_id', -1)])
    list_model_search = document['model_keys']


    models = get_model(list_model_search)
    return choose, list_model_search, list_feature, target,matrix,models

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
    list_model_search = config['list_model_search']
    target = config['target']
    matrix = config['matrix']
    models = {}
    for key, model_info in config['models'].items():
        model_class = eval(model_info['model'])
        params = model_info['params']
        for param_key, param_value in params.items():
            params[param_key] = [None if v is None else v for v in param_value]
        models[key] = {
            "model": model_class(),
            "params": params 
        }
    return data, choose, list_model_search, list_feature, target,matrix,models



def get_data_config_from_json(file_content: Item):
    data = pd.DataFrame(file_content.data)
    config = file_content.config
    
    choose = config['choose']
    list_model_search = config['list_model_search']
    list_feature = config['list_feature']
    target = config['target']
    matrix = config['matrix']

    models = {}
    for key, model_info in config['models'].items():
        model_class = eval(model_info['model'])
        params = model_info['params']
        models[key] = {
            "model": model_class(),
            "params": params
        }
    return data, choose, list_model_search, list_feature, target,matrix,models



Classification_models = {
    "0": {
        "model": DecisionTreeClassifier(),
        "params": {
            "max_depth": [5, 10, 15],
            "min_samples_split": [2, 5, 10]
        }
    },
    "1": {
        "model": RandomForestClassifier(),
        "params": {
            "n_estimators": [50, 100, 200],
            "max_features": ["sqrt", "log2", 0.5, 1]
        }
    },
    "2": {
        "model": KNeighborsClassifier(),
        "params": {
            "n_neighbors": [3, 5, 7, 9],
            "weights": ["uniform", "distance"]
        }
    },
    "3": {
        "model": SVC(),
        "params": {
            "C": [0.1, 1, 10],
            "kernel": ["linear", "rbf"]
        }
    },
    "4": {
        "model": LogisticRegression(),
        "params": {
            "C": [0.001, 0.01, 0.1, 1],
            "penalty": ["l1", "l2"],
            "solver": ["saga"],
            "max_iter": [500, 1000]
        }
    },
    "5": {
        "model": GaussianNB(),
        "params": {
            "var_smoothing": [1e-9, 1e-8, 1e-7, 1e-6]
        }
    }
}
Clustering_models = {
    "0": {
        "model": DecisionTreeClassifier(),
        "params": {
            "max_depth": [5, 10, 15],
            "min_samples_split": [2, 5, 10]
        }
    },
    "1": {
        "model": RandomForestClassifier(),
        "params": {
            "n_estimators": [50, 100, 200],
            "max_features": ["sqrt", "log2", 0.5, 1]
        }
    },
    "2": {
        "model": KNeighborsClassifier(),
        "params": {
            "n_neighbors": [3, 5, 7, 9],
            "weights": ["uniform", "distance"]
        }
    },
    "3": {
        "model": SVC(),
        "params": {
            "C": [0.1, 1, 10],
            "kernel": ["linear", "rbf"]
        }
    },
    "4": {
        "model": LogisticRegression(),
        "params": {
            "C": [0.001, 0.01, 0.1, 1],
            "penalty": ["l1", "l2"],
            "solver": ["saga"],
            "max_iter": [500, 1000]
        }
    },
    "5": {
        "model": GaussianNB(),
        "params": {
            "var_smoothing": [1e-9, 1e-8, 1e-7, 1e-6]
        }
    }
}


def get_model(list_model_search):
    Models = {}
    for key in list_model_search:
        if key in Classification_models:
            Models[key] = Classification_models[key]
    return Models
def training(models, list_model_search, matrix, X_train, y_train):
    best_model_id = None
    best_model = None
    best_score = -1
    best_params = {}
    model_scores = {}
    
    for model_id in list_model_search:
        model_info = models[model_id]
        model = model_info['model']
        param_grid = model_info['params']
        grid_search = GridSearchCV(model, param_grid, cv=5, scoring=matrix, error_score="raise")
        grid_search.fit(X_train, y_train)
        
        model_name = model.__class__.__name__
        model_scores[model_name] = grid_search.best_score_

        if grid_search.best_score_ > best_score:
            best_model_id = model_id
            best_model = grid_search.best_estimator_
            best_score = grid_search.best_score_
            best_params = grid_search.best_params_

    return best_model_id, best_model ,best_score, best_params, model_scores



def train_process(data, choose, list_model_search, list_feature, target,matrix,models):
    X_train,y_train = preprocess_data(list_feature, target, data)
    best_model_id, best_model ,best_score, best_params,model_scores = training(models,list_model_search, matrix,X_train,y_train)
    return best_model_id, best_model ,best_score, best_params, model_scores


def app_train_local(file_data, file_config):
    contents = file_data.file.read()
    data_file = BytesIO(contents)
    data = pd.read_csv(data_file)

    contents = file_config.file.read()
    data_file_config = BytesIO(contents)
    choose, list_model_search, list_feature, target, matrix,models = get_config(data_file_config)
    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        data, choose, list_model_search, list_feature, target, matrix, models
    )
    return best_model_id, best_model, best_score, best_params, model_scores
