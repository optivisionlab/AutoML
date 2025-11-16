# Standard Libraries

# Third-party Libraries
import pandas as pd
from bson.objectid import ObjectId
import pyarrow.parquet as pq
import time
from pymongo.asynchronous.database import AsyncDatabase
from fastapi import Depends

# Local Modules
from automl.v2.minio import minIOStorage
from automl.process_data import preprocess_data
from database.database import get_db


class MongoDataLoader:
    def __init__(self, db: AsyncDatabase):
        self.__data_collection = db.tbl_Data

    # database đang xử lý đồng bộ
    async def _get_data_link_from_db(self, id_data: str) -> tuple[str | None, str | None]:
        """Lấy data link từ MongoDB theo ID"""

        try:
            data = await self.__data_collection.find_one({"_id": ObjectId(id_data)}, {"data_link": 1})
            if data:
                data_link = data.get("data_link", {})
                return data_link.get("bucket_name"), data_link.get("object_name")
        except Exception as e:
            print(f"Exception when get dataset from MongoDB: {str(e)}")
            return None, None
        
    
    async def get_data_preview(self, id_data: str, num_rows: int = 50) -> tuple[pd.DataFrame | None, list | None]:
        bucket_name, object_name = await self._get_data_link_from_db(id_data)
        if not (bucket_name and object_name):
            return None
        
        try:
            parquet_stream = minIOStorage.get_object(bucket_name, object_name)
            df_retrieved = pd.read_parquet(parquet_stream)

            df_preview = df_retrieved.head(num_rows)

            return df_preview
        
        except Exception as e:
            print(f"Exception when get dataset preview: {str(e)}")
            return None


    async def get_data_features(self, id_data: str) -> list | None:
        bucket_name, object_name = await self._get_data_link_from_db(id_data)
        if not (bucket_name and object_name):
            return None
        
        try:
            # Lấy file stream
            parquet_stream = minIOStorage.get_object(bucket_name, object_name)
            
            schema = pq.read_schema(parquet_stream)
            
            return schema.names
        except Exception as e:
            print(f"Exception when get dataset schema: {str(e)}")
            return None


    async def get_processed_data(self, id_data: str, list_features: list, target: str) -> tuple[pd.DataFrame, pd.DataFrame, object] | tuple[None, None, None]:
        """Load dataset từ MinIO"""
        bucket_name, object_name = await self._get_data_link_from_db(id_data)
        if not (bucket_name and object_name):
            return None, None, None
        
        try:
            parquet_stream = minIOStorage.get_object(bucket_name, object_name)
            df_retrieved = pd.read_parquet(parquet_stream)

            X_processed, y_processed, preprocessor, le_target = preprocess_data(list_features, target, df_retrieved)

            return X_processed, y_processed, preprocessor, le_target

        except Exception as e:
            print(f"Exception when read dataset from MinIO: {str(e)}")
            return None, None, None



class MongoJob:
    def __init__(self, db: AsyncDatabase):
        self.__job_collection = db.tbl_Job

    async def update_failure(self, job_id: str, error_msg: str):
            update_data = {
                "$set": {
                    "status": -1,
                    "infor": error_msg
                }
            }
            await self.__job_collection.update_one({"job_id": job_id}, update_data)

        
    async def update_success(self, job_id: str, final_result: dict):
        update_data = {
            "$set": {
                "best_model_id": final_result["best_model_id"],
                "best_model": final_result["best_model"],
                "model": {
                    "bucket_name": final_result["model"].get("bucket_name", ""),
                    "object_name": final_result["model"].get("object_name", "")
                },
                "best_params": final_result["best_params"],
                "best_score": final_result["best_score"],
                "orther_model_scores": final_result["model_scores"],
                "status": 1,
                "end_time": time.perf_counter()
            }
        }
        await self.__job_collection.update_one({"job_id": job_id}, update_data)
