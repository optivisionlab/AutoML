# Standard Libraries
import pickle
import base64
import asyncio

# Third-party Libraries
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

# Local Modules
from automl.engine import train_process
from database.get_dataset import dataset

# ÁNH XẠ MÔ HÌNH AN TOÀN
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


app = FastAPI()
# Load environment
load_dotenv()

@app.post("/train")
async def train_models(request: Request):
    """
    Huấn luyện model
    """

    # Xử lý dữ liệu
    try:
        payload = await request.json()

        # Process data
        try:
            metric_list = payload["metrics"]
            config = payload["config"]
            
            choose = config.get("choose")
            list_feature = config.get("list_feature")
            target = config.get("target")
            metric_sort = config.get("metric_sort")

            data, features = await asyncio.to_thread(dataset.get_data_and_features, payload["id_data"])
            
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid data format: {str(e)}"
            )

        # Train models
        models = {}
        for id, content in payload["models"].items():
            models[int(id)] = content # Chuyển ID mới thành int
            content['model'] = MODEL_MAPPING[content['model']]()

        try:
            # Tác vụ huấn luyện sử dụng nhóm luồng
            best_model_id, best_model ,best_score, best_params, model_scores = await asyncio.to_thread(
                train_process,
                data,
                choose,
                list_feature,
                target,
                metric_list,
                metric_sort,
                models
            )

            # Tuần tư hóa mô hình thành byte
            model_bytes = pickle.dumps(best_model)

            # Mã hóa chuỗi byte thành Base64 để có thể truyền qua JSON
            model_base64 = base64.b64encode(model_bytes).decode('utf-8')

            return {
                "success": True,
                "model_scores": model_scores,
                "best_model": model_base64,
                "best_score": best_score
            }

            
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Training failed: {str(e)}"
            )
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    


@app.get("/health")
async def health_check() -> dict[str, str]:
    """API kiểm tra tình trạng worker"""
    return {
        "status": "OK",
        "message": "Welcome to my server!"
    }



import uvicorn

if __name__ == "__main__":
    uvicorn.run("worker:app", host="0.0.0.0", port=8000, reload=True)
