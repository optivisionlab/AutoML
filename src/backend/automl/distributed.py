from pydantic import BaseModel
import pandas as pd
import os, yaml
import numpy as np
import asyncio
import httpx
import requests
from concurrent.futures import ThreadPoolExecutor

from automl.engine import train_process

# Xử lý map reduce
# định nghĩa hàm Map (xử lý từng cặp khóa/giá trị đầu vào)
# định nghĩa hàm Reduce (hợp nhất các giá trị liên quan đến cùng một khóa trung gian)
# mỗi model có thể được train độc lập trên cùng dataset
# Map: Ánh xạ mỗi model/config thành một task training riêng
# Reduce: Tổng hợp kết quả (model có điểm số tốt nhất)
workers = [
    "http://0.0.0.0:4002",
    "http://0.0.0.0:4001"
]

class InputRequest(BaseModel):
    data: list[dict] 
    config: dict

def get_models():
    base_dir = "assets/system_models"
    file_path = os.path.join(base_dir, "model.yml")
    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    
    models = {}
    for key, model_info in data['Classification_models'].items():
        models[key] = {
            "model": model_info["model"], # không thể gửi kiểu dữ liệu phức tạp qua json eval(model_info["model"])()
            "params": model_info['params']
        }

    metric_list = data['metric_list']
    return models, metric_list 


def get_data_config_from_json_distribute(file_content: InputRequest):
    data = file_content.data 
    config = file_content.config
    models, metric_list = get_models()
    
    return (
        data,
        config,
        metric_list,
        models
    ) 



# def reduce_function (results):
#     """Tổng hợp kết quả và chọn model tốt nhất"""
#     best_score = -1
#     best_result = None

#     for result in results:
#         _, _, score, _, _ = result
#         if score > best_score:
#             best_score = score
#             best_result = result
    
#     return best_result, results # Model tot nhat va toan bo ket qua. Chua dung toi



def split_models(models, n_workers=2):
    """Chia đều model thành n phần và đánh số lại ID từ 0"""
    """
    Lý do đánh số lại vì hàm training lấy model theo id, mà id lại duyệt vòng for range(len(models))
    """
    model_items = list(models.items())
    
    # Chia thành n phần
    splits = [model_items[i::n_workers] for i in range(n_workers)]
    
    # Đánh số lại ID và tạo dict mới
    result = []
    for split in splits:
        new_dict = {}
        for new_id, (old_id, model_data) in enumerate(split):
            new_dict[int(new_id)] = model_data  # Chuyển ID mới thành int
        result.append(new_dict)
    
    return result



def send_to_worker(worker_url, models_part, data, config, metric_list):
    payload = {
        "data": data,
        "config": config,
        "metrics": metric_list,
        "models": models_part
    }

    # lay du lieu de gui den cac worker. Y/c du lieu co ban
    try:
        with httpx.Client() as client:
            response = client.post(
                f"{worker_url}/train",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPError as e:
        print(f"Error contacting worker {worker_url}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "results": []
        }
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "results": []
        }


def run_mapreduce(data, config, metric_list, models):
    models_split = split_models(models, len(workers))
    with ThreadPoolExecutor() as executor:
        futures = []
        for worker, models_part in zip(workers, models_split):
            
            future = executor.submit(
                send_to_worker,
                worker,
                models_part,
                data,
                config,
                metric_list
            )

            futures.append(future)
        
        return futures



def process (file_content):
    data, config, metric_list, models = get_data_config_from_json_distribute(file_content)

    futures = run_mapreduce(data, config, metric_list, models)

    return futures


# Xu ly tai mot server API http://localhost:9999/distributed

# Xu ly tai mot server API http://localhost:9999/try
def train_jsons(item: InputRequest):
    data, config, metric_list, models = (
        get_data_config_from_json_distribute(item)
    )

    choose = config['choose']
    list_feature = config['list_feature']
    target = config['target']
    metric_sort = config['metric_sort']

    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        data, choose, list_feature, target, metric_list, metric_sort, models
    )

    return best_model_id, best_model, best_score, best_params, model_scores




if __name__ == "__main__":
    models, metric_list = get_models()
    print(models)
    print("------------------------------")
    print(metric_list)

