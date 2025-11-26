import asyncio
import os
import yaml
import time
import logging
import itertools
import hashlib
import json

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

from automl.v2.minio import minIOStorage
from database.get_dataset import MongoJob
from database.database import get_db


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



def get_config_hash(id_data: str, list_feature: list, target: str) -> str:
    """
    Tạo một hash duy nhất dựa trên data và cấu hình tiền xử lý.
    """
    # Sắp xếp list_feature
    sorted_features = sorted(list_feature)

    # Tạo một chuỗi đại diện duy nhất
    key_string = f"{id_data}-{json.dumps(sorted_features)}-{target}"

    # Trả về hash MD5 của chuỗi
    return hashlib.md5(key_string.encode('utf-8')).hexdigest()



# =========================================================================
# CẤU TRÚC DỮ LIỆU TRUNG TÂM
# =========================================================================

# Hàng đợi chung cho các task chưa phân loại
# Ưu tiên 0 = Task bị timeout
# Ưu tiên 1 = Task mới
GLOBAL_TASK_QUEUE = asyncio.PriorityQueue()

# Hàng đợi riêng cho từng Data ID
# Key: task_cache_key, Value: asyncio.Queue (FIFO)
LOCAL_QUEUES: dict[str, asyncio.Queue] = {}

# Lock để bảo vệ việc tạo hàng đợi mới trong LOCAL_QUEUES
LOCAL_QUEUE_LOCK = asyncio.Lock()

# Theo dõi tiến độ Job
# Key: job_id, Value: dict chứa thông tin job
JOB_TRACKER: dict[str, dict] = {}

# Theo dõi các Task đang được giao (Dùng cho Heartbeat)
# Key: task_id, Value: dict chứa thông tin task
ACTIVE_TASKS: dict[str, dict] = {}
TASK_TIMEOUT_SECONDS = int(os.getenv("TASK_TIMEOUT_SECONDS", 3600)) # 1 giờ
MAX_TASK_SNOOZES = int(os.getenv("MAX_TASK_SNOOZES", 1))

# Bộ đếm TIE-BREAKER cho PriorityQueue
task_counter = itertools.count()

# =========================================================================
# LOGIC CỦA JOB
# =========================================================================
async def setup_job_tasks(job_id: str, id_data: str, id_user: str, config: dict, cache_key: str):
    """
    Tạo task và bỏ vào hàng đợi ưu tiên toàn cục
    """
    was_queue_empty = GLOBAL_TASK_QUEUE.empty()
    models, metric_list = await asyncio.to_thread(get_models)

    list_feature = config.get('list_feature', [])
    target = config.get('target', '')
    # cache_key = get_config_hash(id_data, list_feature, target)
    

    JOB_TRACKER[job_id] = {
        "total_tasks": len(models),
        "completed_tasks": 0,
        "results": [],
        "completion_event": asyncio.Event(),
        "config": config,
        "id_user": id_user
    }

    tasks_added = 0
    for model_id, model_info in models.items():
        task = {
            "task_id": f"{job_id}_{model_info['model']}",
            "job_id": job_id,
            "id_data": id_data,
            "config": config,
            "model_info": model_info,
            "metrics": metric_list,
            "cache_key": cache_key
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



async def reduce_results_for_job(job_id: str, db: AsyncDatabase):
    job_update = MongoJob(db)
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
            "model_name": result.get("model_name", ""),
            "scores": result.get("scores"), # bao gồm cả 4 tiêu chí
            "best_params": result.get("best_params", {})
        }
        final_model_scores.append(score_entry)

    metric = tracker["config"].get("metric_sort", "accuracy")
    best_model_info = max(final_model_scores, key=lambda x: x['scores'].get(metric, -1.0))

    original_best_result = next(
        r for r in valid_results if r['model_name'] == best_model_info['model_name']
    )

    # Thao tác với Cloud và Database
    try:
        # Move model tốt nhất lưu ở bộ nhớ tạm vào folder chính
        version = 1
        dest_model_path = f"{tracker['id_user']}/{job_id}/{best_model_info['model_name']}_{version}.pkl"

        await asyncio.to_thread(
            minIOStorage.move_model,
            source_bucket=original_best_result["model"].get("bucket_name"),
            source_model=original_best_result["model"].get("object_name"),
            dest_bucket="models",
            dest_model=dest_model_path
        )

        final_result_payload = {
            "best_model_id": best_model_info["model_id"],
            "best_model": best_model_info["model_name"],
            "model": {
                "bucket_name": "models",
                "object_name": dest_model_path
            },
            "best_params": best_model_info["best_params"],
            "best_score": original_best_result["score"],
            "model_scores": final_model_scores
        }

        await job_update.update_success(job_id, final_result_payload)
        return True
    
    except Exception as e:
        error_msg = f"Update failure: {str(e)}"
        await job_update.update_failure(job_id, error_msg)
        raise Exception(f"{error_msg}")



async def run_reduction_and_cleanup(job_id: str, db: AsyncDatabase):
    job_update = MongoJob(db)
    """
    Chạy reduce và dọn dẹp job trong một background task
    """
    if job_id not in JOB_TRACKER:
        logging.warning(f"[{job_id}] Job tracker not found for cleanup.")
        return
    
    try:
        # Chạy hàm reduce trong một thread riêng
        await reduce_results_for_job(job_id, db)
        print(f"[{job_id}] Reduction successful.")

    except Exception as e:
        await job_update.update_failure(job_id, f"Reduction failed: {str(e)}")

    finally:
        JOB_TRACKER.pop(job_id, None)



async def handle_task_result_submission(result: dict, db: AsyncDatabase):
    """Xử lý kết quả được worker gửi về"""
    job_id = result.get("job_id")
    model_name = result.get("model_name")
    worker_url = result.get("worker_url")

    if not job_id or not model_name or not worker_url:
        logging.error(f"Received invalid result: {result}")
        return {"status": "Invalid result payload"}
    
    task_id = f"{job_id}_{model_name}"

    if task_id not in ACTIVE_TASKS:
        return {"status": "stale_discarded"}
    
    activate_task_info = ACTIVE_TASKS[task_id]
    if activate_task_info.get("worker_url") != worker_url:
        return {"status": "stale_discarded"}

    ACTIVE_TASKS.pop(task_id, None)

    # Gửi kết quả cho JobTracker
    if not job_id or job_id not in JOB_TRACKER:
        logging.error(f"Received result for unknown job: {job_id}")
        return {"status": "failed"}

    tracker = JOB_TRACKER[job_id]
    
    tracker["results"].append(result)
    tracker["completed_tasks"] += 1

    if tracker["completed_tasks"] >= tracker["total_tasks"]:
        print(f"[{job_id}] All tasks completed")
        asyncio.create_task(run_reduction_and_cleanup(job_id, db))
        tracker["completion_event"].set()

    return {"status": "success"}


def _register_active_task(task, worker_url, entry_count):
    task_id = task["task_id"]
    ACTIVE_TASKS[task_id] = {
        "worker_url": worker_url,
        "start_time": time.time(),
        "task_data": task,
        "entry_count": entry_count,
        "snooze_count": 0
    }
    return task


async def get_prioritized_task(worker_url: str, cached_key_hint: str | None = None):
    """
    Lấy task theo cơ chế ưu tiên:
    1. Ưu tiên 1: Lấy từ hàng đợi LOCAL
    2. Ưu tiên 2: Lấy từ hàng đợi GLOBAL
    """
    task = None
    # Lấy từ hàng đợi LOCAL
    if cached_key_hint:
        local_queue = None
        async with LOCAL_QUEUE_LOCK:
            local_queue = LOCAL_QUEUES.get(cached_key_hint)
        
        if local_queue:
            try:
                task = local_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

    if task:
        return _register_active_task(task, worker_url, -1)

    # Master sẽ rút task từ Global. Nếu task không khớp cache của worker,
    # Master sẽ "cất" nó vào Local Queue tương ứng thay vì đưa cho worker này.
    while True:
        try:
            priority, entry_count, task = GLOBAL_TASK_QUEUE.get_nowait()
        except asyncio.QueueEmpty:
            break # Global hết task, thoát khỏi vòng lặp
        
        task_cache_key = task.get("cache_key")

        # Trường hợp 1: Worker mới tinh (không có cache) -> Nhận luôn
        if not cached_key_hint:
            return _register_active_task(task, worker_url, entry_count)

        # Trường hợp 2: Worker có cache, và task này khớp -> Nhận luôn
        if cached_key_hint == task_cache_key:
            return _register_active_task(task, worker_url, entry_count)

        # Trường hợp 3: Worker có cache, nhưng task khác cache (MISS)
        else:
            # Cất task này vào hàng đợi Local tương ứng của nó
            local_queue_miss = None
            async with LOCAL_QUEUE_LOCK:
                if task_cache_key not in LOCAL_QUEUES:
                    LOCAL_QUEUES[task_cache_key] = asyncio.Queue()
                local_queue_miss = LOCAL_QUEUES[task_cache_key]
            
            await local_queue_miss.put(task)
            task = None

    if cached_key_hint:
        # Duyệt qua tất cả các Local Queue khác đang có task
        async with LOCAL_QUEUE_LOCK:
            # Lấy danh sách các key để tránh lỗi runtime khi dict thay đổi
            all_keys = list(LOCAL_QUEUES.keys())
        
        for key in all_keys:
            # Bỏ qua queue của chính worker (vì đã check rồi)
            if key == cached_key_hint:
                continue

            target_queue = LOCAL_QUEUES.get(key)
            if target_queue:
                try:
                    # Lấy trộm task từ queue của key khác
                    task = target_queue.get_nowait()
                    print(f"[Master] Fallback: Worker {worker_url} (Hint: {cached_key_hint}) assigned task for new key: {key}")
                    return _register_active_task(task, worker_url, -1)
                except asyncio.QueueEmpty:
                    continue
    
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

                requeue_task = False
                try:
                    # Ping worker để kiểm tra
                    await monitor_client.get(f"{dead_worker_url}/health", timeout=5.0)

                    # Worker vẫn sống (ALIVE but SLOW)
                    snooze_count = task_info.get("snooze_count", 0)

                    if snooze_count < MAX_TASK_SNOOZES:
                        if task_id in ACTIVE_TASKS:
                            ACTIVE_TASKS[task_id]["start_time"] = time.time()
                            ACTIVE_TASKS[task_id]["snooze_count"] = snooze_count + 1
                        requeue_task = False # không thu hồi
                    else:
                        requeue_task = True # thu hồi

                except (httpx.RequestError, httpx.TimeoutException):
                    logging.error(f"[Monitor] Worker {dead_worker_url} is dead. Re-queueing task {task_id}")
                    WORKER_REGISTRY.pop(dead_worker_url, None)
                    requeue_task = True

                if requeue_task:
                    original_entry_count = task_info.get("entry_count", 0)

                    if task_id in ACTIVE_TASKS and ACTIVE_TASKS[task_id].get("worker_url") == dead_worker_url:
                        await GLOBAL_TASK_QUEUE.put((0, original_entry_count, task_info["task_data"]))
                        ACTIVE_TASKS.pop(task_id, None)

                        for w_url, info in WORKER_REGISTRY.items():
                            if info.get("status") == "idle":
                                try:
                                    await monitor_client.get(f"{w_url}/check-for-work", timeout=5.0)
                                    break
                                except Exception as e:
                                    logging.error(f"[Monitor] Failed to wake up replacement worker {w_url}: {e}")
                    else:
                        # Task đã được submit hoặc giao lại cho người khác trong lúc ta đang check
                        logging.warning(f"[Monitor] Task {task_id} was already handled. No action taken.")


# =========================================================================
# FASTAPI APP
# =========================================================================
master = APIRouter()

@master.get("/task/get")
async def api_get_task(cached_key_hint: str | None = None, worker_url: str | None = None):
    if worker_url:
        WORKER_REGISTRY[worker_url] = {
            'status': 'idle'
        }

    task = await get_prioritized_task(worker_url, cached_key_hint)
    if task and worker_url:
        WORKER_REGISTRY[worker_url] = {
            'status': 'working'
        }

    return {"task": task}


@master.post("/task/submit")
async def api_submit_result(result: dict, db: AsyncDatabase = Depends(get_db)):
    status = await handle_task_result_submission(result, db)
    return status