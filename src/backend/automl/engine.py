import pandas as pd # type: ignore
from sklearn.model_selection import train_test_split
from sklearn.model_selection import GridSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
import yaml


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
    
    for model_id in list_model_search:
        model, param_grid = models[model_id]
        grid_search = GridSearchCV(model, param_grid, cv=5, scoring=matrix)
        grid_search.fit(X_train, y_train)
        
        if grid_search.best_score_ > best_score:
            best_model_id = model_id
            best_model = grid_search.best_estimator_
            best_score = grid_search.best_score_
            best_params = grid_search.best_params_

    return best_model_id, best_model ,best_score, best_params


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
        models[int(key)] = (model_class(), params)
    return choose, list_model_search, list_feature, target,matrix,models

def train_process(data, choose, list_model_search, list_feature, target,matrix,models):
    X_train,y_train,X_test,y_test = preprocess_data(list_feature, target, data)
    best_model_name, best_model ,best_score, best_params = training(models,list_model_search, matrix,X_train,y_train)
    return best_model_name, best_model ,best_score, best_params

