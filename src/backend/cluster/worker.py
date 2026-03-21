import pickle
import asyncio
import os
import logging
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
TRAINING EXECUTION
"""
async def execute_training_task(task: dict):
    model_info = task["model_info"]
    task_id = task["task_id"]

    try:
        # Data acquisition & network measurement
        dataset, bw_observed = await dataset_cache.fetch_and_cache(task["id_data"], task["cache_key"])
        X_processed, y_processed = dataset
        
        models_to_train = {
            0: {
                "model": MODEL_MAPPING[model_info["model"]](),
                "params": model_info.get('params') or {}
            }
        }

        _, best_model_obj, best_score, best_params, model_scores, time_limit_reached = await asyncio.to_thread(
            train_process,
            X_processed,
            y_processed,
            task["metrics"],
            task["config"].get("metric_sort", "accuracy"),
            models_to_train,
            task["config"].get("problem_type", 'classification'),
            task["config"].get("search_algorithm", "grid_search"),
            task["config"].get("max_time") # minutes
        )

        model_bytes = pickle.dumps(best_model_obj)
        await asyncio.to_thread(
            minIOStorage.uploaded_object,
            bucket_name="temp",
            object_name=f"{task_id}.pkl",
            object_bytes=model_bytes
        )

        return {
            "success": True,
            "job_id": task["job_id"],
            "model_name": model_info["model"],
            "score": best_score,
            "scores": model_scores[0]["scores"],
            "best_params": best_params,
            "bandwidth_observed": bw_observed, 
            "model": {"bucket_name": "temp", "object_name": f"{task_id}.pkl"},
            "worker_url": WORKER_URL,
            "time_limit_reached": time_limit_reached
        }

    except Exception as e:
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
    """Master gửi tín hiệu khi job hết thời gian. Worker ghi log nhưng không ngắt training."""
    logging.info(f"[Worker] Nhận tín hiệu hủy cho task: {task_id}")
    return {"status": "acknowledged"}


if __name__ == "__main__":
    uvicorn.run("cluster.worker:app", host=WORKER_HOST, port=WORKER_PORT, reload=True)