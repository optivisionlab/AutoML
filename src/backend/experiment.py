# Standard Libraries
import time
from uuid import uuid4

# Third-party Libraries
from fastapi import status, HTTPException
from fastapi.routing import APIRouter
from pydantic import BaseModel
import asyncio
from bson import ObjectId

# Local Modules
from database.get_dataset import dataset, get_database
from kafka_consumer import get_producer
from kafka_consumer import data
from automl.distributed import process_async

exp = APIRouter(prefix="/v2/auto", tags=["Experiment API"])

class InputRequest(BaseModel):
    id_data: str
    id_user: str
    config: dict

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id_data": "1",
                    "id_user": "2",
                    "config": {
                        "choose": "new_model",
                        "metric_sort": "accuracy",
                        "list_feature": [
                            "A",
                            "B",
                            "..."
                        ],
                        "target": "Revenue"

                    }
                }
            ]
        }
    }

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



async def send_message(topic: str, key: str, message: dict):
    try:
        producer = get_producer()
    except RuntimeError:
        raise ConnectionError("Kafka Producer not initialized in the lifespan.")

    await producer.send_and_wait(
        topic=topic, 
        key=key.encode('utf-8'), 
        value=message
    )


def save_job_mongo(input: InputRequest, models_info) -> dict:
    db = get_database()
    user_collection = db["tbl_User"]
    job_collection = db["tbl_Job"]
    data_collection = db["tbl_Data"]


    try:
        # Tìm tên người dùng
        user_doc = user_collection.find_one({"_id": ObjectId(input.id_user)}, {"username": 1})

        if not user_doc:
            return {"status": "error", "message": "User not found"}
        user_name = user_doc.get("username")

        # Tìm tên dữ liệu
        data_doc = data_collection.find_one({"_id": ObjectId(input.id_data)}, {"dataName": 1})
        if not data_doc:
            return {"status": "error", "message": "Data not found"}
        data_name = data_doc.get("dataName")

        # Tạo một bản ghi job mới
        new_job = {
            "job_id": str(uuid4()),
            "best_model_id": models_info["best_model_id"],
            "best_model": models_info["best_model"],
            "model": models_info["model"],
            "best_params": models_info["best_params"],
            "best_score": models_info["best_score"],
            "orther_model_scores": models_info["model_scores"],
            "config": input.config,
            "data": {
                "id": input.id_data,
                "name": data_name
            },
            "user": {
                "id": input.id_user,
                "name": user_name
            },
            "status": 1,
            "activate": 0,
            "create_at": time.time(),
        }

        # Chèn bản ghi job vào collection
        result = job_collection.insert_one(new_job)

        # Trả về kết quả
        return {
            "status": "success",
            "message": "Job saved successfully",
            "job_id": str(result.inserted_id)
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

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



def save_job(input: InputRequest) -> str:
    db = get_database()
    user_collection = db["tbl_User"]
    job_collection = db["tbl_Job"]
    data_collection = db["tbl_Data"]
    
    # Tìm tên người dùng
    user_doc = user_collection.find_one({"_id": ObjectId(input.id_user)}, {"username": 1})

    if not user_doc:
        raise ValueError("User not found")
    user_name = user_doc.get("username")

    # Tìm tên dữ liệu
    data_doc = data_collection.find_one({"_id": ObjectId(input.id_data)}, {"dataName": 1})
    if not data_doc:
        raise ValueError("Data not found")
    data_name = data_doc.get("dataName")

    job_id = str(uuid4())

    # Tạo một bản ghi job mới
    new_job = {
        "job_id": job_id,
        "config": input.config,
        "data": {
            "id": input.id_data,
            "name": data_name
        },
        "user": {
            "id": input.id_user,
            "name": user_name
        },
        "status": 0,
        "activate": 0,
        "create_at": time.time()
    }

    msg_job = {
        "id_data": input.id_data,
        "config": input.config
    }

    try:
        job_collection.insert_one(new_job)

    except Exception as e:
        raise Exception(f"{str(e)}")
    
    return job_id, msg_job


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
