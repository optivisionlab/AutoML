# Standard Libraries

# Third-party Libraries
import pandas as pd
from bson.objectid import ObjectId
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
import pyarrow.parquet as pq

# Local Modules
from database.database import get_database
from automl.v2.minio import minIOStorage

# =========================================================================
# PREPROCESS DATA
# =========================================================================
def detect_column_types(df: pd.DataFrame, text_cardinality_threshold: int = 50):
    numeric_cols = []
    categorical_cols = []
    text_cols = []
    
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)
        elif pd.api.types.is_object_dtype(df[col]):
            unique_count = df[col].nunique()
            if unique_count > text_cardinality_threshold:
                text_cols.append(col)
            else:
                categorical_cols.append(col)

    return numeric_cols, categorical_cols, text_cols


# Pipeline
numeric_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler())
])

categorical_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='most_frequent')),
    ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
])

text_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='constant', fill_value='')),
    ('tfidf', TfidfVectorizer(max_features=100, preprocessor=lambda x: str(x)))
])

def preprocess_data(list_feature: list, target: str, data: pd.DataFrame):
    data_process = data[list_feature]
    numeric_cols, categorical_cols, text_cols = detect_column_types(data_process)

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', numeric_transformer, numeric_cols),
            ('cat', categorical_transformer, categorical_cols),
            ('text', text_transformer, text_cols)
        ],
        remainder='passthrough'
    )

    X_processed = preprocessor.fit_transform(data_process)

    y_data = data[target]
    le_target = LabelEncoder()

    y_imputed_as_str = y_data.fillna('').astype(str)
    y_processed = le_target.fit_transform(y_imputed_as_str)

    return X_processed, y_processed, preprocessor
# =========================================================================



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
        
    
    def get_data_preview(self, id_data: str, num_rows: int = 50) -> tuple[pd.DataFrame | None, list | None]:
        bucket_name, object_name = self._get_data_link_from_db(id_data)
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


    def get_data_features(self, id_data: str) -> list | None:
        bucket_name, object_name = self._get_data_link_from_db(id_data)
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


    def get_processed_data(self, id_data: str, list_features: list, target: str) -> tuple[pd.DataFrame, pd.DataFrame, object] | tuple[None, None, None]:
        """Load dataset từ MinIO"""
        bucket_name, object_name = self._get_data_link_from_db(id_data)
        if not (bucket_name and object_name):
            return None, None, None
        
        try:
            parquet_stream = minIOStorage.get_object(bucket_name, object_name)
            df_retrieved = pd.read_parquet(parquet_stream)

            X_processed, y_processed, preprocessor = preprocess_data(list_features, target, df_retrieved)

            return X_processed, y_processed, preprocessor

        except Exception as e:
            print(f"Exception when read dataset from MinIO: {str(e)}")
            return None, None, None



dataset = MongoDataLoader()


class MongoJob:
    def __init__(self):
        self.__db = get_database()
        self.__job_collection = self.__db["tbl_Job"]

    def update_failure(self, job_id: str, error_msg: str):
            update_data = {
                "$set": {
                    "status": -1,
                    "infor": error_msg
                }
            }
            self.__job_collection.update_one({"job_id": job_id}, update_data)

        
    def update_success(self, job_id: str, final_result: dict):
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
                "status": 1
            }
        }
        self.__job_collection.update_one({"job_id": job_id}, update_data)

job_update = MongoJob()