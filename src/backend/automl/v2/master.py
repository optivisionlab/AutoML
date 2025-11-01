import asyncio
import base64
import os
import yaml
import time
import logging
import itertools

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter


load_dotenv()

NUMBER_WORKERS = int(os.getenv('NUMBER_WORKERS', 1))
WORKER_LIST = os.getenv("WORKER_LIST", '')

WORKERS = [f"{WORKER_LIST.split(',')[i]}" for i in range(NUMBER_WORKERS)]


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


# =========================================================================
# CẤU TRÚC DỮ LIỆU TRUNG TÂM
# =========================================================================

# Hàng đợi ưu tiên: (priority, task)
# Ưu tiên 0 = Data Locality HIT (ưu tiên cao nhất)
# Ưu tiên 1 = Data Locality MISS
GLOBAL_TASK_QUEUE = asyncio.PriorityQueue()

# Sổ theo dõi tiến độ Job
# Key: job_id, Value: dict chứa thông tin job
JOB_TRACKER: dict[str, dict] = {}

# Sổ theo dõi các Task đang được giao (Dùng cho Heartbeat)
# Key: task_id, Value: dict chứa thông tin task
ACTIVE_TASKS: dict[str, dict] = {}
TASK_TIMEOUT_SECONDS = int(os.getenv("TASK_TIMEOUT_SECONDS", 600)) # 10 phút

# Bộ đếm TIE-BREAKER cho PriorityQueue
task_counter = itertools.count()

# =========================================================================
# LOGIC CỦA JOB
# =========================================================================
async def setup_job_tasks(job_id: str, id_data: str, id_user: str, config: dict):
    """
    Tạo task và bỏ vào hàng đợi ưu tiên toàn cục
    """
    was_queue_empty = GLOBAL_TASK_QUEUE.empty()

    models, metric_list = await asyncio.to_thread(get_models)

    JOB_TRACKER[job_id] = {
        "total_tasks": len(models),
        "completed_tasks": 0,
        "results": [],
        "completion_event": asyncio.Event(),
        "config": config,
        "id_user": id_user,
        "id_data": id_data
    }

    tasks_added = 0
    for model_id, model_info in models.items():
        task = {
            "task_id": f"{job_id}_{model_info['model']}",
            "job_id": job_id,
            "id_data": id_data,
            "config": config,
            "model_info": model_info,
            "metrics": metric_list
        }
        entry_count = next(task_counter)
        await GLOBAL_TASK_QUEUE.put((1, entry_count, task))
        tasks_added += 1

    if was_queue_empty and tasks_added > 0:
        async with httpx.AsyncClient() as client:
            signal_tasks = [
                client.get(f"{worker}/check-for-work", timeout=5.0)
                for worker in WORKERS
            ]
            results = await asyncio.gather(*signal_tasks, return_exceptions=True)
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    logging.warning(f"[{job_id}] Failed to send signal to worker {WORKERS[i]}: {res}")


def reduce_results_for_job(job_id: str):
    """
    Tổng hợp kết quả cuối cùng cho một job
    """
    tracker = JOB_TRACKER[job_id]
    valid_results = [r for r in tracker["results"] if r.get("success")]
    if not valid_results:
        raise ValueError("No successful results from workers")
    
    final_model_scores = []
    for i, result in enumerate(valid_results):
        score_entry = {
            "model_id": i,
            "model_name": result["model_name"],
            "scores": result.get("scores"),
            "best_params": result.get("best_params", {})
        }
        final_model_scores.append(score_entry)

    metric = tracker["config"].get("metric_sort", "accuracy")
    best_model_info = max(final_model_scores, key=lambda x: x["scores"].get(metric, -1.0))
    
    original_best_result = next(
        r for r in valid_results if r["model_name"] == best_model_info["model_name"]
    )
    model_bytes = base64.b64decode(original_best_result["model_base64"])

    # Trả về kết quả cuối cùng
    return {
        "best_model_id": str(best_model_info["model_id"]),
        "model": model_bytes,
        "best_model": best_model_info["model_name"],
        "best_score": original_best_result["score"],
        "best_params": best_model_info.get("best_params", {}),
        "model_scores": final_model_scores
    }


async def handle_task_result_submission(result: dict):
    """Xử lý kết quả được worker gửi về"""
    job_id = result.get("job_id")
    model_name = result.get("model_name")
    if not job_id or not model_name:
        logging.error(f"Received invalid result: {result}")
        return {"status": "Invalid result"}
    
    task_id = f"{job_id}_{model_name}"

    if task_id in ACTIVE_TASKS:
        ACTIVE_TASKS.pop(task_id, None)
    
    # Gửi kết quả cho JobTracker
    if not job_id or job_id not in JOB_TRACKER:
        logging.error(f"Received result for unknown job: {job_id}")
        return {"status": "Failure"}

    tracker = JOB_TRACKER[job_id]
    
    tracker["results"].append(result)
    if result.get("success"):
        tracker["completed_tasks"] += 1

        if tracker["completed_tasks"] >= tracker["total_tasks"]:
            print(f"[{job_id}] All tasks completed")
            tracker["completion_event"].set()

    return {"status": "success"}


async def get_prioritized_task(worker_url: str, cached_id_data: str | None = None):
    # Đẩy các task có data locality lên đầu hàng đợi
    if cached_id_data and not GLOBAL_TASK_QUEUE.empty():
        temp_tasks = []
        found_local_task = False
        while not GLOBAL_TASK_QUEUE.empty():
            priority, entry_count, task = GLOBAL_TASK_QUEUE.get_nowait()

            if priority > 0 and task.get("id_data") == cached_id_data:
                await GLOBAL_TASK_QUEUE.put((0, entry_count, task))
                found_local_task = True
            else:
                temp_tasks.append((priority, entry_count, task))

        
        for item in temp_tasks:
            await GLOBAL_TASK_QUEUE.put(item)
            
        if found_local_task:
            print(f"[Master] Data Locality HIT for worker {worker_url} on data {cached_id_data}")

    # Lấy task có ưu tiên cao nhất
    try:
        priority, entry_count, task = GLOBAL_TASK_QUEUE.get_nowait()
        task_id = task["task_id"]
        
        # Ghi lại vào sổ theo dõi Heartbeat
        ACTIVE_TASKS[task_id] = {
            "worker_url": worker_url,
            "start_time": time.time(),
            "task_data": task,
            "entry_count": entry_count
        }
        
        return task
    except asyncio.QueueEmpty:
        return None



# =========================================================================
# LOGIC HEARTBEAT
# =========================================================================
WORKER_REGISTRY = {}

async def monitor_tasks():
    """
    Chạy nền để kiểm tra các task bị kẹt và worker bị chết.
    Chạy ở lifespan trong app.py
    """
    async with httpx.AsyncClient() as monitor_client:
        while True:
            await asyncio.sleep(TASK_TIMEOUT_SECONDS)

            frozen_tasks = list(ACTIVE_TASKS.items())
            current_time = time.time()

            for task_id, task_info in frozen_tasks:
                if (current_time - task_info["start_time"]) <= TASK_TIMEOUT_SECONDS:
                    continue

                dead_worker_url = task_info.get("worker_url")
                if not dead_worker_url:
                    continue

                logging.warning(f"[Monitor] Task {task_id} timed out. Checking worker {dead_worker_url}") 

                try:
                    # Ping worker để kiểm tra
                    await monitor_client.get(f"{dead_worker_url}/health", timeout=5.0)
                    print(f"[Monitor] Worker {dead_worker_url} is alive but slow")

                except (httpx.RequestError, httpx.TimeoutException):
                    logging.error(f"[Monitor] Worker {dead_worker_url} is DEAD. Re-queueing task {task_id}")

                    WORKER_REGISTRY.pop(dead_worker_url, None)

                    # Đẩy task trở lại hàng đợi (với ưu tiên cao nhất)
                    original_entry_count = task_info["entry_count"]
                    await GLOBAL_TASK_QUEUE.put((0, original_entry_count, task_info["task_data"]))
                    
                    # Xóa khỏi danh sách đang theo dõi
                    ACTIVE_TASKS.pop(task_id, None)

                    for worker_url, info in WORKER_REGISTRY.items():
                        if info.get('status') == 'idle':
                            try:
                                await monitor_client.get(f"{worker_url}/check-for-work", timeout=5.0)
                                break
                            except Exception as e:
                                logging.error(f"[Monitor] Failed to wake up replacement worker {worker_url}: {e}")
            


# =========================================================================
# FASTAPI APP
# =========================================================================
master = APIRouter()

@master.get("/task/get")
async def api_get_task(cached_id_data: str | None = None, worker_url: str | None = None):
    if worker_url:
        WORKER_REGISTRY[worker_url] = {
            'status': 'idle'
        }

    task = await get_prioritized_task(worker_url, cached_id_data)
    if task and worker_url:
        WORKER_REGISTRY[worker_url] = {
            'status': 'working'
        }

    return {"task": task}


@master.post("/task/submit")
async def api_submit_result(result: dict):
    status = await handle_task_result_submission(result)

    return status