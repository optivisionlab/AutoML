import pickle
import asyncio
import os
import logging
import multiprocessing as mp
import psutil
import numpy as np
import httpx
import time
import uvicorn
from fastapi import FastAPI

from dotenv import load_dotenv
from contextlib import asynccontextmanager

from automl.v2.minio import minIOStorage
from automl.engine import train_process

# Import machine learning models
from cluster import *


# Load file .env
load_dotenv()


"""
CONFIGS & CONSTANTS
"""

# WORKER URL
WORKER_HOST = os.getenv('WORKER_HOST', '0.0.0.0')
WORKER_PORT = int(os.getenv('WORKER_PORT', 8000))
WORKER_URL = f"http://{WORKER_HOST}:{WORKER_PORT}"

# MASTER URL
MASTER_HOST = "[::]" if os.getenv('HOST_BACK_END', '0.0.0.0') == "::" else os.getenv('HOST_BACK_END', '0.0.0.0')
MASTER_PORT = int(os.getenv('PORT_BACK_END', 8080))
MASTER_URL = f"http://{MASTER_HOST}:{MASTER_PORT}"

DEFAULT_CPU_CORES = 2
BYTES_IN_GB = 1024 ** 3


# MAPPING
MODEL_MAPPING = {
    "RandomForestClassifier": RandomForestClassifier,
    "DecisionTreeClassifier": DecisionTreeClassifier,
    "SVC": SVC,
    "KNeighborsClassifier": KNeighborsClassifier,
    "LogisticRegression": LogisticRegression,
    "GaussianNB": GaussianNB,
    "LinearRegression": LinearRegression,
    "DecisionTreeRegressor": DecisionTreeRegressor,
    "RandomForestRegressor": RandomForestRegressor,
    "GradientBoostingRegressor": GradientBoostingRegressor,
    "XGBRegressor": XGBRegressor
}


"""
LRU CACHE
"""
class LRUDatasetCache:
    def __init__(self, max_size=3):
        self.max_size = max_size
        self.cache: dict[str, tuple] = {}
        self.access_order: list[str] = []

    def get_latest_key(self):
        return self.access_order[-1] if self.access_order else None

    async def fetch_and_cache(self, id_data: str, cache_key: str):
        # Hit Cache > Bandwidth equals 1 (no network usage)
        if cache_key in self.cache:
            self.access_order.remove(cache_key)
            self.access_order.append(cache_key)
            return self.cache[cache_key], -1.0

        # Miss Cache > Pull from MinIO and measure bandwidth
        data_cache_path = f"{id_data}/{cache_key}.npz"
        bw_observed = 0.0

        try:
            start_time = time.perf_counter()
            data_buffer = await asyncio.to_thread(minIOStorage.get_object, "cache", data_cache_path)
            download_time = time.perf_counter() - start_time

            file_size_mb = data_buffer.getbuffer().nbytes / (1024 * 1024)
            if download_time > 0:
                bw_observed = file_size_mb / download_time

            with np.load(data_buffer) as cached_data:
                dataset = (cached_data['X'], cached_data['y'])
            data_buffer.close()

        except Exception as e:
            raise Exception(f"Failed to fetch data from MinIO: {str(e)}")

        # Exit old data if it's full
        if len(self.cache) >= self.max_size:
            lru_key = self.access_order.pop(0)
            del self.cache[lru_key]

        self.cache[cache_key] = dataset
        self.access_order.append(cache_key)

        return dataset, bw_observed

dataset_cache = LRUDatasetCache(max_size=3)


"""
SUBPROCESS TRAINING
"""

# Theo dõi subprocess đang chạy để có thể hủy khi cần
_current_process: mp.Process | None = None
_current_task_id: str | None = None


def _training_worker(result_queue: mp.Queue, X, y, metrics, metric_sort,
                     models_to_train, problem_type, search_algorithm, max_time):
    """Hàm chạy trong subprocess để huấn luyện model.
    
    Gọi train_process() và đưa kết quả vào queue để trả về process chính.
    Nếu subprocess bị kill, queue sẽ rỗng → process chính biết task đã bị hủy.
    
    Args:
        result_queue: Queue để trả kết quả về process chính
        X, y: Dữ liệu huấn luyện (numpy arrays)
        metrics: Danh sách metric đánh giá
        metric_sort: Metric chính để chọn model tốt nhất
        models_to_train: Dictionary chứa model và params
        problem_type: 'classification' hoặc 'regression'
        search_algorithm: Thuật toán tìm kiếm hyperparameter
        max_time: Thời gian tối đa (giây), None = không giới hạn
    """
    try:
        best_model_id, best_model_obj, best_score, best_params, model_scores, _ = train_process(
            X, y, metrics, metric_sort, models_to_train, problem_type, search_algorithm, max_time
        )

        model_bytes = pickle.dumps(best_model_obj)
        result_queue.put({
            "success": True,
            "best_model_id": best_model_id,
            "model_bytes": model_bytes,
            "best_score": best_score,
            "best_params": best_params,
            "model_scores": model_scores
        })
    except Exception as e:
        result_queue.put({"success": False, "error": str(e)})


"""
TRAINING EXECUTION
"""
async def execute_training_task(task: dict):
    global _current_process, _current_task_id

    model_info = task["model_info"]
    task_id = task["task_id"]

    try:
        # Tải dữ liệu từ cache hoặc MinIO
        dataset, bw_observed = await dataset_cache.fetch_and_cache(task["id_data"], task["cache_key"])
        X_processed, y_processed = dataset
        
        models_to_train = {
            0: {
                "model": MODEL_MAPPING[model_info["model"]](),
                "params": model_info.get('params') or {}
            }
        }

        # Tạo subprocess để huấn luyện (có thể kill khi cần)
        result_queue = mp.Queue()
        process = mp.Process(
            target=_training_worker,
            args=(
                result_queue, X_processed, y_processed,
                task["metrics"],
                task["config"].get("metric_sort", "accuracy"),
                models_to_train,
                task["config"].get("problem_type", "classification"),
                task["config"].get("search_algorithm", "grid_search"),
                task["config"].get("max_time")
            )
        )

        _current_task_id = task_id
        process.start()
        _current_process = process
        logging.info(f"[Worker] Bắt đầu subprocess (PID={process.pid}) cho task: {task_id}")

        # Chờ subprocess hoàn thành (non-blocking với asyncio)
        while process.is_alive():
            await asyncio.sleep(0.5)

        _current_process = None
        _current_task_id = None
        process.join()

        # Lấy kết quả từ queue (dùng try/except thay vì empty() vì empty() không đáng tin cậy giữa các process)
        try:
            proc_result = result_queue.get_nowait()
        except Exception:
            # Queue rỗng = subprocess bị kill trước khi hoàn thành
            logging.warning(f"[Worker] Subprocess bị hủy cho task: {task_id}")
            return {
                "success": False,
                "job_id": task["job_id"],
                "model_name": model_info["model"],
                "error": "Task đã bị hủy do hết thời gian toàn cục",
                "worker_url": WORKER_URL
            }

        if proc_result["success"]:
            # Upload model lên MinIO
            await asyncio.to_thread(
                minIOStorage.uploaded_object,
                bucket_name="temp",
                object_name=f"{task_id}.pkl",
                object_bytes=proc_result["model_bytes"]
            )

            return {
                "success": True,
                "job_id": task["job_id"],
                "model_name": model_info["model"],
                "score": proc_result["best_score"],
                "scores": proc_result["model_scores"][0]["scores"],
                "best_params": proc_result["best_params"],
                "bandwidth_observed": bw_observed,
                "model": {"bucket_name": "temp", "object_name": f"{task_id}.pkl"},
                "worker_url": WORKER_URL
            }
        else:
            raise Exception(proc_result["error"])

    except Exception as e:
        _current_process = None
        _current_task_id = None
        logging.error(f"[Execution Error] {str(e)}")
        return {
            "success": False,
            "job_id": task["job_id"],
            "model_name": model_info["model"],
            "error": str(e),
            "worker_url": WORKER_URL
        }


"""
POLLING LOOP & APP LIFECYCLE
"""

wake_up_event = asyncio.Event()

async def polling_loop(client: httpx.AsyncClient):
    wake_up_event.set()

    # Get Worker's hardware specifications
    cpu_cores = psutil.cpu_count(logical=False) or DEFAULT_CPU_CORES
    ram_gb = psutil.virtual_memory().total / BYTES_IN_GB

    while True:
        try:
            await wake_up_event.wait()

        except asyncio.CancelledError:
            logging.error(f"[Worker] 'wait()' was cancelled. Worker will be shut down")
            raise
        except Exception as e:
            logging.error(f"[Worker] Error when wake up: {str(e)}")
            await asyncio.sleep(60)
            continue

        try:
            response = await client.get(
                f"{MASTER_URL}/task/get",
                params={
                    "cached_key_hint": dataset_cache.get_latest_key(),
                    "worker_url": WORKER_URL,
                    "cpu_cores": cpu_cores,
                    "ram_gb": ram_gb
                },
                timeout=5.0
            )
            task = response.json().get("task")
            if task:
                print(f"[Worker] Received task. Training")
                start_time = time.perf_counter()
                result = await execute_training_task(task)
                logging.info(f"Task executed in {(time.perf_counter() - start_time):.2f}s")

                await client.post(f"{MASTER_URL}/task/submit", json=result, timeout=10.0)
            else:
                print(f"[Worker] No tasks. Return to sleep")
                wake_up_event.clear()

        except httpx.RequestError as e:
            logging.warning("Cannot connect to Master. Retrying in 30s...")
            await asyncio.sleep(30)
        except Exception as e:
            logging.error(f"Fatal polling error: {e}")
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = httpx.AsyncClient()
    polling_task = asyncio.create_task(polling_loop(client))
    yield
    polling_task.cancel()
    await client.aclose()

app = FastAPI(title="AutoML Worker", lifespan=lifespan)


@app.get("/check-for-work")
async def check_for_work():
    wake_up_event.set()
    return {"status": "starting"}


@app.get("/health")
async def ping():
    return {"status": "OK"}


@app.post("/cancel-task")
async def cancel_task(task_id: str = ""):
    """Master gọi khi job hết thời gian. Worker kill subprocess để giải phóng RAM."""
    global _current_process, _current_task_id

    if _current_process and _current_process.is_alive() and _current_task_id == task_id:
        process = _current_process
        logging.info(f"[Worker] Kill subprocess (PID={process.pid}) cho task: {task_id}")
        process.kill()
        process.join(timeout=5)  # Reap subprocess, tránh zombie process
        _current_process = None
        _current_task_id = None
        return {"status": "killed"}
    else:
        logging.info(f"[Worker] Không tìm thấy subprocess cho task: {task_id}")
        return {"status": "not_found"}


if __name__ == "__main__":
    uvicorn.run("cluster.worker:app", host=WORKER_HOST, port=WORKER_PORT, reload=True)