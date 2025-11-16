import pickle
import asyncio
import os
import logging
import signal
import numpy as np
import httpx
import time
import uvicorn
from fastapi import FastAPI
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from automl.v2.minio import minIOStorage
from automl.engine import train_process


# Load file .env
load_dotenv()


# WORKER URL
WORKER_HOST = os.getenv('WORKER_HOST', '0.0.0.0')
WORKER_PORT = int(os.getenv('WORKER_PORT', 8000))

# MASTER URL
MASTER_HOST = os.getenv('HOST_BACK_END', '0.0.0.0')
MASTER_PORT = int(os.getenv('PORT_BACK_END', 8080))


# ÁNH XẠ MÔ HÌNH
MODEL_MAPPING = {
    "RandomForestClassifier": RandomForestClassifier,
    "DecisionTreeClassifier": DecisionTreeClassifier,
    "SVC": SVC,
    "KNeighborsClassifier": KNeighborsClassifier,
    "LogisticRegression": LogisticRegression,
    "GaussianNB": GaussianNB
}


# =========================================================================
# QUẢN LÝ CACHE (LRU)
# =========================================================================
# Giới hạn cache chứa tối đa 3 bộ dữ liệu
MAX_CACHE_SIZE = 3
DATASET_CACHE = {}
# Dùng list để theo dõi thứ tự truy cập
CACHE_ACCESS_ORDER = []

POLLING_CLIENT = None
WAKE_UP_EVENT = asyncio.Event()

async def get_data_with_cache(id_data: str, cache_key: str):
    """
    Quản lý cache
    """
    
    # Cache HIT
    if cache_key in DATASET_CACHE:
        CACHE_ACCESS_ORDER.remove(cache_key)
        CACHE_ACCESS_ORDER.append(cache_key)
        return DATASET_CACHE[cache_key]
    
    cache_bucket = "cache"
    data_cache = f"{id_data}/{cache_key}.npz"

    try:
        data_buffer = await asyncio.to_thread(
            minIOStorage.get_object,
            cache_bucket,
            data_cache
        )

        with np.load(data_buffer) as cached_data:
            X_processed = cached_data['X']
            y_processed = cached_data['y']
        data_buffer.close()

    except Exception as e:
        raise Exception(f"Cache not found for {str(e)}")

    # Kiểm tra cache đầy
    if len(DATASET_CACHE) >= MAX_CACHE_SIZE:
        lru_id = CACHE_ACCESS_ORDER.pop(0)
        del DATASET_CACHE[lru_id]

    # Thêm data mới vào cache
    DATASET_CACHE[cache_key] = (X_processed, y_processed)
    CACHE_ACCESS_ORDER.append(cache_key)

    return DATASET_CACHE[cache_key]


# =========================================================================
# LOGIC THỰC THI TASK
# =========================================================================
async def _execute_single_training_task(task: dict):
    """
    Xử lý huấn luyện với một model
    """
    try:
        id_data = task["id_data"]
        cache_key = task["cache_key"]
        config = task["config"]
        task_id = task["task_id"]
        search_algorithm = config.get("search_algorithm", "grid_search")

        X_processed, y_processed = await get_data_with_cache(id_data, cache_key)
        model_info = task["model_info"]
        model_params = model_info.get('params') or {}
        models_to_train = {
            0: {
                "model": MODEL_MAPPING[model_info["model"]](),
                "params": model_params
            }
        }

        best_model_id, best_model_obj, best_score, best_params, model_scores_list = await asyncio.to_thread(
            train_process,
            X_processed,
            y_processed,
            task["metrics"],
            config.get("metric_sort"),
            models_to_train,
            search_algorithm
        )

        model_bytes = pickle.dumps(best_model_obj)

        # Lưu vào bộ nhớ tạm thay vì chuyển bằng JSON
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
            "scores": model_scores_list[0]["scores"],
            "best_params": best_params,
            "model": {
                "bucket_name": "temp",
                "object_name": f"{task_id}.pkl"
            },
            "worker_url": f"http://{WORKER_HOST}:{WORKER_PORT}"
        }
    except Exception as e:
        return {
            "success": False,
            "job_id": task["job_id"],
            "model_name": model_info["model"],
            "error": str(e),
            "worker_url": f"http://{WORKER_HOST}:{WORKER_PORT}"
        }
    

# =========================================================================
# VÒNG LẶP POLLING
# =========================================================================
async def polling_loop(client: httpx.AsyncClient):
    # Lấy ID duy nhất của worker
    master_host_addr = MASTER_HOST
    if MASTER_HOST == "::":
        master_host_addr = "[::]"

    master_url = f"http://{master_host_addr}:{MASTER_PORT}"

    
    if not master_url:
        logging.critical("Master URL does not exist. Worker will be shut down")
        os.kill(os.getpid(), signal.SIGTERM)
        return
    
    WAKE_UP_EVENT.set()
    
    while True:
        try:
            await WAKE_UP_EVENT.wait()

        except asyncio.CancelledError:
            print(f"[Worker] 'wait()' was cancelled. Worker will be shut down")
            raise
        except Exception as e:
            logging.error(f"[Worker] Error when wake up: {str(e)}")
            await asyncio.sleep(60)
            continue


        try:
            # Lấy cache key dùng gần nhất
            cached_hint = CACHE_ACCESS_ORDER[-1] if CACHE_ACCESS_ORDER else None

            worker_url = f"http://{WORKER_HOST}:{WORKER_PORT}"

            # Gọi API "GET TASK" của Master
            response = await client.get(
                f"{master_url}/task/get",
                params={
                    "cached_key_hint": cached_hint,
                    "worker_url": worker_url
                },
                timeout=5.0
            )
            task = response.json().get("task")
            if task:
                print(f"[Worker] Received task. Training")
                start = time.perf_counter()
                result = await _execute_single_training_task(task)
                print(f"[Worker] Time: {(time.perf_counter() - start):.2f} seconds")

                await client.post(f"{master_url}/task/submit", json=result, timeout=10.0)
            else:
                print(f"[Worker] No tasks. Return to sleep")
                WAKE_UP_EVENT.clear()

        except httpx.RequestError as e:
            print(f"[Worker] Cannot connect to Master")
            await asyncio.sleep(30)
            continue
        except Exception as e:
            print(f"[Worker] Fatal error while retrieving task: {e}. Retrying...")
            await asyncio.sleep(60)
            continue


# =========================================================================
# FASTAPI APP
# =========================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global POLLING_CLIENT
    POLLING_CLIENT = httpx.AsyncClient()
    polling_task = asyncio.create_task(polling_loop(POLLING_CLIENT))
    yield
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        print("Polling Task confirmed cancelled")
    except Exception as e:
        logging.error(f"Polling Task reports error when shutting down: {str(e)}")
    finally:
        if POLLING_CLIENT:
            await POLLING_CLIENT.aclose()



app = FastAPI(title="Worker", lifespan=lifespan)

@app.get("/check-for-work")
async def check_for_work():
    WAKE_UP_EVENT.set()
    return {"status": "starting"}


@app.get("/health")
async def ping():
    return {"status": "OK"}


if __name__ == "__main__":
    uvicorn.run("worker:app", host=WORKER_HOST, port=WORKER_PORT, reload=True)