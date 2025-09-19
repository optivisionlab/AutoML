# Standard Libraries
import time
from uuid import uuid4
import pickle

# Third-party Libraries
from fastapi import status, HTTPException
from fastapi.routing import APIRouter
from pydantic import BaseModel
import asyncio
from bson.objectid import ObjectId

# Local Modules
from automl.distributed import process_async
from database.get_dataset import dataset, get_database

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
    


def save_job(input: InputRequest, models_info) -> dict:
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
            "other_model_scores": models_info["model_scores"],
            "config": input.config,
            "data": {
                "id": input.id_data,
                "name": data_name
            },
            "user": {
                "id": input.id_user,
                "name": user_name
            },
            "create_at": time.time(),
            "status": 1
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



@exp.post("/distributed/mongodb")
async def distributed_mongodb(input: InputRequest):
    try:
        start = time.time()

        results, processed_workers, successful_workers = await process_async(input.id_data, input.config)
        # Lưu vào database 
        save_job_result:dict = await asyncio.to_thread(save_job, input, results)

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
