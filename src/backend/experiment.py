# Standard Libraries
import io
import os
import yaml

# Third-party Libraries
from fastapi import status, HTTPException, Query, Request, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from pymongo.asynchronous.database import AsyncDatabase
from fastapi.routing import APIRouter
import aiofiles
import pandas as pd
import numpy as np
import asyncio
import pickle
import joblib

# Local Modules
from database.get_dataset import MongoDataLoader
from database.database import get_db
from automl.v2.schemas import InputRequest
from automl.v2.minio import minIOStorage
from automl.v2.service import save_job, query_jobs, send_message
from users.routers import get_current_user


exp = APIRouter(prefix="/v2/auto", tags=["Experiment API"])


# API lấy ra danh sách đặc trưng của dataset 
@exp.get("/features")
async def get_features_of_dataset(id_data: str, problem_type: str, request: Request, current_user = Depends(get_current_user)):
    dataset = MongoDataLoader(request.app.state.db)
    try:
        features = await dataset.get_features_suggest_target(id_data, problem_type)

        return {
            "features": features
        }
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@exp.get("/data")
async def get_data_of_dataset(id_data: str, request: Request, current_user = Depends(get_current_user)):
    dataset = MongoDataLoader(request.app.state.db)
    try:
        data_preview, total_rows = await dataset.get_data_preview(id_data)

        if data_preview is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or cannot be read"
            )
    
        return {
            "rows": total_rows,
            "data": data_preview.to_dict(orient='records')
        }
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# API huấn luyện model ==> Client -> Kafka -> Server
@exp.post("/jobs/training")
async def distributed_training(input: InputRequest, db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)):
    """Gửi message vào Kafka và huấn luyện model"""

    try:
        job_id, msg_job = await save_job(input, db)

        await send_message(os.getenv('KAFKA_TOPIC'), job_id, msg_job)

        # Trả về kết quả thành công
        return {
            "status": "success",
            "message": "Training job initiated successfully",
            "job_id": job_id
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {str(e)}")


# API lấy danh sách job theo id_user => Thêm phân trang
@exp.get("/jobs/offset/{id_user}", response_model=dict)
async def get_jobs_offset(
    id_user: str,
    page: int = Query(1, ge=1),
    limit: int = Query(5, ge=1),
    db: AsyncDatabase = Depends(get_db),
    current_user = Depends(get_current_user)
):
    job_list_raw, total_pages, total_jobs = await query_jobs(id_user, page, limit, db)

    jobs_data = [{**job, '_id': str(job['_id'])} for job in job_list_raw]

    return {
        "data": jobs_data,
        "pagination": {
            "total_jobs": total_jobs,
            "total_pages": total_pages,
            "current_page": page,
            "next_page": page + 1 if page < total_pages else None,
            "prev_page": page - 1 if page > 1 else None
        }
    }


# API lấy danh sách độ đo
async def read_yaml_async(file_path: str):
    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as file:
        content = await file.read()

    metrics = yaml.safe_load(content)
    return metrics['metric_list']


@exp.get('/metrics')
async def metrics(
    problem_type: str,
    current_user = Depends(get_current_user)
) -> dict:
    if not problem_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not recognizing the type of problem"
        )

    base_dir = "assets/system_models"
    metrics = None
    if problem_type == 'classification':
        file_path = os.path.join(base_dir, "classification.yml")
        metrics = await read_yaml_async(file_path=file_path)
    elif problem_type == 'regression':
        file_path = os.path.join(base_dir, "regression.yml")
        metrics = await read_yaml_async(file_path=file_path)

    return {
        "metrics": metrics
    }


CANCEL_PREDICTION_TASKS = {}

@exp.delete("/{job_id}/predictions")
async def cancel_prediction_task(job_id: str, current_user = Depends(get_current_user)):
    """
    Cancel predict process
    """
    if job_id in CANCEL_PREDICTION_TASKS:
        task = CANCEL_PREDICTION_TASKS[job_id]
        task.cancel()
        return {"detail": f"Successfully force-stopped the job's prediction process {job_id}."}
    
    return {"detail": "No running process found for this job"}


# Temporary model inference
async def inference_model_batch(job_id: str, user_id: str, df: pd.DataFrame, db: AsyncDatabase):
    await asyncio.sleep(15)
    job_collection = db.tbl_Job

    try:
        stored_model_data = await job_collection.find_one({"job_id": job_id, "status": 1})
        if not stored_model_data:
            return {"error": "Job not found or not completed"}
    except Exception as e:
        return {"error": f"Failed to retrieve model: {str(e)}"}

    config = stored_model_data.get("config", {})
    list_feature = config.get("list_feature", [])
    target_name = config.get("target", "Target")

    try:
        model_url = stored_model_data.get("model")
        model_path = f"{model_url.get('object_name')}"
        preprocessor_path = f"{user_id}/{job_id}/preprocessor.joblib"
        target_path = f"{user_id}/{job_id}/target.joblib" 
    except Exception as e:
        return {"error": f"Failed to construct model paths: {str(e)}"}

    async def load_artifact(bucket, path, file_type):
        try:
            buffer = await asyncio.to_thread(minIOStorage.get_object, bucket, path)
            return await asyncio.to_thread(file_type.load, buffer)
        except Exception as e:
            raise ValueError(f"Failed to load artifact from {path}: {str(e)}")

    try:
        model, preprocessor, le_target = await asyncio.gather(
            load_artifact(model_url.get('bucket_name'), model_path, pickle),
            load_artifact(model_url.get('bucket_name'), preprocessor_path, joblib),
            load_artifact(model_url.get('bucket_name'), target_path, joblib)
        )
    except Exception as e:
        return {"error": f"Failed to load required model artifacts: {str(e)}"}

    missing_cols = set(list_feature) - set(df.columns)
    if missing_cols:
        return {"error": f"Uploaded file is missing required columns: {missing_cols}"}

    data_to_predict = df[list_feature]

    try:
        X_new_transformed = await asyncio.to_thread(preprocessor.transform, data_to_predict)

        if isinstance(X_new_transformed, np.ndarray):
            X_new_transformed = np.nan_to_num(X_new_transformed, nan=0.0, posinf=0.0, neginf=0.0)
        elif hasattr(X_new_transformed, "toarray"):
            X_new_transformed = X_new_transformed.toarray()
            X_new_transformed = np.nan_to_num(X_new_transformed, nan=0.0, posinf=0.0, neginf=0.0)

        y_pred_raw = await asyncio.to_thread(model.predict, X_new_transformed)
        if hasattr(y_pred_raw, 'ravel'):
            y_pred_raw = y_pred_raw.ravel()

        if le_target:
            y_pred_final = await asyncio.to_thread(le_target.inverse_transform, y_pred_raw)
        else:
            y_pred_final = y_pred_raw

    except Exception as e:
        return {"error": f"Failed during prediction process: {str(e)}"}

    return {
        "predictions": y_pred_final.tolist(),
        "target_name": target_name
    }


@exp.post("/{job_id}/predictions")
async def create_batch_prediction(
    job_id: str,
    file_data: UploadFile = File(...),
    db: AsyncDatabase = Depends(get_db),
    current_user = Depends(get_current_user)
):
    user_id = str(current_user['_id'])
    filename = file_data.filename.lower()

    try:
        contents = await file_data.read()
        file_stream = io.BytesIO(contents)

        if filename.endswith('.csv'):
            df = pd.read_csv(file_stream)
        elif filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_stream)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only .csv or .xlsx file formats are supported"
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File could not be read: {str(e)}")

    prediction_task = asyncio.create_task(
        inference_model_batch(job_id, user_id, df, db)
    )

    CANCEL_PREDICTION_TASKS[job_id] = prediction_task

    try:
        prediction_result = await prediction_task

        if "error" in prediction_result:
            raise HTTPException(status_code=422, detail=prediction_result['error'])

        predictions = prediction_result['predictions']
        target_name = prediction_result.get('target_name', 'Target')

        df[f"{target_name}_prediction"] = predictions
    except asyncio.CancelledError:
        del df
        raise HTTPException(status_code=499, detail="The process has been canceled")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction errors: {str(e)}")
    finally:
        CANCEL_PREDICTION_TASKS.pop(job_id, None)

    output_stream = io.BytesIO()
    media_type = ""

    if filename.endswith('.csv'):
        df.to_csv(output_stream, index=False)
        media_type = "text/csv"
    elif filename.endswith(('.xls', '.xlsx')):
        df.to_excel(output_stream, index=False)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    output_stream.seek(0)

    return StreamingResponse(
        output_stream,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="predicted_{file_data.filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )
