import logging
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
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, balanced_accuracy_score
from sklearn.metrics import make_scorer
from sklearn.model_selection import KFold
from sklearn.metrics import (mean_squared_error, mean_absolute_error, r2_score)
from sklearn.base import clone
from pymongo.asynchronous.database import AsyncDatabase

from automl.model import Item
from automl.search.factory import SearchStrategyFactory
from automl.search.strategy.base import SearchStrategy
from automl.v2.minio import minIOStorage
from automl.process_classification import preprocess_data

np.random.seed(42)
random.seed(42)

# Cấu hình logger cho module này
logger = logging.getLogger(__name__)

import time
from bson import ObjectId
from uuid import uuid4


async def get_dataset_and_user_info(data_id, user_id, db: AsyncDatabase):
    """
    Hàm helper để lấy thông tin dataset và user từ MongoDB.

    Args:
        data_id: Chuỗi ObjectId của dataset
        user_id: Chuỗi ObjectId của user

    Returns:
        tuple: (data_name, user_name)

    Raises:
        HTTPException: Nếu không tìm thấy dataset hoặc user
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
    """
    Xác định danh sách ID các mô hình cần huấn luyện dựa trên lựa chọn của người dùng.

    Args:
        choose: Lựa chọn của người dùng ('new model' hoặc tên model cụ thể)

    Returns:
        list: Danh sách ID các mô hình cần tìm kiếm siêu tham số
    """
    if choose == "new model":
        list_model_search = [0, 1, 2, 3]
    else:
        # Gọi đến hàm để người ta chọn xem người ta muốn train lại cái model nào. hàm này sẽ return ra id của mô hình đó. 
        # id = ...
        # list_model_search = [id]
        list_model_search = [2]
    return list_model_search

def get_config(file):
    """
    Đọc cấu hình huấn luyện từ file YAML.

    Trích xuất các thông tin: lựa chọn model, danh sách đặc trưng, biến mục tiêu,
    độ đo sắp xếp, thuật toán tìm kiếm và giới hạn thời gian.

    Args:
        file: File object hoặc stream chứa nội dung YAML

    Returns:
        tuple: (choose, list_feature, target, metric_list, metric_sort,
                models, search_algorithm, max_time)
    """
    config = yaml.safe_load(file)
    choose = config['choose']
    list_feature = config['list_feature']
    target = config['target']
    metric_sort = config['metric_sort']
    # Chuẩn hóa đầu vào
    metric_sort = metric_sort.strip().lower().replace(' ', '_')

    search_algorithm = config.get('search_algorithm', 'grid_search')  # Default to 'grid_search' if not specified
    max_time = config.get('max_time', None)  # Thời gian tối đa (giây), None = dùng default từ YAML

    models, metric_list = get_model()
    return choose, list_feature, target, metric_list, metric_sort, models, search_algorithm, max_time


def get_model():
    """
    Tải danh sách các mô hình classification và metric từ file YAML hệ thống.

    Đọc file `assets/system_models/classification.yml`, khởi tạo từng model
    cùng với param grid tương ứng.

    Returns:
        tuple: (models, metric_list)
            - models: Dict {id: {'model': estimator, 'params': list[dict]}}
            - metric_list: Danh sách các metric đánh giá
    """
    base_dir = "assets/system_models"
    file_path = os.path.join(base_dir, "classification.yml")
    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    models = {}
    for key, model_info in data['Classification_models'].items():
        model_class = eval(model_info['model'])
        params = model_info.get('params')
        # Xử lý None/empty params - trả về list rỗng hoặc list với dict rỗng
        if params is None or params == []:
            params = [{}]
        models[key] = {
            "model": model_class(),
            "params": params
        }
    metric_list = data['metric_list']
    return models, metric_list


def get_data_config_from_json(file_content: Item):
    """
    Trích xuất dữ liệu và cấu hình huấn luyện từ request JSON (Item).

    Args:
        file_content: Đối tượng Item chứa data (list[dict]) và config (dict)

    Returns:
        tuple: (data, choose, list_feature, target, metric_list, metric_sort,
                models, search_algorithm, max_time)
    """
    data = pd.DataFrame(file_content.data)
    config = file_content.config

    choose = config['choose']
    list_feature = config['list_feature']
    target = config['target']
    metric_sort = config['metric_sort']
    # Chuẩn hóa đầu vào
    metric_sort = metric_sort.strip().lower().replace(' ', '_')

    search_algorithm = config.get('search_algorithm', 'grid_search')  # Default to 'grid_search' if not specified
    max_time = config.get('max_time', None)  # Thời gian tối đa (giây), None = dùng default từ YAML

    models, metric_list = get_model()
    return data, choose, list_feature, target, metric_list, metric_sort, models, search_algorithm, max_time


def training(models, metric_list, metric_sort, X_train, y_train, search_algorithm='grid_search', max_time=None):
    """
    Huấn luyện các mô hình classification với tối ưu hóa siêu tham số.

    Hỗ trợ nhiều thuật toán tìm kiếm:
    - 'grid_search': Grid Search (tìm kiếm toàn diện)
    - 'bayesian_search': Bayesian Optimization (tối ưu hóa Bayesian)
    - 'genetic_algorithm': Genetic Algorithm (thuật toán di truyền)

    Args:
        models: Dictionary các mô hình với param grids tương ứng
        metric_list: Danh sách các độ đo để đánh giá (vd: ['accuracy', 'f1_macro'])
        metric_sort: Độ đo chính để chọn mô hình tốt nhất (vd: 'accuracy')
        X_train: Dữ liệu đặc trưng huấn luyện
        y_train: Dữ liệu nhãn mục tiêu huấn luyện
        search_algorithm: Thuật toán tìm kiếm ('grid_search', 'bayesian_search', 'genetic_algorithm')
        max_time: Thời gian tối đa (giây), None = không giới hạn

    Returns:
        tuple: (best_model_id, best_model, best_score, best_params, model_results)
    """
    best_model_id = None
    best_model = None
    best_score = -1
    best_params = {}
    model_results = []

    # Chuẩn hóa đầu vào
    metric_sort = metric_sort.strip().lower().replace(' ', '_')

    def parse_metric(metric_str):
        """
        Phân tích metric string để trả về (base_metric, average_type).
        - 'accuracy' -> ('accuracy', None)
        - 'f1_macro' -> ('f1', 'macro')
        - 'f1_weighted' -> ('f1', 'weighted')
        - 'precision_macro' -> ('precision', 'macro')
        - 'f1' -> ('f1', None) # backward compatibility
        """
        if metric_str == 'accuracy':
            return 'accuracy', None
        
        if metric_str == 'balanced_accuracy':
            return 'balanced_accuracy', None
        
        if metric_str.endswith('_macro'):
            return metric_str[:-6], 'macro'
        elif metric_str.endswith('_weighted'):
            return metric_str[:-9], 'weighted'
        else:
            return metric_str, None

    # Tạo scoring dict từ metric_list
    scoring = {}
    for metric in metric_list:
        base_metric, avg_type = parse_metric(metric)
        
        if base_metric == 'accuracy':
            scoring['accuracy'] = make_scorer(accuracy_score)
        elif base_metric == 'balanced_accuracy':
            scoring['balanced_accuracy'] = make_scorer(balanced_accuracy_score)
        elif base_metric in ['precision', 'recall', 'f1']:
            score_func = {
                'precision': precision_score,
                'recall': recall_score,
                'f1': f1_score
            }[base_metric]
            scoring[metric] = make_scorer(score_func, average=avg_type)

        else:
            # Thử lấy hàm tính điểm động nếu không phải là các metric phổ biến
            score_func = globals().get(f'{base_metric}_score')
            if score_func:
                scoring[metric] = make_scorer(score_func, average=avg_type)
            else:
                raise ValueError(f"Metric không xác định: {metric}")

    # Chuẩn hóa metric_sort
    base_metric_sort, avg_type_sort = parse_metric(metric_sort)
    
    if base_metric_sort in ['accuracy', 'balanced_accuracy']:
        normalized_metric_sort = base_metric_sort
    else:
        normalized_metric_sort = metric_sort

    # Sử dụng factory để tạo chiến lược tìm kiếm với cấu hình
    strategy_config = {
        'cv': 5,
        'scoring': scoring,
        'metric_sort': normalized_metric_sort,
        'error_score': "raise",
        'return_train_score': True
    }
    if max_time is not None:
        strategy_config['max_time'] = max_time
    
    try:
        search_strategy = SearchStrategyFactory.create_strategy(search_algorithm, strategy_config)
    except ValueError as e:
        print(f"Cảnh báo: {e}. Sử dụng tìm kiếm 'grid' mặc định.")
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
        
        # Lấy estimator tốt nhất với các tham số tốt nhất
        best_estimator = model.set_params(**best_params_model)
        best_estimator.fit(X_train, y_train)

        # Trích xuất điểm từ cv_results
        # Chuyển danh sách rank sang numpy array để thực hiện argmin
        rank_key = f'rank_test_{normalized_metric_sort}'
        if rank_key in cv_results:
            rank_array = np.array(cv_results[rank_key])
        else:
            # Dự phòng sang 'rank_test_score' nếu không tìm thấy rank của metric cụ thể
            rank_array = np.array(cv_results.get('rank_test_score', []))
        
        best_idx = rank_array.argmin() if len(rank_array) > 0 else 0
        
        scores_dict = {}
        for metric in metric_list:
            key = f"mean_test_{metric}"
            if key in cv_results:
                scores_dict[metric] = cv_results[key][best_idx]
        
        results = {
            "model_id": model_id,
            "model_name": model.__class__.__name__,
            "best_params": best_params_model,
            "scores": scores_dict,
            "cv_results": cv_results  # Toàn bộ kết quả CV cho tất cả tổ hợp tham số
        }

        model_results.append(results)

        if best_score_model >= best_score:
            best_model_id = model_id
            best_model = best_estimator
            best_score = best_score_model
            best_params = best_params_model
    
    # Chuyển đổi cuối cùng để đảm bảo tất cả giá trị trả về là kiểu Python gốc
    best_params = SearchStrategy.convert_numpy_types(best_params)
    best_score = SearchStrategy.convert_numpy_types(best_score)
    model_results = SearchStrategy.convert_numpy_types(model_results)

    return best_model_id, best_model, best_score, best_params, model_results


# =============================
# CUSTOM SCORER
# =============================
def mse_score(y_true, y_pred):
    """Tính Mean Squared Error (MSE) giữa giá trị thực và dự đoán."""
    return mean_squared_error(y_true, y_pred)

def mae_score(y_true, y_pred):
    """Tính Mean Absolute Error (MAE) giữa giá trị thực và dự đoán."""
    return mean_absolute_error(y_true, y_pred)

def mape_score(y_true, y_pred):
    """Tính Mean Absolute Percentage Error (MAPE), trả về giá trị phần trăm (%)."""
    epsilon = 1e-10
    return np.mean(np.abs((y_true - y_pred) / np.maximum(np.abs(y_true), epsilon))) * 100

def r2_score_sklearn(y_true, y_pred):
    """Wrapper cho sklearn r2_score, tính hệ số xác định R²."""
    return r2_score(y_true, y_pred)

ERROR_METRICS = {'mse', 'mae', 'mape', 'rmse', 'log_loss'}

def safe_extract_score(metric_name, raw_score):
    """
    Chuyển đổi điểm thô từ cross-validation thành giá trị an toàn.

    Xử lý NaN/Inf và lấy giá trị tuyệt đối cho error metrics
    (vì sklearn trả về giá trị âm cho greater_is_better=False).

    Args:
        metric_name: Tên metric (vd: 'mse', 'mae', 'r2')
        raw_score: Điểm thô từ cv_results

    Returns:
        float hoặc None: Giá trị đã xử lý, None nếu NaN/Inf
    """
    if raw_score is None or np.isinf(raw_score) or np.isnan(raw_score):
        return None
    
    if metric_name in ERROR_METRICS:
        return abs(raw_score)
    
    return raw_score


def training_regression(models, metric_list, metric_sort, X_train, y_train, search_algorithm='grid_search', max_time=None):
    """
    Huấn luyện các mô hình regression với tối ưu hóa siêu tham số.
    
    Hỗ trợ nhiều thuật toán tìm kiếm:
    - 'grid_search': Grid Search (tìm kiếm toàn diện)
    - 'bayesian_search': Bayesian Optimization (tối ưu hóa Bayesian)
    - 'genetic_algorithm': Genetic Algorithm (thuật toán di truyền)
    
    Args:
        models: Dictionary các mô hình với param grids tương ứng
        metric_list: Danh sách các độ đo để đánh giá (vd: ['mse', 'mae', 'r2'])
        metric_sort: Độ đo chính để chọn mô hình tốt nhất (vd: 'mse', 'r2')
        X_train: Dữ liệu đặc trưng huấn luyện
        y_train: Dữ liệu nhãn mục tiêu huấn luyện
        search_algorithm: Thuật toán tìm kiếm ('grid_search', 'bayesian_search', 'genetic_algorithm')
    
    Returns:
        Tuple: (best_model_id, best_model, best_score, best_params, model_results)
    """
    # Chuẩn hóa đầu vào
    metric_sort = metric_sort.strip().lower().replace(' ', '_')

    # Nếu sort theo MSE/MAE (càng nhỏ càng tốt)
    if metric_sort in ERROR_METRICS:
        global_best_score = np.inf 
        find_min = True  # Flag: Tìm số nhỏ nhất
    else:
        # Nếu sort theo R2/Accuracy (càng lớn càng tốt) -> Khởi tạo vô cùng nhỏ
        global_best_score = -np.inf
        find_min = False # Flag: Tìm số lớn nhất

    best_model_id = None
    best_model = None
    best_params = {}
    model_results = []

    # Scoring dictionary cho regression
    # Greater_is_better=False sẽ làm cho kết quả trả về là số âm (dùng cho scikit-learn internal)
    scoring = {
        "mse": make_scorer(mse_score, greater_is_better=False),
        "mae": make_scorer(mae_score, greater_is_better=False),
        "mape": make_scorer(mape_score, greater_is_better=False),
        "r2": make_scorer(r2_score_sklearn, greater_is_better=True),
    }
    
    # Sử dụng KFold cho regression (không StratifiedKFold vì target là continuous)
    cv_strategy = KFold(n_splits=5, shuffle=True, random_state=42)

    # Cấu hình cho SearchStrategyFactory
    strategy_config = {
        'cv': cv_strategy,
        'scoring': scoring,
        'metric_sort': metric_sort,
        'error_score': "raise",
        'return_train_score': False,
        'n_jobs': -1,
        'random_state': 42,  # Đảm bảo reproducibility cho Bayesian và GA
    }
    if max_time is not None:
        strategy_config['max_time'] = max_time
    
    # Tạo search strategy từ factory
    try:
        search_strategy = SearchStrategyFactory.create_strategy(search_algorithm, strategy_config)
    except ValueError as e:
        logger.warning(f"Cảnh báo: {e}. Sử dụng tìm kiếm 'grid_search' mặc định.")
        search_strategy = SearchStrategyFactory.create_strategy('grid_search', strategy_config)

    for model_id in range(len(models)):
        model_info = models[model_id]
        # Clone model để tránh thay đổi model gốc (shared state)
        # Đảm bảo mỗi lần gọi training_regression đều có model độc lập
        model = clone(model_info['model'])
        
        # Đặt random_state cho các model có tham số này để đảm bảo
        # kết quả CV giống nhau cho cùng tổ hợp tham số, bất kể thứ tự đánh giá
        if hasattr(model, 'random_state'):
            model.set_params(random_state=42)
        
        param_grid = model_info.get('params') or [{}]

        # Sử dụng search strategy thống nhất
        best_params_model, best_score_model, best_all_scores_model, cv_results = search_strategy.search(
            model=model,
            param_grid=param_grid,
            X=X_train,
            y=y_train
        )
        
        # Chuyển đổi tất cả kiểu numpy sang kiểu Python gốc
        best_params_model = SearchStrategy.convert_numpy_types(best_params_model)
        best_score_model = SearchStrategy.convert_numpy_types(best_score_model)
        cv_results = SearchStrategy.convert_numpy_types(cv_results)

        # Xử lý điểm số cho regression metrics (sử dụng safe_extract_score để xử lý abs và NaN/Inf)
        current_model_score = safe_extract_score(metric_sort, best_score_model)
        
        # Nếu gặp lỗi NaN/Inf thì bỏ qua model này
        if current_model_score is None:
            continue

        # Clone model mới và fit với best params để trả về model độc lập
        best_estimator = clone(model).set_params(**best_params_model)
        if hasattr(best_estimator, 'random_state'):
            best_estimator.set_params(random_state=42)
        best_estimator.fit(X_train, y_train)

        # Trích xuất điểm từ cv_results
        clean_scores = {}
        
        # Tìm index của kết quả tốt nhất
        rank_key = f'rank_test_{metric_sort}'
        if rank_key in cv_results and cv_results[rank_key]:
            rank_array = np.array(cv_results[rank_key])
            best_idx = rank_array.argmin() if len(rank_array) > 0 else 0
        elif 'rank_test_score' in cv_results and cv_results['rank_test_score']:
            rank_array = np.array(cv_results['rank_test_score'])
            best_idx = rank_array.argmin() if len(rank_array) > 0 else 0
        else:
            best_idx = 0
            
        for metric in metric_list:
            key = f"mean_test_{metric}"
            if key in cv_results and len(cv_results[key]) > best_idx:
                raw_val = cv_results[key][best_idx]
                clean_scores[metric] = safe_extract_score(metric, raw_val)
            else:
                clean_scores[metric] = None

        results = {
            'model_id': model_id,
            'model_name': model.__class__.__name__,
            'best_params': best_params_model,
            "scores": clean_scores,
            "cv_results": cv_results  # Toàn bộ kết quả CV cho tất cả tổ hợp tham số
        }
        model_results.append(results)

        if find_min:
            is_better = current_model_score <= global_best_score
        else:
            is_better = current_model_score >= global_best_score
        
        if is_better:
            global_best_score = current_model_score
            best_model_id = model_id
            best_model = best_estimator
            best_params = best_params_model

    return best_model_id, best_model, global_best_score, best_params, model_results


def train_process(X_train, y_train, metric_list, metric_sort, models, problem_type, search_algorithm='grid_search', max_time=None):
    """
    Điều phối quá trình huấn luyện dựa trên loại bài toán.

    Gọi `training()` cho classification hoặc `training_regression()` cho regression.

    Args:
        X_train: Dữ liệu đặc trưng huấn luyện
        y_train: Dữ liệu nhãn mục tiêu
        metric_list: Danh sách các độ đo đánh giá
        metric_sort: Độ đo chính để xếp hạng
        models: Dictionary các mô hình và param grids
        problem_type: Loại bài toán ('classification' hoặc 'regression')
        search_algorithm: Thuật toán tìm kiếm siêu tham số
        max_time: Thời gian tối đa (giây), None = không giới hạn

    Returns:
        tuple: (best_model_id, best_model, best_score, best_params, model_scores)
    """
    best_model_id, best_model, best_score, best_params, model_scores = None, None, None, None, None

    if problem_type == 'classification':
        best_model_id, best_model, best_score, best_params, model_scores = training(models, metric_list, metric_sort,
                                                                                X_train, y_train, search_algorithm, max_time)
    if problem_type == 'regression':
        best_model_id, best_model, best_score, best_params, model_scores = training_regression(models, metric_list, metric_sort, X_train, y_train, search_algorithm, max_time)
    
    return best_model_id, best_model, best_score, best_params, model_scores


def app_train_local(file_data, file_config):
    """
    Huấn luyện mô hình từ file CSV và file config YAML upload trực tiếp.

    Đọc dữ liệu từ file_data (CSV), cấu hình từ file_config (YAML),
    tiền xử lý rồi gọi train_process.

    Args:
        file_data: File upload chứa dữ liệu CSV
        file_config: File upload chứa cấu hình YAML

    Returns:
        tuple: (best_model_id, best_model, best_score, best_params, model_scores)
    """
    contents = file_data.file.read()
    data_file = BytesIO(contents)
    data = pd.read_csv(data_file)

    contents = file_config.file.read()
    data_file_config = BytesIO(contents)
    choose, list_feature, target, metric_list, metric_sort, models, search_algorithm, max_time = get_config(data_file_config)

    X_processed, y_processed, preprocessor, le_target = preprocess_data(list_feature, target, data) # Thiếu problem_type

    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        X_processed, y_processed, metric_list, metric_sort, models, search_algorithm, max_time
    )

    return best_model_id, best_model, best_score, best_params, model_scores


# Chuyển đổi ObjectId sang string để trả về cho client
def serialize_mongo_doc(doc):
    """
    Chuyển đổi ObjectId trong document MongoDB sang string.

    Args:
        doc: Document dict từ MongoDB

    Returns:
        dict: Document đã chuyển đổi _id sang string
    """
    doc["_id"] = str(doc["_id"])
    return doc


# Không dùng kafka
async def train_json(item: Item, userId, id_data, db: AsyncDatabase):
    """
    API endpoint xử lý huấn luyện mô hình từ dữ liệu JSON.

    Nhận dữ liệu và cấu hình từ Item, thực hiện tiền xử lý, huấn luyện,
    lưu kết quả vào MongoDB và trả về thông tin job.

    Args:
        item: Đối tượng Item chứa data và config từ client
        userId: ID của người dùng
        id_data: ID của dataset
        db: Kết nối AsyncDatabase MongoDB

    Returns:
        JSONResponse: Thông tin job đã tạo

    Raises:
        HTTPException: Nếu lưu job thất bại
    """
    job_collection = db.tbl_Job

    data, choose, list_feature, target, metric_list, metric_sort, models, search_algorithm, max_time = (
        get_data_config_from_json(item)
    )

    X_processed, y_processed, preprocessor, le_target = preprocess_data(list_feature, target, data)

    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        X_processed, y_processed, metric_list, metric_sort, models, search_algorithm, max_time
    )

    data_name, user_name = await get_dataset_and_user_info(id_data, userId, db)
    model_data = pickle.dumps(best_model)
    job_id = str(uuid4())

    # Đảm bảo tất cả giá trị được chuyển đổi đúng sang kiểu Python gốc trước khi lưu
    
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


# Suy luận kết quả
async def inference_model(job_id: str, user_id: str, file_data, db: AsyncDatabase):
    """
    Chạy dự đoán trên dữ liệu mới bằng mô hình đã huấn luyện.

    Tải model, preprocessor và label encoder từ MinIO, biến đổi dữ liệu
    đầu vào rồi thực hiện dự đoán.

    Args:
        job_id: ID của job huấn luyện đã hoàn thành
        user_id: ID của người dùng sở hữu job
        file_data: File upload chứa dữ liệu CSV cần dự đoán
        db: Kết nối AsyncDatabase MongoDB

    Returns:
        list[dict]: Dữ liệu gốc kèm cột 'predict' chứa kết quả dự đoán
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
        """Hàm helper để tải và nạp file"""
        try:
            buffer = await asyncio.to_thread(minIOStorage.get_object, bucket, path)
            return await asyncio.to_thread(type.load, buffer)
        except Exception as e:
            raise ValueError(f"Failed to load artifact from {path}: {str(e)}")
        
    try:
        # Tải đồng thời cả 3 file
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
        # Sử dụng preprocessor đã lưu để biến đổi dữ liệu
        X_new_transformed = await asyncio.to_thread(preprocessor.transform, data_to_predict)
        
        if isinstance(X_new_transformed, np.ndarray):
            X_new_transformed = np.nan_to_num(X_new_transformed, nan=0.0, posinf=0.0, neginf=0.0)
        elif hasattr(X_new_transformed, "toarray"): # Nếu là sparse matrix
            X_new_transformed = X_new_transformed.toarray()
            X_new_transformed = np.nan_to_num(X_new_transformed, nan=0.0, posinf=0.0, neginf=0.0)

        # Sử dụng mô hình đã lưu để dự đoán
        y_pred_raw = await asyncio.to_thread(model.predict, X_new_transformed)
        
        if hasattr(y_pred_raw, 'ravel'):
            y_pred_raw = y_pred_raw.ravel()

        if le_target:
            # Sử dụng le_target đã lưu để chuyển đổi ngược nhãn
            y_pred_final = await asyncio.to_thread(le_target.inverse_transform, y_pred_raw)
        else:
            y_pred_final = y_pred_raw
    except Exception as e:
        return {"error": f"Failed during prediction process: {str(e)}"}
    
    data['predict'] = y_pred_final
    data = data.replace({np.nan: None})

    data_json = await asyncio.to_thread(data.to_dict, orient="records")
    return data_json


# Lấy danh sách job
async def get_jobs(user_id, db: AsyncDatabase):
    """
    Lấy danh sách tất cả job huấn luyện từ MongoDB.

    Args:
        user_id: ID người dùng để lọc (None = lấy tất cả)
        db: Kết nối AsyncDatabase MongoDB

    Returns:
        JSONResponse: Danh sách job (không bao gồm model binary và user info)

    Raises:
        HTTPException: Nếu truy vấn thất bại
    """
    job_collection = db.tbl_Job

    try:
        query = {}
        if user_id:
            query["user.id"] = user_id

        jobs = await job_collection.find(query, {"model": 0, "item": 0, "user": 0}).to_list(length=None)
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
    """
    Lấy thông tin chi tiết một job theo ID.

    Args:
        id_job: ID của job cần truy vấn
        db: Kết nối AsyncDatabase MongoDB

    Returns:
        JSONResponse: Thông tin chi tiết job

    Raises:
        HTTPException: Nếu không tìm thấy job hoặc truy vấn lỗi
    """
    job_collection = db.tbl_Job
    try:
        job = await job_collection.find_one({"job_id": id_job}, {"model": 0, "item": 0, "user": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Không tìm thấy job với ID đã cho.")

        for key, value in job.items():
            if isinstance(value, datetime):
                job[key] = value.timestamp()

        return JSONResponse(content=serialize_mongo_doc(job))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi truy vấn job: {str(e)}")


async def update_activate_model(job_id, db: AsyncDatabase, activate=0):
    """
    Cập nhật trạng thái kích hoạt/vô hiệu hóa của mô hình.

    Args:
        job_id: ID của job chứa mô hình
        db: Kết nối AsyncDatabase MongoDB
        activate: Trạng thái mới (0 = vô hiệu hóa, 1 = kích hoạt)

    Returns:
        JSONResponse: Xác nhận cập nhật thành công
    """
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
