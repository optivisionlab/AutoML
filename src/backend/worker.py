import pickle
import asyncio
import os
import logging
import yaml
import signal

import httpx
import uvicorn
from fastapi import FastAPI
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
import pandas as pd
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from automl.v2.minio import minIOStorage

from automl.engine import train_process
from database.get_dataset import dataset


# Load file .env
load_dotenv()

# Load file .config.yml
def load_configuration(config_path):
    if not os.path.exists(config_path):
        logging.error("Not found file")
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            return config
    except yaml.YAMLError as e:
        logging.error(f"Invalid file {str(e)}")
        return None
    except Exception as e:
        logging.error(f"Error {str(e)}")
        return None
    
config = load_configuration('.config.yml')


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

async def get_data_with_cache(id_data: str, list_feature: list):
    """
    Quản lý cache
    """
    cache_bucket = "cache"
    data_cache = f"{id_data}.feather"
    
    # Cache HIT
    if id_data in DATASET_CACHE:
        CACHE_ACCESS_ORDER.remove(id_data)
        CACHE_ACCESS_ORDER.append(id_data)
        return DATASET_CACHE[id_data]
    
    try:
        data_buffer = await asyncio.to_thread(
            minIOStorage.get_object,
            cache_bucket,
            data_cache
        )

        data = pd.read_feather(data_buffer)
        features = data.columns.tolist()
    except Exception as e:
        data, features = await asyncio.to_thread(dataset.get_data_and_features, id_data, list_feature)

    # Kiểm tra cache đầy
    if len(DATASET_CACHE) >= MAX_CACHE_SIZE:
        lru_id = CACHE_ACCESS_ORDER.pop(0)
        del DATASET_CACHE[lru_id]

    # Thêm data mới vào cache
    DATASET_CACHE[id_data] = (data, features)
    CACHE_ACCESS_ORDER.append(id_data)

    return data, features


# =========================================================================
# LOGIC THỰC THI TASK
# =========================================================================
async def _execute_single_training_task(task: dict):
    """
    Xử lý huấn luyện với một model
    """
    try:
        id_data = task["id_data"]
        config = task["config"]
        task_id = task["task_id"]
        list_feature = config.get("list_feature")
        search_algorithm = config.get("search_algorithm", "grid_search")

        data, features = await get_data_with_cache(id_data, list_feature)
        model_info = task["model_info"]
        models_to_train = {
            0: {
                "model": MODEL_MAPPING[model_info["model"]](),
                "params": model_info["params"]
            }
        }

        best_model_id, best_model_obj, best_score, best_params, model_scores_list = await asyncio.to_thread(
            train_process,
            data,
            config.get("choose"),
            list_feature,
            config.get("target"),
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
            }
        }
    except Exception as e:
        return {
            "success": False,
            "job_id": task["job_id"],
            "error": str(e)
        }
    

# =========================================================================
# VÒNG LẶP POLLING
# =========================================================================
async def polling_loop(client: httpx.AsyncClient):
    # Lấy ID duy nhất của worker
    master_url = None
    if config is not None:
        try:
            host = config['HOST_BACK_END']
            port = config['PORT_BACK_END']

            if host == "::":
                host = "[::]"

            master_url = f"http://{host}:{port}"
        except KeyError as e:
            logging.error(f"Missing important configuration in .config.yml: {str(e)}")
        except TypeError as e:
            logging.error(f"Configuration value is not valid {str(e)}")

    if not master_url:
        logging.critical("Master URL does not exist. Worker will be shut down")
        os.kill(os.getpid(), signal.SIGTERM)
        return

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
            # Lấy id data dùng gần nhất
            cached_hint = CACHE_ACCESS_ORDER[-1] if CACHE_ACCESS_ORDER else None

            worker_url = os.getenv('WORKER_URL')
            if not worker_url:
                logging.error("Error: Missing 'WORKER_URL'. Worker will be shut down")
                os.kill(os.getpid(), signal.SIGTERM)
                return


            # Gọi API "GET TASK" của Master
            response = await client.get(
                f"{master_url}/task/get",
                params={
                    "cached_id_data": cached_hint,
                    "worker_url": worker_url
                },
                timeout=5.0
            )
            task = response.json().get("task")

            if task:
                print(f"[Worker] Received task. Training")
                result = await _execute_single_training_task(task)
                await client.post(f"{master_url}/task/submit", json=result)
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


WORKER_HOST = os.getenv('WORKER_HOST', '0.0.0.0')
WORKER_PORT = int(os.getenv('WORKER_PORT', 8000)) 

if __name__ == "__main__":
    uvicorn.run("worker:app", host=WORKER_HOST, port=WORKER_PORT, reload=True)