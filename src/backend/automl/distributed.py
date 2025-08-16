from pydantic import BaseModel
import pandas as pd
import os, yaml
import httpx
from concurrent.futures import ThreadPoolExecutor

from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering, MeanShift, SpectralClustering
from sklearn.discriminant_analysis import StandardScaler
from sklearn.calibration import LabelEncoder

from automl.engine import train_process

# Xử lý map reduce
# định nghĩa hàm Map (xử lý từng cặp khóa/giá trị đầu vào)
# định nghĩa hàm Reduce (hợp nhất các giá trị liên quan đến cùng một khóa trung gian)
# mỗi model có thể được train độc lập trên cùng dataset
# Map: Ánh xạ mỗi model/config thành một task training riêng
# Reduce: Tổng hợp kết quả (model có điểm số tốt nhất)
workers = [
    "http://0.0.0.0:4001",
    "http://0.0.0.0:4002"
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
    


def reduce_function(model_trains):
    """Tổng hợp kết quả và chọn model tốt nhất"""
    """
    Args:
        model_trains: Danh sách các đối tượng model đã train từ các worker
        
    Returns:
        dict: Kết quả tổng hợp gồm best model và tất cả model_scores
    """
    results = []
    for model in model_trains:
        try:
            result = model.result() # blocking call
            if result.get("success"):
                results.extend(result.get("results", []))

        except Exception as e:
            print(f"Error processing: {str(e)}")
            continue
    
    if not results:
        raise ValueError("No valid results found")

    all_model_scores = []
    model_id_counter = 0

    # Gộp và đánh lại ID cho tất cả model
    for model in results:
        for model_score in model.get("model_scores", []):
            if not isinstance(model_score, dict):
                continue

            model_score = model_score.copy()
            model_score["model_id"] = model_id_counter
            all_model_scores.append(model_score)
            model_id_counter += 1
    
    if not all_model_scores:
        raise ValueError("No valid model scores found")

    # Chọn model tốt nhất theo accuracy
    best_model_info = max(all_model_scores, key=lambda x: x["scores"]["accuracy"])
    

    return {
        "best_model_id": str(best_model_info["model_id"]),
        "best_model": best_model_info['model_name'],
        "best_score": best_model_info["scores"]["accuracy"],
        "best_params": best_model_info.get("best_params", {}),
        "model_scores": all_model_scores
    }


# Quy trinh Map Reduce
def process (file_content):
    data, config, metric_list, models = get_data_config_from_json_distribute(file_content)

    respone_worker = run_mapreduce(data, config, metric_list, models)

    results = reduce_function(respone_worker)

    return results, respone_worker



# Xu ly tai mot server API http://localhost:9999/distributed

# Xu ly tai mot server API http://localhost:9999/try
def train_jsons(item: InputRequest):
    data, config, metric_list, models = (
        get_data_config_from_json_distribute(item)
    )

    data = pd.DataFrame(data)
    for id, content in models.items():
        content['model'] = eval(content['model'])()

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

