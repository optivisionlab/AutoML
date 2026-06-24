from fastapi import FastAPI, Request
import uvicorn
from typing import Dict, Any

app = FastAPI(title="Mock HAutoML Server")

@app.post("/get-list-data-by-userid")
async def list_datasets(id: str = ""):
    return {"datasets": [{"id": "dataset_student", "name": "student"}]}

@app.get("/get-data-info")
async def get_dataset(id: str = ""):
    return {
        "id": id, 
        "name": "student", 
        "problem_type": "classification", 
        "target": "grade",
        "n_rows": 1000,
        "n_cols": 10
    }

@app.get("/api/v1/available-models/{problem_type}")
async def get_models(problem_type: str):
    return {"models": ["Random Forest", "XGBoost", "SVM", "Logistic Regression", "KNN"]}

@app.post("/train-from-requestbody-json/")
async def start_training(userId: str, id_data: str, request: Request):
    data = await request.json()
    return {"job_id": "job_123", "status": "running", "models_requested": data.get("models", [])}

@app.post("/get-job-info")
async def get_job(id: str = ""):
    return {
        "job_id": id, 
        "status": "completed", 
        "best_model": "Random Forest",
        "best_score": 0.96,
        "leaderboard": [
            {"model": "Random Forest", "accuracy": 0.96},
            {"model": "XGBoost", "accuracy": 0.93},
            {"model": "SVM", "accuracy": 0.91}
        ]
    }

@app.post("/get-list-job-by-userId")
async def list_jobs(user_id: str = ""):
    return {"jobs": [{"job_id": "job_123", "status": "completed"}]}

@app.get("/home")
async def home():
    return {"message": "HAutoML API is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8585)
