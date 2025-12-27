# Standard Libraries
import re
from io import BytesIO

# Third-party Libraries
import pandas as pd
import numpy as np
from bson.objectid import ObjectId
import pyarrow.parquet as pq
from pymongo.asynchronous.database import AsyncDatabase

# Local Modules
from automl.v2.minio import minIOStorage
from automl.process_classification import preprocess_data as classification
from automl.process_regression import preprocess_data as regression


class MongoDataLoader:
    def __init__(self, db: AsyncDatabase):
        self.__data_collection = db.tbl_Data

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

            total_rows = len(df_retrieved)
            df_preview = df_retrieved.head(num_rows)


            return df_preview, total_rows
        
        except Exception as e:
            print(f"Exception when get dataset preview: {str(e)}")
            return None, 0


    @classmethod
    def analyze_column_for_target(cls, series: pd.Series, threshold_unique=20) -> str:
        # Loại bài toán, lý do và cảnh báo
        try:
            # Xử lý dữ liệu null
            clean_series = series.dropna()
            if clean_series.empty:
                return "none"
            
            if pd.api.types.is_datetime64_any_dtype(clean_series) or pd.api.types.is_timedelta64_dtype(clean_series):
                return "none"

            # Nếu là Text hoặc Boolean -> Classification
            if pd.api.types.is_string_dtype(clean_series) or pd.api.types.is_bool_dtype(clean_series):
                return "classification"

            # Nếu là số (numeric)
            if pd.api.types.is_numeric_dtype(clean_series):
                # # Kiểm tra số thập phân -> Regression
                if np.any(np.mod(clean_series, 1) != 0):
                    return "regression"

                # Nếu là số nguyên
                num_unique = clean_series.nunique()
                if num_unique <= threshold_unique:
                    return "classification"

                return "regression"
            
            return "none"
        except Exception as e:
            return "none"


    async def get_features_suggest_target(self, id_data: str, selected_problem_type: str, num_row: int = 1000) -> dict | None:
        bucket_name, object_name = await self._get_data_link_from_db(id_data)
        if not (bucket_name and object_name):
            return None
        
        # Loại bỏ các cột là ID
        pattern = r"^(?i:id|stt|no|key|code|uuid|guid)$|(?i:.*_id)$|.*ID$"

        features = {}

        try:
            # Lấy data stream từ MinIO
            response = minIOStorage.get_object(bucket_name, object_name)
            file_buffer = BytesIO(response.read()) 
            
            # Đọc metadata & preview data
            parquet_file = pq.ParquetFile(file_buffer)
            schema_names = parquet_file.schema.names

            table = parquet_file.read_row_group(0)
            df_preview = table.to_pandas().head(num_row)

            for col_name in schema_names:
                if re.match(pattern, col_name):
                    features[col_name] = False
                    continue

                series: pd.Series = df_preview[col_name]
                if series.isnull().all():
                    features[col_name] = False
                    continue

                suggested_type = self.analyze_column_for_target(series)
                if selected_problem_type == suggested_type:
                    features[col_name] = True
                else:
                    features[col_name] = False

            return features
        except Exception as e:
            print(f"Exception when get dataset schema: {str(e)}")
            return None


    async def get_processed_data(self, id_data: str, list_features: list, target: str, problem_type: str) -> tuple[pd.DataFrame, pd.DataFrame, object, object] | tuple[None, None, None, None]:
        """Load dataset từ MinIO"""
        bucket_name, object_name = await self._get_data_link_from_db(id_data)
        if not (bucket_name and object_name):
            return None, None, None, None
        
        try:
            parquet_stream = minIOStorage.get_object(bucket_name, object_name)
            df_retrieved = pd.read_parquet(parquet_stream)
            
            X_processed, y_processed, preprocessor, le_target = None, None, None, None
            
            if problem_type == "classification":
                # Classification processs
                X_processed, y_processed, preprocessor, le_target = classification(list_features, target, df_retrieved)
            else:
                # Regression process
                X_processed, y_processed, preprocessor, le_target = regression(list_features, target, df_retrieved)

            return X_processed, y_processed, preprocessor, le_target

        except Exception as e:
            print(f"Exception when read dataset from MinIO: {str(e)}")
            return None, None, None, None
    


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
            }
        }
        await self.__job_collection.update_one({"job_id": job_id}, update_data)
