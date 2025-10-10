# Thao tác với MinIO

"""
minio-data/
    user_id/
        job_id/
            {model_name}_{version}.pkl
"""

# Standard libraries
import os
import io

# Third-party libraries
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv

load_dotenv()

# Truy cập các biến môi trường
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY") 

class MinIOStorage:
    def __init__(self, endpoint, access_key, secret_key, secure=False):
        try:
            if not all([endpoint, access_key, secret_key]):
                raise ValueError("Not found environment variables")
            
            self.__client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure
            )
            print("MinIO client initialized successfully.")
        except Exception as e:
            raise Exception(f"MinIO initialization error: {e}")
    

    def uploaded_model(self, bucket_name: str, object_name: str, model_bytes: bytes, ):
        if not self.__client.bucket_exists(bucket_name):
            try:
                self.__client.make_bucket(bucket_name)
            except S3Error as e:
                if e.code == 'BucketAlreadyOwnedByYou' or e.code == 'BucketAlreadyExists':
                    pass 
                else:
                    raise Exception(f"Failed to create MinIO bucket '{bucket_name}': {e}")

        with io.BytesIO(model_bytes) as data_stream:
            try:
                self.__client.put_object(
                    bucket_name,
                    object_name,
                    data=data_stream,
                    length=len(model_bytes),
                    content_type='application/octet-stream'
                )
                print(f"Model uploaded to MinIO: s3://{bucket_name}/{object_name}")
            except S3Error as e:
                # Ghi log lỗi chi tiết hơn
                raise Exception(f"MinIO upload error (S3Error) for {object_name}: {e}")
            except Exception as e:
                raise Exception(f"MinIO upload error for {object_name}: {e}")
        

    def uploaded_dataset(self, bucket_name: str, object_name: str, parquet_buffer):
        if not self.__client.bucket_exists(bucket_name):
            try:
                self.__client.make_bucket(bucket_name)
            except S3Error as e:
                if e.code == 'BucketAlreadyOwnedByYou' or e.code == 'BucketAlreadyExists':
                    pass 
                else:
                    raise Exception(f"Failed to create MinIO bucket '{bucket_name}': {e}")

        try:
            self.__client.put_object(
                bucket_name,
                object_name,
                data=parquet_buffer,
                length=len(parquet_buffer.getvalue()),
                content_type='application/x-parquet'
            )
            print(f"Dataset uploaded to MinIO: s3://{bucket_name}/{object_name}")
        except S3Error as e:
            raise Exception(f"MinIO upload error (S3Error) for {object_name}: {e}")
        except Exception as e:
            raise Exception(f"MinIO upload error for {object_name}: {e}") 


    def get_object(self, bucket_name: str, object_name: str):
        try:
            data_stream = self.__client.get_object(
                bucket_name,
                object_name
            )
            return data_stream
        except Exception as e:
            raise Exception(f"{str(e)}")


    def remove_object(self, bucket_name: str, object_name: str):
        try:
            self.__client.remove_object(
                bucket_name,
                object_name
            )
            return True
        except S3Error as e:
            if e.code == 'NoSuchKey':
                print(f"Object don't exists, skip: {object_name}")
                return True
            raise Exception(f"Error when remove object: {e}")
        except Exception as e:
            raise Exception(f"Unspecified error when remove object: {e}")

        
    def get_url(self, bucket_name: str, object_name: str):
        try:
            url = self.__client.presigned_get_object(bucket_name, object_name)
            print(f"Pre Signed URL: {url}")
            return url
        except Exception as e:
            raise Exception(f"{str(e)}")


    def download_model(self, bucket_name: str, object_name: str, local_temp_path: str):
        try:
            os.makedirs(os.path.dirname(local_temp_path), exist_ok=True)
            
            self.__client.fget_object(
                bucket_name,
                object_name,
                local_temp_path
            )
            print(f"Model downloaded successfully to: {local_temp_path}")
            return local_temp_path
        except S3Error as e:
            # S3Error sẽ bắt được lỗi NoSuchBucket, NoSuchKey,, ...
            raise Exception(f"MinIO download drror (S3Error): {e}")
        except Exception as e:
            raise Exception(f"MinIO download error: {e}")

    def list_objects(self, bucket_name: str):
        for obj in self.__client.list_objects(bucket_name, recursive=True):
            print(obj.object_name)
        
        
minIOStorage = MinIOStorage(endpoint=MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY)
