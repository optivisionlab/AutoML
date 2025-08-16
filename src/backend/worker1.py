from fastapi import FastAPI, Request, HTTPException
import pandas as pd
from automl.engine import train_process

from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering, MeanShift, SpectralClustering
from sklearn.discriminant_analysis import StandardScaler
from sklearn.calibration import LabelEncoder



app = FastAPI()


@app.post("/train")
async def train_models(request: Request):
    """
    Huấn luyện model
    """
    try:
        payload = await request.json()

        # Process data
        try:
            data = pd.DataFrame(payload["data"])
            config = payload["config"]
            metric_list = payload["metrics"]
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail="Invalid data format"
            )

        # Train models

        models = {}
        for id, content in payload["models"].items():
            models[int(id)] = content
            content['model'] = eval(content['model'])()


        try:
            # bad request do ham train_process
            best_model_id, best_model, best_score, best_params, model_scores = train_process(
                data=data,
                choose = config['choose'],
                list_feature = config['list_feature'],
                target = config['target'],
                metric_list=metric_list,
                metric_sort = config['metric_sort'],
                models=models
            )

            return {
                "success": True,
                "results": [{
                    "best_model_id": best_model_id,
                    "best_model": str(best_model),
                    "best_score": best_score,
                    "best_params": best_params,
                    "model_scores": model_scores
                }]
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Training failed: {str(e)}"
            )
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON   {str(e)}")

     



@app.get("/health")
async def health_check() -> dict[str, str]:
    """API kiểm tra tình trạng worker"""
    return {
        "status": "healthy",
        "ready": "true"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("worker1:app", host="0.0.0.0", port=4001, reload=True)
