# Standard Libraries
import time

# Third-party Libraries
from fastapi import status, HTTPException, Query
from fastapi.routing import APIRouter
import asyncio
import pickle

# Local Modules
from database.get_dataset import dataset
from kafka_consumer import data
from automl.v2.distributed import process_async
from automl.v2.schemas import InputRequest, JobResponse
from automl.v2.service import save_job_mongo, save_job, query_jobs, send_message, get_model
from automl.v2.minio import minIOStorage

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


# API lấy model để sử dụng (mongodb + minio)
@exp.get('jobs/prediction/{id}')
async def get_model_by_path(
    _id: str, 
    data
):
    # model mới có dạng dict, những dữ liệu được training trước đó sẽ xảy ra lỗi.
    bucket_name, object_name = get_model(_id)
    model_stream = None
    try:
        # Lấy luồng byte từ MinIO
        model_stream = minIOStorage.get_object(bucket_name, object_name)
        model = pickle.load(model_stream)

        prediction = model.predict(data)
        return {
            "_id": _id,
            "prediction": prediction.tolist()
        }
    except Exception as e:
        model_stream.close() if model_stream else None
        raise HTTPException(status_code=500, detail=f"Failed to process model: {str(e)}")
    finally:
        if model_stream:
            try:
                model_stream.close()
            except Exception:
                pass