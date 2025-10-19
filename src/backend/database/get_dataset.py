# Standard Libraries
import io

# Third-party Libraries
import pandas as pd
import numpy as np
from bson.objectid import ObjectId
from automl.v2.minio import minIOStorage
from typing import List, Optional

# Local Modules
from database.database import get_database

# Preprocess data basic
def automatic_imputation(df: pd.DataFrame, list_features: Optional[List[str]] = None) -> pd.DataFrame:
    df_imputed = df.copy()

    if list_features is None:
        columns_to_impute = df_imputed.columns
    else:
        columns_to_impute = [col for col in list_features if col in df_imputed.columns]


    for column in columns_to_impute:
        if pd.api.types.is_numeric_dtype(df_imputed[column]):
            median_val = df_imputed[column].median()
            df_imputed[column] = df_imputed[column].fillna(median_val)
        
        elif pd.api.types.is_object_dtype(df_imputed[column]):        
            df_imputed[column] = df_imputed[column].fillna('')

    return df_imputed


class MongoDataLoader:
    def __init__(self):
        self.__db = get_database()
        self.__data_collection = self.__db["tbl_Data"]

    # database đang xử lý đồng bộ
    def _get_data_link_from_db(self, id_data: str) -> tuple[str | None, str | None]:
        """Lấy data link từ MongoDB theo ID"""

        try: 
            data = self.__data_collection.find_one({"_id": ObjectId(id_data)}, {"data_link": 1})
            if data:
                data_link = data.get("data_link", {})
                return data_link.get("bucket_name"), data_link.get("object_name")
        except Exception as e:
            print(f"Exception when get dataset from MongoDB: {str(e)}")
            return None, None


    
    def get_data_and_features(self, id_data: str, list_features: Optional[List[str]] = None) -> tuple[pd.DataFrame | None, list | None]:
        """Load dataset từ MinIO"""
        bucket_name, object_name = self._get_data_link_from_db(id_data)
        if not (bucket_name and object_name):
            return None, None
        
        try:
            parquet_stream = minIOStorage.get_object(bucket_name, object_name)
            df_retrieved = pd.read_parquet(parquet_stream)


            # df_retrieved = df_retrieved.where(pd.notna(df_retrieved), None)
            df_preprocess = automatic_imputation(df_retrieved, list_features)

            # Lấy danh sách các cột (features)
            features = df_preprocess.columns.tolist()

            return df_preprocess, features
        except Exception as e:
            print(f"Exception when read dataset from MinIO: {str(e)}")
            return None, None
        
    
dataset = MongoDataLoader()
