# Standard libraries
import io
import logging
import os

# Third-party libraries
from miniopy_async import Minio
from miniopy_async.error import S3Error
from miniopy_async.commonconfig import CopySource
from fastapi import status

# Local libraries
from src.config.settings import settings
from src.core.exceptions import CustomException, ErrorCode


# Logging
logger = logging.getLogger(__name__)


"""
minio-data/
    user_id/
        job_id/
            {model_name}_{version}.pkl
"""


class MinIOStorage:
    def __init__(self):
        try:
            self.client = Minio(
                endpoint=settings.MINIO.ENDPOINT,
                access_key=settings.MINIO.ACCESS_KEY,
                secret_key=settings.MINIO.SECRET_KEY,
                secure=settings.PROJECT.ENVIRONMENT != "development"
            )
        except Exception as e:
            logger.error(f"MinIO initialization error: {e}")
            raise Exception("Failed to initialize MinIO Client")

    async def _ensure_bucket_exists(self, bucket_name: str) -> None:
        try:
            if not await self.client.bucket_exists(bucket_name):
                await self.client.make_bucket(bucket_name)
        except S3Error as e:
            if e.code in ('BucketAlreadyOwnedByYou', 'BucketAlreadyExists'):
                pass
            else:
                logger.error(f"Failed to create Minio bucket {bucket_name}: {e}")
                raise CustomException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Storage error: {e.message}",
                    error_code=ErrorCode.INTERNAL_SERVER_ERROR
                )

    async def upload_object(self, bucket_name: str, object_name: str, object_bytes: bytes):
        await self._ensure_bucket_exists(bucket_name)

        with io.BytesIO(object_bytes) as data_stream:
            try:
                await self.client.put_object(
                    bucket_name,
                    object_name,
                    data=data_stream,
                    length=len(object_bytes),
                    content_type='application/octet-stream'
                )
                logger.info(f"Model uploaded to MinIO: s3://{bucket_name}/{object_name}")
            except Exception as e:
                logger.error(f"MinIO upload error for {object_name}: {e}")
                raise CustomException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to upload file to storage.",
                    error_code=ErrorCode.INTERNAL_SERVER_ERROR
                )

    async def move_model(self, source_bucket: str, source_model: str, dest_bucket: str, dest_model: str):
        if not await self.client.bucket_exists(source_bucket):
            raise CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source bucket {source_bucket} not found.",
                error_code=ErrorCode.NOT_FOUND
            )

        await self._ensure_bucket_exists(dest_bucket)

        try:
            await self.client.copy_object(
                bucket_name=dest_bucket,
                object_name=dest_model,
                source=CopySource(source_bucket, source_model)
            )
            await self.client.remove_object(source_bucket, source_model)
        except Exception as e:
            logger.error(f"Minio move error for {source_model}: {e}")
            raise CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to move object in storage.",
                error_code=ErrorCode.INTERNAL_SERVER_ERROR
            )

    async def copy_object(self, source_bucket: str, source_key: str, dest_bucket: str, dest_key: str):
        if not await self.client.bucket_exists(source_bucket):
            raise CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source bucket {source_bucket} not found.",
                error_code=ErrorCode.NOT_FOUND
            )

        await self._ensure_bucket_exists(dest_bucket)

        try:
            await self.client.copy_object(
                bucket_name=dest_bucket,
                object_name=dest_key,
                source=CopySource(source_bucket, source_key)
            )
        except Exception as e:
            logger.error(f"Minio copy error for {source_key}: {e}")
            raise CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to copy object in storage.",
                error_code=ErrorCode.INTERNAL_SERVER_ERROR
            )

    async def upload_dataset(self, bucket_name: str, object_name: str, parquet_buffer: io.BytesIO):
        await self._ensure_bucket_exists(bucket_name)

        try:
            await self.client.put_object(
                bucket_name,
                object_name,
                data=parquet_buffer,
                length=len(parquet_buffer.getvalue()),
                content_type='application/x-parquet'
            )
            logger.info(f"Dataset uploaded to MinIO: s3://{bucket_name}/{object_name}")
        except Exception as e:
            logger.error(f"MinIO upload error for {object_name}: {e}")
            raise CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload dataset to storage.",
                error_code=ErrorCode.INTERNAL_SERVER_ERROR
            )

    async def check_object_exists(self, bucket_name: str, object_name: str) -> bool:
        try:
            await self.client.stat_object(bucket_name, object_name)
            return True
        except S3Error as e:
            if e.code in ('NoSuchKey', 'NoSuchBucket') or '404' in str(e):
                return False
            logger.error(f"Error checking file {object_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unknown error checking file {object_name}: {e}")
            return False

    async def get_object(self, bucket_name: str, object_name: str) -> io.BytesIO:
        response = None
        try:
            response = await self.client.get_object(bucket_name, object_name)
            data_bytes = await response.read()
            buffer = io.BytesIO(data_bytes)
            buffer.seek(0)
            return buffer
        except S3Error as e:
            raise CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Object not found: {e.message}",
                error_code=ErrorCode.NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Get object error: {e}")
            raise CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving object from storage.",
                error_code=ErrorCode.INTERNAL_SERVER_ERROR
            )
        finally:
            if response:
                try:
                    response.close()
                    if hasattr(response, 'release'):
                        response.release()
                except Exception:
                    pass

    async def remove_object(self, bucket_name: str, object_name: str) -> bool:
        try:
            await self.client.remove_object(bucket_name, object_name)
            return True
        except S3Error as e:
            if e.code == 'NoSuchKey':
                logger.info(f"Object doesn't exist, skip removing: {object_name}")
                return True
            logger.error(f"Error removing object {object_name}: {e}")
            raise CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove object from storage.",
                error_code=ErrorCode.INTERNAL_SERVER_ERROR
            )

    async def get_url(self, bucket_name: str, object_name: str) -> str:
        try:
            url = await self.client.presigned_get_object(bucket_name, object_name)
            logger.info(f"Pre Signed URL generated for: {object_name}")
            return url
        except Exception as e:
            logger.error(f"Presigned URL error: {e}")
            raise CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate download URL.",
                error_code=ErrorCode.INTERNAL_SERVER_ERROR
            )

    async def download_model(self, bucket_name: str, object_name: str, local_temp_path: str) -> str:
        try:
            os.makedirs(os.path.dirname(local_temp_path), exist_ok=True)
            await self.client.fget_object(bucket_name, object_name, local_temp_path)
            logger.info(f"Model downloaded successfully to: {local_temp_path}")
            return local_temp_path
        except Exception as e:
            logger.error(f"MinIO download error: {e}")
            raise CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to download model to local system.",
                error_code=ErrorCode.INTERNAL_SERVER_ERROR
            )

    async def list_objects(self, bucket_name: str):
        try:
            async for obj in self.client.list_objects(bucket_name, recursive=True):
                logger.info(obj.object_name)
        except Exception as e:
            logger.error(f"List objects error: {e}")


# Instantiate MinIO
minio_service = MinIOStorage()
