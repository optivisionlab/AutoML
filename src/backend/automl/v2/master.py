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


"""
CONFIGS & CONSTANTS
"""

# -- Worker Config --
NUMBER_WORKERS = int(os.getenv("NUMBER_WORKERS", 1))
WORKER_LIST_STR = os.getenv("WORKER_LIST", "")
WORKERS = [worker_url.strip() for worker_url in WORKER_LIST_STR.split(",")] if WORKER_LIST_STR else []

# -- Network Sensing --
DEFAULT_BANDWIDTH_MBPS = float(os.getenv("DEFAULT_BANDWIDTH_MBPS", 100.0))
EMA_SMOOTHING_FACTOR = 0.3
NETWORK_COST_LIMIT_SECONDS = float(os.getenv("NETWORK_TIMEOUT_LIMIT", 5.0))

# -- Fault Tolerance --
TASK_TIMEOUT_SECONDS = int(os.getenv("TASK_TIMEOUT_SECONDS", 3600))
MAX_SNOOZE_LIMIT = int(os.getenv("MAX_TASK_SNOOZES", 1))
MAX_RETRIES_PER_TASK = int(os.getenv("MAX_TASK_RETRIES", 3))

# -- Capacity Aware --
HEAVY_MODELS = {"RandomForestClassifier", "RandomForestRegressor", "XGBRegressor", "GradientBoostingRegressor", "SVC"}
T_CPU = 8
T_RAM_GB = 16.0

"""
SYSTEM STATE
"""
class SystemState:
    def __init__(self):
        self.current_bandwidth_mbps = DEFAULT_BANDWIDTH_MBPS
        self.network_lock = asyncio.Lock()

        # Capacity-Aware Queues
        self.heavy_task_queue = asyncio.PriorityQueue()
        self.light_task_queue = asyncio.PriorityQueue()

        self.local_queues: dict[str, asyncio.Queue] = {}
        self.local_queue_lock = asyncio.Lock()

        # Lifecycle management
        self.job_tracker: dict[str, dict] = {}
        self.active_tasks: dict[str, dict] = {}
        self.worker_registry: dict[str, dict] = {}
        self.task_counter = itertools.count()

state = SystemState()


"""
HELPER FUNCTIONS
"""

def get_models(problem_type: str):
    file_name = "classification.yml" if problem_type == "classification" else "regression.yml"
    file_path = os.path.join("assets/system_models", file_name)

    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    models = {}

    for key, model_info in data[f"{problem_type.capitalize()}_models"].items():
        models[key] = {
            "model": model_info["model"],
            "params": model_info.get("params") or [{}]
        }
    return models, data.get("metric_list", [])


def get_config_hash(id_data: str, list_feature: list, target: str, problem_type: str) -> str:
    sorted_features = sorted(list_feature)
    key_string = f"{id_data}-{json.dumps(sorted_features)}-{target}-{problem_type}"
    return hashlib.md5(key_string.encode("utf-8")).hexdigest()


"""
JOB SETUP & REDUCTION
"""
async def setup_job_tasks(job_id: str, id_data: str, id_user: str, config: dict, cache_key: str, db: AsyncDatabase = None):
    """Tạo các task huấn luyện và đưa vào hàng đợi ưu tiên.
    
    Args:
        job_id: ID của job
        id_data: ID của dataset
        id_user: ID của người dùng
        config: Cấu hình huấn luyện (chứa max_time, problem_type, ...)
        cache_key: Khóa cache cho dataset
        db: Kết nối database (cần cho timeout watcher)
    """
    was_queue_empty = (state.heavy_task_queue.empty() and state.light_task_queue.empty())
    models, metric_list = await asyncio.to_thread(get_models, config.get("problem_type", "classification"))

    state.job_tracker[job_id] = {
        "total_tasks": len(models),
        "completed_tasks": 0,
        "results": [],
        "completion_event": asyncio.Event(),
        "config": config,
        "id_user": id_user,
        # Thông tin quản lý thời gian toàn cục
        "start_time": time.time(),
        "max_time": config.get("max_time", 3600),
        "timed_out": False,
        "timeout_watcher_task": None
    }

    tasks_added = 0
    for model_id, model_info in models.items():
        is_heavy = model_info["model"] in HEAVY_MODELS
        task = {
            "task_id": f"{job_id}_{model_info['model']}",
            "job_id": job_id,
            "id_data": id_data,
            "config": config,
            "model_info": model_info,
            "metrics": metric_list,
            "cache_key": cache_key,
            "is_heavy": is_heavy
        }
        entry_count = next(state.task_counter)

        if is_heavy:
            await state.heavy_task_queue.put((1, entry_count, task))
        else:
            await state.light_task_queue.put((1, entry_count, task))

        tasks_added += 1

    # Gửi tín hiệu cho worker bắt đầu làm việc
    if was_queue_empty and tasks_added > 0:
        async with httpx.AsyncClient() as client:
            signal_tasks = [
                client.get(f"{worker}/check-for-work", timeout=5.0)
                for worker in WORKERS
            ]
            results = await asyncio.gather(*signal_tasks, return_exceptions=True)
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    logging.warning(f"[{job_id}] Không gửi được tín hiệu đến worker {WORKERS[i]}: {res}")

    # Khởi tạo timeout watcher nếu có giới hạn thời gian
    # NOTE: max_time ở đây là ngân sách thời gian TOÀN CỤC cho job.
    # - Job-level: _job_timeout_watcher dùng max_time làm hard deadline để kill job.
    # - Task-level: _register_active_task() tính remaining_time = max_time - elapsed
    #   và ghi đè vào task["config"]["max_time"], nên worker nhận đúng thời gian còn lại.
    # - Khác với local path (engine.py), nơi các model chạy TUẦN TỰ và
    #   _check_global_time_budget() giảm dần thời gian cho mỗi model.
    max_time = config.get("max_time")
    if max_time is not None and db is not None:
        watcher_task = asyncio.create_task(
            _job_timeout_watcher(job_id, max_time, db)
        )
        state.job_tracker[job_id]["timeout_watcher_task"] = watcher_task
        logging.info(f"[{job_id}] Đã khởi tạo timeout watcher toàn cục: {max_time}s")


async def _job_timeout_watcher(job_id: str, max_time: float, db: AsyncDatabase):
    """Background task giám sát thời gian toàn cục của job.
    
    Chờ completion_event hoặc hết max_time (cái nào đến trước).
    Nếu hết thời gian mà job chưa xong → hủy các task đang chờ,
    trigger early reduction với kết quả hiện có.
    
    Args:
        job_id: ID của job cần giám sát
        max_time: Thời gian tối đa (giây)
        db: Kết nối database để cập nhật trạng thái job
    """
    tracker = state.job_tracker.get(job_id)
    if not tracker:
        return

    try:
        # Chờ job hoàn thành HOẶC hết thời gian (chọn cái nào đến trước)
        await asyncio.wait_for(
            tracker["completion_event"].wait(),
            timeout=max_time
        )
        # Job hoàn thành trước timeout → không cần xử lý gì thêm
        logging.info(f"[{job_id}] Job hoàn thành trong giới hạn thời gian ({max_time}s)")

    except asyncio.TimeoutError:
        # TIMEOUT: Job chưa hoàn thành
        completed = tracker['completed_tasks']
        total = tracker['total_tasks']
        logging.warning(
            f"[{job_id}] Hết thời gian toàn cục ({max_time}s). "
            f"Đã hoàn thành: {completed}/{total} model"
        )

        # Đánh dấu job đã hết thời gian
        tracker["timed_out"] = True

        # Thu thập thông tin worker trước khi xóa active_tasks
        # Snapshot để tránh RuntimeError khi dict bị mutate bởi coroutine khác
        tasks_to_cancel = [
            (tid, info["worker_url"], info["task_data"]["job_id"])
            for tid, info in list(state.active_tasks.items())
            if info["task_data"]["job_id"] == job_id
        ]

        # Xóa khỏi active_tasks
        for task_id, _, _ in tasks_to_cancel:
            state.active_tasks.pop(task_id, None)
            logging.info(f"[{job_id}] Đã hủy task đang chạy: {task_id}")

        # Gửi tín hiệu cancel đến worker để kill subprocess
        async with httpx.AsyncClient() as cancel_client:
            for task_id, worker_url, _ in tasks_to_cancel:
                if worker_url:
                    try:
                        await cancel_client.post(
                            f"{worker_url}/cancel-task",
                            params={"task_id": task_id},
                            timeout=5.0
                        )
                        logging.info(f"[{job_id}] Đã gửi cancel đến {worker_url} cho task {task_id}")
                    except Exception as e:
                        logging.warning(f"[{job_id}] Không gửi được cancel đến {worker_url}: {e}")

        # Trigger early reduction chỉ khi có ít nhất 1 kết quả THÀNH CÔNG
        # (completed_tasks đếm cả failures, không dùng được để quyết định reduction)
        successful_count = len([r for r in tracker['results'] if r.get('success')])
        if successful_count > 0 and not tracker.get("reduction_scheduled"):
            tracker["reduction_scheduled"] = True
            logging.info(f"[{job_id}] Tiến hành tổng hợp sớm với {successful_count}/{total} kết quả thành công")
            asyncio.create_task(run_reduction_and_cleanup(job_id, db))
        else:
            # Không có kết quả thành công nào → đánh dấu lỗi
            job_update = MongoJob(db)
            await job_update.update_failure(
                job_id,
                f"Hết thời gian toàn cục ({max_time}s): không có model nào hoàn thành thành công"
            )
            state.job_tracker.pop(job_id, None)
            logging.error(f"[{job_id}] Không có kết quả thành công nào trước khi hết thời gian")

    except asyncio.CancelledError:
        # Watcher bị hủy (job hoàn thành bình thường trước timeout)
        pass


ERROR_METRICS = {'mse', 'mae', 'mape', 'rmse', 'log_loss'}
MACRO_WEIGHTED_METRICS = {'f1', 'recall', 'precision'}

async def reduce_results_for_job(job_id: str, db: AsyncDatabase):
    # Aggregates final results for a job
    job_update = MongoJob(db)
    tracker = state.job_tracker[job_id]

    valid_results = [r for r in tracker["results"] if r.get("success")]
    if not valid_results:
        raise ValueError("No successful results from workers")

    final_model_scores = []
    for i, result in enumerate(valid_results):
        score_entry = {
            "model_id": i,
            "model_name": result.get("model_name", ""),
            "scores": result.get("scores"),
            "best_params": result.get("best_params") or {}
        }
        final_model_scores.append(score_entry)

    # Select best model logic
    metric_sort = tracker["config"].get("metric_sort", "")
    metric_sort = metric_sort.strip().lower().replace(" ", "_")

    if metric_sort in ERROR_METRICS:
        # REGRESSION -> Find MIN
        best_model_info = min(
            final_model_scores,
            key=lambda x: x["scores"].get(metric_sort) if x["scores"].get(metric_sort) is not None else float("inf")
        )
    else:
        # CLASSIFICATION -> Find MAX
        best_model_info = max(
            final_model_scores,
            key=lambda x: x["scores"].get(metric_sort) if x["scores"].get(metric_sort) is not None else -float("inf")
        )

    original_best_result = next(
        r for r in valid_results if r["model_name"] == best_model_info["model_name"]
    )

    try:
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
            "model_scores": final_model_scores,
            # Thông tin giới hạn thời gian
            "time_limit_reached": tracker.get("timed_out", False),
            "completed_models": tracker["completed_tasks"],
            "total_models": tracker["total_tasks"]
        }

        await job_update.update_success(job_id, final_result_payload)
        return True

    except Exception as e:
        error_msg = f"Update failure: {str(e)}"
        await job_update.update_failure(job_id, error_msg)
        raise Exception(f"{error_msg}")


async def run_reduction_and_cleanup(job_id: str, db: AsyncDatabase):
    # Runs reduction and cleans up the job in a background task
    job_update = MongoJob(db)

    if job_id not in state.job_tracker:
        logging.warning(f"[{job_id}] Job tracker not found for cleanup.")
        return

    try:
        await reduce_results_for_job(job_id, db)
        print(f"[{job_id}] Reduction successful")
    except Exception as e:
        await job_update.update_failure(job_id, f"Reduction failed: {str(e)}")
    finally:
        state.job_tracker.pop(job_id, None)


"""
SCHEDULER & FAULT TOLERANCE
"""

def _is_task_from_timed_out_job(task: dict) -> bool:
    """Kiểm tra task có nên bị bỏ qua không (job đã hết thời gian hoặc đã hoàn thành).
    
    Trả về True trong 2 trường hợp:
    1. Job đã bị đánh dấu timed_out (hết thời gian toàn cục)
    2. Job không còn trong job_tracker (đã hoàn thành và dọn dẹp)
    
    Args:
        task: Thông tin task chứa job_id
    
    Returns:
        True nếu task nên bị bỏ qua, False nếu vẫn hợp lệ
    """
    task_job_id = task.get("job_id")
    # Job đã bị xóa khỏi tracker → đã hoàn thành hoặc thất bại → bỏ qua
    if task_job_id not in state.job_tracker:
        return True
    return state.job_tracker[task_job_id].get("timed_out", False)


async def get_prioritized_task(worker_url: str, cached_key_hint: str | None = None, worker_cpu: int = 4, worker_ram: float = 8.0):
    """
    Algorithm: Prioritize scheduling based on Locality and Network Cost
    """
    # Data Locality
    if cached_key_hint:
        async with state.local_queue_lock:
            local_queue = state.local_queues.get(cached_key_hint)
        while local_queue and not local_queue.empty():
            task = local_queue.get_nowait()
            # Bỏ qua task thuộc job đã hết thời gian, thử task tiếp theo
            if _is_task_from_timed_out_job(task):
                continue
            return _register_active_task(task, worker_url, -1)

    # Capacity-Aware Routing
    is_strong = (worker_cpu >= T_CPU) and (worker_ram >= T_RAM_GB)
    while not state.heavy_task_queue.empty() or not state.light_task_queue.empty():
        task = None
        entry_count = -1

        if is_strong:
            if not state.heavy_task_queue.empty():
                priority, entry_count, task = state.heavy_task_queue.get_nowait()
            elif not state.light_task_queue.empty():
                priority, entry_count, task = state.light_task_queue.get_nowait()
        else:
            if not state.light_task_queue.empty():
                priority, entry_count, task = state.light_task_queue.get_nowait()
            elif not state.heavy_task_queue.empty():
                priority, entry_count, task = state.heavy_task_queue.get_nowait()

        if not task:
            break

        # Bỏ qua task thuộc job đã hết thời gian
        if _is_task_from_timed_out_job(task):
            continue

        # Cost-Based Validation
        task_cache_key = task.get("cache_key")
        data_size_mb = task.get("config", {}).get("estimated_size_md", 50.0)
        network_cost = data_size_mb / max(state.current_bandwidth_mbps, 1.0)

        if cached_key_hint != task_cache_key and network_cost > NETWORK_COST_LIMIT_SECONDS:
            async with state.local_queue_lock:
                if task_cache_key not in state.local_queues:
                    state.local_queues[task_cache_key] = asyncio.Queue()
                await state.local_queues[task_cache_key].put(task)

            continue

        return _register_active_task(task, worker_url, entry_count)

    # Work Stealing
    if cached_key_hint:
        async with state.local_queue_lock:
            all_keys = list(state.local_queues.keys())

        for key in all_keys:
            if key == cached_key_hint:
                continue

            target_queue = state.local_queues.get(key)
            while target_queue and not target_queue.empty():
                task = target_queue.get_nowait()
                # Bỏ qua task thuộc job đã hết thời gian, thử task tiếp theo
                if _is_task_from_timed_out_job(task):
                    continue
                return _register_active_task(task, worker_url, -1)

    return None


def _register_active_task(task, worker_url, entry_count):
    task_id = task["task_id"]
    job_id = task.get("job_id")

    # Tính remaining time từ job tracker và ghi đè max_time
    # Để worker nhận đúng thời gian còn lại thay vì full max_time gốc
    tracker = state.job_tracker.get(job_id)
    if tracker and tracker.get("max_time") is not None:
        elapsed = time.time() - tracker["start_time"]
        remaining = max(0, tracker["max_time"] - elapsed)
        task["config"]["max_time"] = remaining

    state.active_tasks[task_id] = {
        "worker_url": worker_url,
        "start_time": time.time(),
        "task_data": task,
        "entry_count": entry_count,
        "snooze_count": 0,
        "retry_count": task.get("retry_count", 0)
    }
    return task


async def monitor_tasks(db: AsyncDatabase | None = None):
    """
    Algorithm: Circuit Breaker & Fault Recovery
    """
    if db is None:
        logging.error(
            "monitor_tasks started without a database handle; job_tracker cleanup and "
            "reduction scheduling cannot be performed. This is a misconfiguration."
        )
        raise ValueError("monitor_tasks requires a valid AsyncDatabase instance")
    async with httpx.AsyncClient() as monitor_client:
        while True:
            await asyncio.sleep(TASK_TIMEOUT_SECONDS)
            current_time = time.time()
            frozen_tasks = list(state.active_tasks.items())

            for task_id, task_info in frozen_tasks:
                if (current_time - task_info["start_time"]) <= TASK_TIMEOUT_SECONDS:
                    continue

                dead_worker_url = task_info.get("worker_url")
                if not dead_worker_url:
                    continue

                requeue_task = False

                try:
                    await monitor_client.get(f"{dead_worker_url}/health", timeout=5.0)
                    # The worker is alive but running slowly
                    if task_info.get("snooze_count", 0) < MAX_SNOOZE_LIMIT:
                        state.active_tasks[task_id]["start_time"] = time.time()
                        state.active_tasks[task_id]["snooze_count"] += 1
                    else:
                        requeue_task = True
                except (httpx.RequestError, httpx.TimeoutError):
                    # Worker is dead
                    state.worker_registry.pop(dead_worker_url, None)
                    requeue_task = True

                if requeue_task:
                    await _handle_failed_task(task_id, task_info, dead_worker_url, monitor_client, db)


async def _handle_failed_task(task_id, task_info, dead_worker_url, monitor_client, db: AsyncDatabase = None):
    # Handle interruptions when a task fails multiple times
    task_data = task_info["task_data"]
    current_retries = task_info.get("retry_count", 0) + 1

    if current_retries > MAX_RETRIES_PER_TASK:
        job_id = task_data["job_id"]
        state.active_tasks.pop(task_id, None)

        # Chỉ đánh dấu TASK này fail, không xóa toàn bộ job
        tracker = state.job_tracker.get(job_id)
        if tracker:
            tracker["completed_tasks"] += 1
            tracker["results"].append({
                "model_name": task_data.get("model_info", {}).get("model", "unknown"),
                "success": False,
                "error": f"Exceeded max retries ({MAX_RETRIES_PER_TASK})"
            })
            logging.warning(
                f"[{job_id}] Task {task_id} vượt quá {MAX_RETRIES_PER_TASK} lần retry, đánh dấu failed. "
                f"Tiến độ: {tracker['completed_tasks']}/{tracker['total_tasks']}"
            )
            # Nếu đây là task cuối → trigger reduction & cleanup giống api_submit_result
            if tracker["completed_tasks"] >= tracker["total_tasks"]:
                completion_event = tracker.get("completion_event")
                if completion_event is not None and not completion_event.is_set():
                    completion_event.set()

                # Hủy timeout watcher nếu còn đang chạy
                timeout_task = tracker.get("timeout_watcher_task")
                if timeout_task is not None and not timeout_task.done():
                    timeout_task.cancel()

                # Đảm bảo reduction/cleanup chỉ được schedule 1 lần
                if db is not None and not tracker.get("reduction_scheduled"):
                    tracker["reduction_scheduled"] = True
                    asyncio.create_task(run_reduction_and_cleanup(job_id, db))
                elif db is None:
                    # db == None ở đây nghĩa là không thể chạy reduction/cleanup như bình thường.
                    # Để tránh job bị kẹt trong bộ nhớ, log lỗi và dọn entry trong job_tracker.
                    logging.error(
                        "[%s] Không thể schedule reduction/cleanup vì db=None sau khi task %s vượt quá số lần retry.",
                        job_id,
                        task_id,
                    )
                    state.job_tracker.pop(job_id, None)
        return

    # Classified Re-queueing
    task_data["retry_count"] = current_retries
    if task_id in state.active_tasks and state.active_tasks[task_id].get("worker_url") == dead_worker_url:
        entry_count = task_info.get("entry_count", 0)

        if task_data.get("is_heavy"):
            await state.heavy_task_queue.put((0, entry_count, task_data))
        else:
            await state.light_task_queue.put((0, entry_count, task_data))
            
        state.active_tasks.pop(task_id, None)

        # Wake up the other worker
        for w_url, info in state.worker_registry.items():
            if info.get("status") == "idle":
                try:
                    await monitor_client.get(f"{w_url}/check-for-work", timeout=5.0)
                    break
                except Exception:
                    pass


"""
API ENDPOINTS & JOB REDUCTION
"""

master = APIRouter()


@master.get("/task/get")
async def api_get_task(cached_key_hint: str | None = None, worker_url: str | None = None, cpu_cores: int = 4, ram_gb: float = 8.0):
    if worker_url:
        state.worker_registry[worker_url] = {"status": "idle", "cpu": cpu_cores, "ram": ram_gb}

    task = await get_prioritized_task(worker_url, cached_key_hint, cpu_cores, ram_gb)

    if task and worker_url:
        state.worker_registry[worker_url]["status"] = "working"

    return {"task": task}


@master.post("/task/submit")
async def api_submit_result(result: dict, db: AsyncDatabase = Depends(get_db)):
    job_id = result.get("job_id")
    model_name = result.get("model_name")
    worker_url = result.get("worker_url")
    bw_feedback = result.get("bandwidth_observed")

    """
    Algorithm: Adaptive Network Feedback
    """
    if bw_feedback and bw_feedback > 0:
        async with state.network_lock:
            state.current_bandwidth_mbps = (1 - EMA_SMOOTHING_FACTOR) * state.current_bandwidth_mbps + EMA_SMOOTHING_FACTOR * bw_feedback

    task_id = f"{job_id}_{model_name}"

    # Kiểm tra job đã hết thời gian → loại bỏ kết quả đến muộn
    tracker = state.job_tracker.get(job_id)
    if tracker and tracker.get("timed_out"):
        logging.info(f"[{job_id}] Loại bỏ kết quả đến muộn từ {worker_url} (job đã hết thời gian)")
        return {"status": "timed_out_discarded"}

    if task_id not in state.active_tasks or state.active_tasks[task_id].get("worker_url") != worker_url:
        return {"status": "stale_discarded"}

    state.active_tasks.pop(task_id, None)

    if job_id not in state.job_tracker:
        return {"status": "failed"}

    tracker = state.job_tracker[job_id]
    tracker["results"].append(result)
    tracker["completed_tasks"] += 1

    if (tracker["completed_tasks"] >= tracker["total_tasks"]):
        # Hủy timeout watcher nếu job hoàn thành bình thường
        watcher = tracker.get("timeout_watcher_task")
        if watcher and not watcher.done():
            watcher.cancel()
        # Đảm bảo reduction/cleanup chỉ được schedule 1 lần
        if not tracker.get("reduction_scheduled"):
            tracker["reduction_scheduled"] = True
            asyncio.create_task(run_reduction_and_cleanup(job_id, db))
        tracker["completion_event"].set()

    return {"status": "success"}
