# Standard Libraries
import time

# Third-party Libraries
from fastapi import status, HTTPException, Query
from fastapi.routing import APIRouter
import asyncio

# Local Modules
from database.get_dataset import dataset
from kafka_consumer import data
from automl.v2.distributed import process_async
from automl.v2.schemas import InputRequest, JobResponse
from automl.v2.service import save_job_mongo, save_job, query_jobs, send_message


exp = APIRouter(prefix="/v2/auto", tags=["Experiment API"])

# API lấy ra danh sách đặc trưng của dataset 
@exp.get("/features")
async def get_features_of_dataset(id_data: str): 
    try:
        data, features = await asyncio.to_thread(dataset.get_data_and_features, id_data)
        dataset.get_data_and_features(id_data)
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


# API training model = client ==> server (dùng cho test)
@exp.post("/distributed/mongodb")
async def distributed_mongodb(input: InputRequest):
    try:
        start = time.time()

        results, processed_workers, successful_workers = await process_async(input.id_data, input.config)
        # Lưu vào database 
        save_job_result:dict = await asyncio.to_thread(save_job_mongo, input, results)

        save_job_result.update({
            "processed_workers": processed_workers,
            "successful_workers": successful_workers,
            "executed_time": time.time() - start
        })

        return save_job_result

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
async def distributed_training(input: InputRequest):
    """Gửi message vào Kafka và huấn luyện model"""

    try:
        job_id, msg_job = await asyncio.to_thread(save_job, input)

        await send_message(data['KAFKA_TOPIC'], job_id, msg_job)

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
    limit: int = Query(5, ge=1)
):
    job_list_raw, total_pages, total_jobs = query_jobs(id_user, page, limit)

    jobs_data = [JobResponse.model_validate(job) for job in job_list_raw]

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