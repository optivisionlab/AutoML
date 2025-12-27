# Standard Libraries
import os
import yaml

# Third-party Libraries
from fastapi import status, HTTPException, Query, Request, Depends
from pymongo.asynchronous.database import AsyncDatabase
from fastapi.routing import APIRouter
import aiofiles

# Local Modules
from database.get_dataset import MongoDataLoader
from database.database import get_db
from automl.v2.schemas import InputRequest
from automl.v2.service import save_job, query_jobs, send_message


exp = APIRouter(prefix="/v2/auto", tags=["Experiment API"])

# API lấy ra danh sách đặc trưng của dataset 
@exp.get("/features")
async def get_features_of_dataset(id_data: str, problem_type: str, request: Request):
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
async def get_data_of_dataset(id_data: str, request: Request):
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
async def distributed_training(input: InputRequest, db: AsyncDatabase = Depends(get_db)):
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
    db: AsyncDatabase = Depends(get_db)
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
    problem_type: str
) -> dict:
    if not problem_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not recognizing the type of problem"
        )

    base_dir = "assets/system_models"
    metrics = None
    if problem_type == 'classification':
        file_path = os.path.join(base_dir, "model.yml")
        metrics = await read_yaml_async(file_path=file_path)
    elif problem_type == 'regression':
        file_path = os.path.join(base_dir, "regression.yml")
        metrics = await read_yaml_async(file_path=file_path)

    return {
        "metrics": metrics
    }
