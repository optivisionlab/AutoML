import pickle
import base64
import asyncio
import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
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
from database.get_dataset import dataset

load_dotenv()

# ÁNH XẠ MÔ HÌNH
MODEL_MAPPING = {
    "RandomForestClassifier": RandomForestClassifier,
    "DecisionTreeClassifier": DecisionTreeClassifier,
    "SVC": SVC,
    "KNeighborsClassifier": KNeighborsClassifier,
    "LogisticRegression": LogisticRegression,
    "GaussianNB": GaussianNB,
    "KMeans": KMeans,
    "DBSCAN": DBSCAN,
    "AgglomerativeClustering": AgglomerativeClustering,
    "MeanShift": MeanShift,
    "SpectralClustering": SpectralClustering
}

app = FastAPI(title="Dynamic Caching Worker")
IS_POLLING = False

DATASET_CACHE = {}

async def _execute_single_training_task(task: dict):
    """Xử lý việc huấn luyện với một model"""
    try:
        id_data = task["id_data"]
        config = task["config"]
        list_feature = config.get("list_feature")

        if id_data in DATASET_CACHE:
            data = DATASET_CACHE[id_data]
        else:
            data, features = await asyncio.to_thread(dataset.get_data_and_features, id_data, list_feature)
            DATASET_CACHE[id_data] = (data)

        model_info = task["model_info"]
        models_to_train = {
            0: {
                "model": MODEL_MAPPING[model_info["model"]](),
                "params": model_info["params"]
            }
        }

        print("Training")
        best_model_id, best_model_obj, best_score, best_params, model_scores_list = await asyncio.to_thread(
            train_process,
            data, config.get("choose"), list_feature, config.get("target"),
            task["metrics"], config.get("metric_sort"), models_to_train
        )

        model_bytes = pickle.dumps(best_model_obj)
        model_base64 = base64.b64encode(model_bytes).decode('utf-8')

        return {
            "success": True,
            "model_name": model_scores_list[0]["model_name"],
            "score": best_score,
            "scores": model_scores_list[0]["scores"],
            "best_params": best_params,
            "model_base64": model_base64
        }
    except Exception as e:
        print(f"Error executing task for model: {e}")
        return { "success": False, "error": str(e) }
    

async def _polling_loop(master_api_url: str, job_id: str):
    global IS_POLLING
    IS_POLLING = True

    id_data_for_this_job = None

    async with httpx.AsyncClient(timeout=None) as client:
        while True:
            try:
                response = await client.get(f"{master_api_url}/jobs/{job_id}/task")
                response.raise_for_status()
                task = response.json().get("task")
                if not task:
                    break

                if not id_data_for_this_job:
                    id_data_for_this_job = task.get("id_data")

                result = await _execute_single_training_task(task)

                await client.post(f"{master_api_url}/jobs/{job_id}/result", json=result)
            except Exception as e:
                print(f"[{job_id}] Error in polling loop: {e}. Retrying in 5s.")
                await asyncio.sleep(5)
    
    IS_POLLING = False
    print(f"[{job_id}]: Polling loop finished.")
    if id_data_for_this_job and id_data_for_this_job in DATASET_CACHE:
        del DATASET_CACHE[id_data_for_this_job]
        print(f"[{job_id}]: Self-cleaned cache for id_data: {id_data_for_this_job}")


@app.post("/control/start-work")
async def start_work(request: Request):
    global IS_POLLING
    if IS_POLLING: return {"status": "already_working"}
    payload = await request.json()
    master_api_url = payload.get("master_api_url")
    job_id = payload.get("job_id")
    if not master_api_url or not job_id:
        raise HTTPException(status_code=400, detail="master_api_url and job_id are required")
    
    asyncio.create_task(_polling_loop(master_api_url, job_id))
    return {"status": "work_started"}


@app.get("/health")
async def health_check():
    return {"status": "OK", "is_polling": IS_POLLING}


if __name__ == "__main__":
    import uvicorn
    HOST = os.getenv('WORKER_HOST', '0.0.0.0')
    PORT = int(os.getenv('WORKER_BASE_PORT', 8000))
    uvicorn.run("worker:app", host=HOST, port=PORT, reload=True)