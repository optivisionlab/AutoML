import pickle
import base64
import asyncio
import os

import httpx
from fastapi import FastAPI, Request
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from automl.engine import train_process
from database.get_dataset import dataset


load_dotenv()

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
    Nếu cache HIT, trả về data
    Nếu cache MISS, tải data, lưu vào cache, và xóa data cũ nhất nếu cần
    """
    # Cache HIT
    if id_data in DATASET_CACHE:
        CACHE_ACCESS_ORDER.remove(id_data)
        CACHE_ACCESS_ORDER.append(id_data)
        return DATASET_CACHE[id_data]
    
    # Cache MISS
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
        list_feature = config.get("list_feature")

        data, features = await get_data_with_cache(id_data, list_feature)
        model_info = task["model_info"]
        models_to_train = {
            0: {
                "model": MODEL_MAPPING[model_info["model"]](),
                "params": model_info["params"]
            }
        }

        print("training...")
        best_model_id, best_model_obj, best_score, best_params, model_scores_list = await asyncio.to_thread(
            train_process,
            data,
            config.get("choose"),
            list_feature,
            config.get("target"),
            task["metrics"],
            config.get("metric_sort"),
            models_to_train
        )

        model_bytes = pickle.dumps(best_model_obj)
        model_base64 = base64.b64encode(model_bytes).decode("utf-8")

        return {
            "success": True,
            "job_id": task["job_id"],
            "model_name": model_info["model"],
            "score": best_score,
            "scores": model_scores_list[0]["scores"],
            "best_params": best_params,
            "model_base64": model_base64
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
    master_url = f"http://{os.getenv('HOST_BACK_END', '0.0.0.0')}:{int(os.getenv('PORT_BACK_END', 8000))}"
    while True:
        try:
            # Lấy id data dùng gần nhất
            cached_hint = CACHE_ACCESS_ORDER[-1] if CACHE_ACCESS_ORDER else None

            # Gọi API "GET TASK" của Master
            response = await client.get(
                f"{master_url}/task/get",
                params={
                    "cached_id_data": cached_hint,
                    "worker_url": f"http://{os.getenv('WORKER_HOST', '0.0.0.0')}:{int(os.getenv('WORKER_BASE_PORT', 4000))}"
                },
                timeout=10.0
            )
            task = response.json().get("task")

            if task:
                result = await _execute_single_training_task(task)
                await client.post(f"{master_url}/task/submit", json=result)
            else:
                WAKE_UP_EVENT.clear()
                # DATASET_CACHE.clear() # sẽ mất thời gian load dataset nếu là dataset đang dùng.
                await asyncio.wait_for(WAKE_UP_EVENT.wait(), timeout=180)

        except httpx.RequestError as e:
            print(f"[Worker] Cannot connect to Master")
            await asyncio.sleep(30)
            continue
        except Exception as e:
            print(f"[Worker] Error in polling loop: {e}. Stopping poll")
            await asyncio.sleep(60)
            continue


# =========================================================================
# FASTAPI APP
# =========================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global POLLING_CLIENT
    POLLING_CLIENT = httpx.AsyncClient(timeout=None)
    polling_task = asyncio.create_task(polling_loop(POLLING_CLIENT))
    yield
    polling_task.cancel()
    await POLLING_CLIENT.aclose()


app = FastAPI(title="Worker", lifespan=lifespan)

@app.post("/control/check-for-work")
async def check_for_work():
    WAKE_UP_EVENT.set()
    return {"status": "started"}


@app.get("/health/ping")
async def ping():
    return {"status": "pong"}

import uvicorn
WORKER_HOST = os.getenv('WORKER_HOST', '0.0.0.0')
WORKER_PORT = int(os.getenv('WORKER_BASE_PORT', 8000)) 

if __name__ == "__main__":
    uvicorn.run("worker:app", host=WORKER_HOST, port=WORKER_PORT, reload=True)