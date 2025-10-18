# Standard Libraries
import os, yaml
import base64

# Third-party Libraries
import httpx, asyncio
from dotenv import load_dotenv


# Xử lý map reduce
# định nghĩa hàm Map (xử lý từng cặp khóa/giá trị đầu vào)
# định nghĩa hàm Reduce (hợp nhất các giá trị liên quan đến cùng một khóa trung gian)
# mỗi model có thể được train độc lập trên cùng dataset
# Map: Ánh xạ mỗi model/config thành một task training riêng
# Reduce: Tổng hợp kết quả (model có điểm số tốt nhất)

# load from environment
load_dotenv()

HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 8000))
NUMBER_WORKERS = int(os.getenv('NUMBER_WORKERS', 1))

WORKERS = [f"http://{HOST}:{PORT + i}" for i in range(NUMBER_WORKERS)]


def get_models():
    base_dir = "assets/system_models"
    file_path = os.path.join(base_dir, "model.yml")
    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    
    models = {}
    for key, model_info in data['Classification_models'].items():
        models[key] = {
            "model": model_info["model"],
            "params": model_info['params']
        }

    metric_list = data['metric_list']
    return models, metric_list 



def split_models(models, n_workers=1):
    """
    Chia đều model thành n phần và đánh số lại ID từ 0
    Lý do đánh số lại vì hàm training lấy model theo id, mà id lại duyệt vòng for range(len(models))
    """
    if n_workers <= 0:
        raise ValueError("Number of workers must be a positive integer")
    
    model_items = list(models.items())
    
    # Chia thành n phần bằng list comprehension
    splits = (model_items[i::n_workers] for i in range(n_workers))
    
    # Đánh số lại ID và tạo dict mới
    result = [
        {
            new_id: model_data
            for new_id, (old_id, model_data) in enumerate(split)
        }
        for split in splits
    ]
    
    return result



# ------------------------------------------------------------------------------------
"""Xử lý bất đồng bộ cùng với chỉ gửi models_part qua api"""
async def send_to_worker_async(worker_url, models_part, metric_list, id_data, config, client):
    """
    Hàm bất đồng bộ gửi yêu cầu post với dữ liệu đến một server
    """
    payload = {
        "metrics": metric_list,
        "models": models_part,
        "id_data": id_data,
        "config": config
    }

    try:
        response = await client.post(
            f"{worker_url}/train",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5000
        )
        print(f"Hello {worker_url}")
        response.raise_for_status() # Ném lỗi nếu status code là 4xx hoặc 5xx
        return response.json()
    
    except httpx.HTTPError as exc:
        print(f"Error contacting worker {worker_url}: {str(exc)}")
        return {
            "success": False,
            "error": str(exc),
            "results": []
        }

    except httpx.RequestError as exc:
        print(f"Unexpected error: {str(exc)}")
        return {
            "success": False,
            "error": str(exc),
            "results": []
        }



async def run_mapreduce_async(metric_list, models, workers, id_data, config):
    """
    Điều phối bất đồng bộ để gửi request đến các worker song song
    """
    models_splits = split_models(models, len(workers))

    # AsyncClient để tái sử dụng kết nối
    async with httpx.AsyncClient() as client:
        # Các tác vụ bất đồng bộ
        tasks = []
        for worker, models_part in zip(workers, models_splits):
            task = asyncio.create_task(
                send_to_worker_async(
                    worker_url=worker,
                    models_part=models_part,
                    metric_list=metric_list,
                    id_data = id_data,
                    config = config,
                    client=client
                )
            )
            tasks.append(task)

        # Chạy tất cả các tác vụ và đồng thời trả về kết quả
        # Chờ đợi tất cả các tác vụ hoàn thành (none-blocking)
        # return_exceptions=True để không bị dừng nếu có task bị lỗi
        return await asyncio.gather(*tasks, return_exceptions=True)



async def reduce_async(worker_responses):
    """Tổng hợp kết quả bất đồng bộ và chọn model tốt nhất"""
    """
    all_responses: Danh sách từ các worker
    """
    combined_results = []

    best_model_base64 = None
    best_overall_score = -1.0 

    for response in worker_responses:
        if isinstance(response, Exception):
            print(f"Error processing a worker response: {response}")
            continue  

        if response.get("success"):
            combined_results.extend(response.get("model_scores", []))
                    
            # Lấy thông tin từ phản hồi của worker
            current_best_score = response.get("best_score", -1.0)
            current_best_model_base64 = response.get("best_model")

            # So sánh và cập nhật mô hình tốt nhất
            if current_best_score > best_overall_score:
                best_overall_score = current_best_score
                best_model_base64 = current_best_model_base64
    
    if best_model_base64 is None:
        raise ValueError("No valid results found to determine the best model")
    
    if not combined_results:
        raise ValueError("No valid results found")
    
    model_bytes = base64.b64decode(best_model_base64)
    
    # Đánh số thứ tự danh sách model
    final_model_scores = []
    model_id_counter = 0

    for model_score in combined_results:
        if not isinstance(model_score, dict):
            continue

        model_score = model_score.copy()
        model_score["model_id"] = model_id_counter
        final_model_scores.append(model_score)
        model_id_counter += 1

    if not final_model_scores:
        raise ValueError("No valid model scores found")
    
    best_model_info = max(final_model_scores, key=lambda x: x["scores"]["accuracy"])

    return {
        "best_model_id": str(best_model_info["model_id"]),
        "best_model": best_model_info['model_name'],
        "model": model_bytes, # Thể hiện của mô hình, dùng khi cần model đã train, đã được tuần tự hóa bằng pickle.dumps()
        "best_score": best_model_info["scores"]["accuracy"],
        "best_params": best_model_info.get("best_params", {}),
        "model_scores": final_model_scores
    }
   

async def process_async(id_data: str, config: dict):

    models, metric_list = await asyncio.to_thread(get_models)

    # Giai đoạn Map: Gửi request bất đồng bộ và nhận lại các phản hồi
    print("starting")
    worker_responses = await run_mapreduce_async(metric_list, models, WORKERS, id_data, config)

    # Đếm số worker thành công dựa trên kết quả
    successful_workers_count = sum(1 for res in worker_responses if isinstance(res, dict) and res.get("success"))

    # Giai đoạn Reduce: Tổng hợp kết quả từ các phản hồi
    results = await reduce_async(worker_responses)

    # Trả về cả kết quả tổng hợp và danh sách các phản hồi
    return results, len(worker_responses), successful_workers_count

