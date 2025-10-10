# Standard Libraries
import io

# Third-party Libraries
import pandas as pd
from bson.objectid import ObjectId
from automl.v2.minio import minIOStorage

# Local Modules
from database.database import get_database

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
                return data.get("bucket_name"), data.get("object_name")
        except Exception as e:
            print(f"Exception when get dataset from MongoDB: {str(e)}")
            return None, None
    
    
    def get_data_and_features(self, id_data: str) -> tuple[pd.DataFrame | None, list | None]:
        """Load dataset từ MinIO"""
        bucket_name, object_name = self._get_data_link_from_db(id_data)
        if not (bucket_name and object_name):
            return None, None
        
        try:
            parquet_stream = minIOStorage.get_object(bucket_name, object_name)
            df_retrieved = pd.read_parquet(parquet_stream)
            parquet_stream.close()

            # df_retrieved = df_retrieved.where(pd.notna(df_retrieved), None)

            # Lấy danh sách các cột (features)
            features = df_retrieved.columns.tolist()

            return df_retrieved, features
        except Exception as e:
            print(f"Exception when read dataset from MinIO: {str(e)}")
            return None, None
        
    
dataset = MongoDataLoader()