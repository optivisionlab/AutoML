# Standard Libraries
import base64
import io

# Third-party Libraries
import pandas as pd
from bson.objectid import ObjectId

# Local Modules
from database.database import get_database

class MongoDataLoader:
    def __init__(self):
        self.__db = get_database()
        self.__data_collection = self.__db["tbl_Data"]

    # database đang xử lý đồng bộ
    def _get_base64_string_from_db(self, id_data: str) -> str | None:
        """Lấy chuỗi Base64 từ MongoDB theo ID"""

        try: 
            data = self.__data_collection.find_one({"_id": ObjectId(id_data)})
            return data.get("dataFile") if data else None
        except Exception as e:
            print(f"Exception when get dataset from MongoDB: {str(e)}")
            return None
    
    
    def get_data_and_features(self, id_data: str) -> tuple[pd.DataFrame | None, list | None]:
        """Giải mã chuỗi Base64 thành DataFrame"""
        base64_string = self._get_base64_string_from_db(id_data)
        if not base64_string:
            return None, None
        
        try:
            decoded_data = base64.b64decode(base64_string)
            data_stream = io.BytesIO(decoded_data)
            df = pd.read_csv(data_stream)
            # df = df.where(pd.notna(df), None)

            # Lấy danh sách các cột (features)
            features = df.columns.tolist()

            return df, features
        except Exception as e:
            print(f"Exception when decode dataset from MongoDB: {str(e)}")
            return None, None
        
    
dataset = MongoDataLoader()