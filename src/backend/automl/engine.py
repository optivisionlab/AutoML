import pandas as pd # type: ignore
from sklearn.model_selection import train_test_split
from sklearn.model_selection import GridSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
import yaml
import json
import pymongo
import numpy as np
import random
from database.database import get_database
from .model import Item

np.random.seed(42)
random.seed(42)

# Hàm load data
def load_data(file_path):
        data = pd.read_csv(file_path)
        return data
# Hàm chuẩn bị dữ liệu từ các thuộc tính mà người ta chọn. 
def preprocess_data(list_feature, target, data):
    X= data[list_feature]
    y=data[target]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    return X_train,y_train,X_test,y_test

def choose_model_version(choose):
    if(choose == "new model") : 
        list_model_search = [0,1,2,3]
    else:
        # Gọi đến hàm để người ta chọn xem người ta muốn train lại cái model nào. hàm này sẽ return ra id của mô hình đó. 
        # id = ...
        # list_model_search = [id]
        list_model_search = [2]
    return list_model_search

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
        grid_search = GridSearchCV(model, param_grid, cv=5, scoring=matrix)
        grid_search.fit(X_train, y_train)
        
        model_name = model.__class__.__name__
        model_scores[model_name] = grid_search.best_score_

        if grid_search.best_score_ > best_score:
            best_model_id = model_id
            best_model = grid_search.best_estimator_
            best_score = grid_search.best_score_
            best_params = grid_search.best_params_

    return best_model_id, best_model ,best_score, best_params, model_scores

def get_config(file):
    
    config = yaml.safe_load(file)

    # Trích xuất các thông tin cần thiết
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

def train_process(data, choose, list_model_search, list_feature, target,matrix,models):
    X_train,y_train,X_test,y_test = preprocess_data(list_feature, target, data)
    best_model_id, best_model ,best_score, best_params,model_scores = training(models,list_model_search, matrix,X_train,y_train)
    return best_model_id, best_model ,best_score, best_params, model_scores



#đây là mấy cái hàm em test lại mà không cần chạy api thôi, k có gì đâu ạ.


def api_train_local(file_data_path: str, file_config_path: str):
    try:
        # Đọc dữ liệu từ file CSV
        data = pd.read_csv(file_data_path)

        # Đọc cấu hình từ file YAML
        with open(file_config_path, 'r') as config_file:
            config = yaml.safe_load(config_file)
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

        best_model_id, best_model, best_score, best_params, model_scores = train_process(data, choose, list_model_search, list_feature, target, matrix, models)
        
        return {
            "List other model's score": model_scores
        }

    except Exception as e:
        print(f"Lỗi_Local: {e}")
        return None


def api_train_mongo():
    try:
        data, choose, list_model_search, list_feature, target,matrix,models = get_data_and_config_from_MongoDB()
        best_model_name, best_model ,best_score, best_params, model_scores = train_process(data, choose, list_model_search, list_feature, target,matrix,models)
        
        return {
            "List other model's score:  ": model_scores
        } 
    except Exception as e:
        print(f"Lỗi: {e}")
        return None

def api_train_json(file_path: str):
    try:
        with open(file_path, 'r') as file:
            file_content = file.read()
        data, choose, list_model_search, list_feature, target, matrix, models = get_data_config_from_json(file_content)

        best_model_name, best_model, best_score, best_params, model_scores = train_process(data, choose, list_model_search, list_feature, target, matrix, models)
        
        return {
            "List other model's score": model_scores
        }

    except Exception as e:
        print(f"Lỗi: {e}")
        return None
    
def main():
    file_data_path = "D:\Hoc\LAB\Auto ML\AutoML\docs\data\glass.csv" 
    file_config_path = "D:\Hoc\LAB\Auto ML\AutoML\docs\data\config.yml" 
    json_file_path = "D:\Hoc\LAB\Auto ML\AutoML\docs\data\output.json"
    
    try:
        local_result = api_train_local(file_data_path, file_config_path)
        print("Local Training Result:")
        print(local_result)
        print("========================================================================\n")
    except Exception as e:
        print(f"Lỗi của hàm api_train_local: {str(e)}")
        print("========================================================================\n")



    try:
        mongo_result = api_train_mongo()
        print("MongoDB Training Result:")
        print(mongo_result)
        print("========================================================================\n")

    except Exception as e:
        print(f"Lỗi của hàm api_train_mongo: {str(e)}")
        print("========================================================================\n")


    try:
        json_result = api_train_json(json_file_path)
        print("JSON Training Result:")
        print(json_result)
        print("========================================================================\n")

    except Exception as e:
        print(f"Lỗi của hàm api_train_json: {str(e)}")
        print("========================================================================\n")

# if __name__ == "__main__":
#     main()



