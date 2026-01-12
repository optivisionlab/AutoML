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
    def analyze_column_for_target(cls, series: pd.Series, threshold_unique=50) -> str:
        """
        Trả về: 'classification', 'regression', hoặc 'both' (nếu không chắc chắn)
        """
        try:
            # Xử lý dữ liệu null
            clean_series = series.dropna()
            if clean_series.empty: return "none"
            
            # Ngày tháng thường không làm Target trực tiếp (trừ Time Series Forecasting đặc thù)
            if pd.api.types.is_datetime64_any_dtype(clean_series) or pd.api.types.is_timedelta64_dtype(clean_series):
                return "none"

            # Thử ép sang kiểu số
            series_numeric = pd.to_numeric(clean_series, errors='coerce').dropna()
            is_numeric_column = len(series_numeric) >= 0.5 * len(clean_series)

            if not is_numeric_column:
                # Dạng Text/Boolean -> Classification
                return "classification"
            else:
                clean_series = series_numeric

            # Binary (0/1, True/False) -> Classification
            if clean_series.nunique() <= 2:
                return "classification"
            
            # Số thực (Float) có phần thập phân -> Regression
            is_float = not np.all(np.isclose(clean_series % 1, 0))
            if is_float:
                return "regression"

            # Số nguyên (Integer) -> Vùng nhập nhằng (Gray Area)
            num_unique = clean_series.nunique()

            # Nếu unique quá lớn so với số dòng -> Regression
            if num_unique > 0.9 * len(clean_series):
                return "regression"
            
            # Nếu unique nhỏ -> Ưu tiên Classification, nhưng Regression vẫn khả thi
            if num_unique <= threshold_unique:
                return "both"
            
            return "regression"
        except Exception as e:
            return "none"


    async def get_features_suggest_target(self, id_data: str, selected_problem_type: str, num_row: int = 1000) -> dict | None:
        bucket_name, object_name = await self._get_data_link_from_db(id_data)
        if not (bucket_name and object_name):
            return None
        
        # Loại bỏ các cột là ID
        pattern = r"^(?i:id|stt|no|key|code|uuid|guid)$|(?i:.*_id)$|^ID_.*$"

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
    
                if series.isnull().all() or series.nunique() <= 1:
                    features[col_name] = False
                    continue

                suggested_type = self.analyze_column_for_target(series)

                if selected_problem_type == "classification":
                    # classification & both
                    if suggested_type in ["classification", "both"]:
                        features[col_name] = True
                    else:
                        features[col_name] = False
                
                elif selected_problem_type == "regression":
                    # regression & both
                    if suggested_type in ["regression", "both"]:
                        features[col_name] = True
                    else:
                        features[col_name] = False

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
