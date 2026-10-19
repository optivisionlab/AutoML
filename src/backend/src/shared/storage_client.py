# Standard Libraries
import io
import os
import logging
from typing import Any
from urllib.parse import urlparse

# Third-party Libraries
from fastapi import status
from miniopy_async import Minio
from miniopy_async.error import S3Error
from miniopy_async.commonconfig import CopySource

# Local Libraries
from src.core import exceptions, constants, utils
from src.config import settings


# Logging
logger = logging.getLogger(__name__)


class S3Storage:
    """
    Unified Async S3-Compatible Storage Client
    """
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        default_bucket: str = "",
        is_secure: bool = False,
        provider_name: str = "S3",
    ):
        self.endpoint = self._clean_endpoint(endpoint)
        self.access_key = access_key
        self.secret_key = secret_key
        self.default_bucket = default_bucket
        self.is_secure = is_secure
        self.provider_name = provider_name
        self.client: Minio | None = None
        self._init_client()

    @staticmethod
    def _clean_endpoint(raw_url: str) -> str:
        if not raw_url:
            return ""
        parsed = urlparse(raw_url)
        endpoint = parsed.netloc if parsed.netloc else parsed.path
        return endpoint.strip("/")

    def _init_client(self) -> None:
        if not self.endpoint or not self.access_key:
            self.client = None
            return
        try:
            self.client = Minio(
                endpoint=self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.is_secure,
            )
        except Exception as e:
            logger.error(f"[{self.provider_name}] Initialization error: {e}")
            self.client = None

    def _resolve_bucket_and_object(
        self,
        arg1: str,
        arg2: str | None = None,
        bucket_name: str | None = None,
    ) -> tuple[str, str]:
        if arg2 is not None:
            return arg1, arg2
        target_bucket = bucket_name or self.default_bucket
        if not target_bucket:
            raise exceptions.CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Bucket name is required for {self.provider_name} storage",
                error_code=constants.ErrorCode.INTERNAL_SERVER_ERROR,
            )
        return target_bucket, arg1

    async def _ensure_bucket_exists(self, bucket_name: str) -> None:
        if not self.client:
            self._init_client()
        if not self.client:
            raise exceptions.CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{self.provider_name} storage client is not configured",
                error_code=constants.ErrorCode.INTERNAL_SERVER_ERROR,
            )
        try:
            if not await self.client.bucket_exists(bucket_name):
                await self.client.make_bucket(bucket_name)
        except S3Error as e:
            if e.code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists", "AccessDenied"):
                pass
            else:
                logger.warning(f"[{self.provider_name}] Bucket check error for {bucket_name}: {e.message}")
        except Exception as e:
            logger.warning(f"[{self.provider_name}] Bucket check error for {bucket_name}: {e}")

    async def upload_file_stream(
        self,
        object_name: str,
        file_obj: Any,
        bucket_name: str | None = None,
        content_type: str = "application/octet-stream",
        length: int = -1,
        part_size: int = 10 * 1024 * 1024,
        max_size_mb: int | None = None,
    ) -> None:
        target_bucket = bucket_name or self.default_bucket
        if not target_bucket:
            raise exceptions.CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Bucket name is required for {self.provider_name} upload",
                error_code=constants.ErrorCode.INTERNAL_SERVER_ERROR,
            )

        limit_mb = max_size_mb if max_size_mb is not None else (settings.BACKBLAZE.MAX_FILE_SIZE_MB if self.provider_name == "Backblaze" else None)
        if limit_mb is not None:
            utils.validate_file_size(file_obj, max_size_mb=limit_mb)

        if length == -1:
            detected_size = utils.get_file_size(file_obj)
            if detected_size >= 0:
                length = detected_size

        await self._ensure_bucket_exists(target_bucket)

        try:
            await self.client.put_object(
                bucket_name=target_bucket,
                object_name=object_name,
                data=file_obj,
                length=length if length >= 0 else -1,
                part_size=part_size if length < 0 or length > part_size else 0,
                content_type=content_type,
            )
            logger.info(f"[{self.provider_name}] Uploaded stream: s3://{target_bucket}/{object_name}")
        except exceptions.CustomException:
            raise
        except Exception as e:
            logger.error(f"[{self.provider_name}] Upload error for {object_name}: {e}")
            raise exceptions.CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file to {self.provider_name} storage",
                error_code=constants.ErrorCode.INTERNAL_SERVER_ERROR,
            )

    async def upload_object(
        self,
        bucket_name: str,
        object_name: str,
        object_bytes: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        await self._ensure_bucket_exists(bucket_name)
        with io.BytesIO(object_bytes) as data_stream:
            try:
                await self.client.put_object(
                    bucket_name=bucket_name,
                    object_name=object_name,
                    data=data_stream,
                    length=len(object_bytes),
                    content_type=content_type,
                )
                logger.info(f"[{self.provider_name}] Object uploaded: s3://{bucket_name}/{object_name}")
            except Exception as e:
                logger.error(f"[{self.provider_name}] Upload error for {object_name}: {e}")
                raise exceptions.CustomException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to upload file to storage",
                    error_code=constants.ErrorCode.INTERNAL_SERVER_ERROR,
                )

    async def upload_dataset(self, bucket_name: str, object_name: str, parquet_buffer: io.BytesIO) -> None:
        await self._ensure_bucket_exists(bucket_name)
        try:
            await self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=parquet_buffer,
                length=len(parquet_buffer.getvalue()),
                content_type="application/x-parquet",
            )
            logger.info(f"[{self.provider_name}] Dataset uploaded: s3://{bucket_name}/{object_name}")
        except Exception as e:
            logger.error(f"[{self.provider_name}] Upload dataset error for {object_name}: {e}")
            raise exceptions.CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload dataset to storage",
                error_code=constants.ErrorCode.INTERNAL_SERVER_ERROR,
            )

    async def get_object(
        self,
        arg1: str,
        arg2: str | None = None,
        bucket_name: str | None = None,
    ) -> io.BytesIO:
        target_bucket, target_object = self._resolve_bucket_and_object(arg1, arg2, bucket_name)
        response = None
        try:
            response = await self.client.get_object(target_bucket, target_object)
            data_bytes = await response.read()
            buffer = io.BytesIO(data_bytes)
            buffer.seek(0)
            return buffer
        except S3Error as e:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Object not found: {e.message}",
                error_code=constants.ErrorCode.NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"[{self.provider_name}] Get object error for {target_object}: {e}")
            raise exceptions.CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving object from {self.provider_name} storage",
                error_code=constants.ErrorCode.INTERNAL_SERVER_ERROR,
            )
        finally:
            if response:
                try:
                    response.close()
                    if hasattr(response, "release"):
                        response.release()
                except Exception:
                    pass

    async def remove_object(
        self,
        arg1: str,
        arg2: str | None = None,
        bucket_name: str | None = None,
    ) -> bool:
        target_bucket, target_object = self._resolve_bucket_and_object(arg1, arg2, bucket_name)
        try:
            await self.client.remove_object(target_bucket, target_object)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return True
            logger.error(f"[{self.provider_name}] Remove object error for {target_object}: {e}")
            raise exceptions.CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to remove object from {self.provider_name} storage",
                error_code=constants.ErrorCode.INTERNAL_SERVER_ERROR,
            )

    async def check_object_exists(
        self,
        arg1: str,
        arg2: str | None = None,
        bucket_name: str | None = None,
    ) -> bool:
        target_bucket, target_object = self._resolve_bucket_and_object(arg1, arg2, bucket_name)
        try:
            await self.client.stat_object(target_bucket, target_object)
            return True
        except Exception:
            return False

    async def get_url(
        self,
        arg1: str,
        arg2: str | None = None,
        bucket_name: str | None = None,
        expires_sec: int = 7 * 24 * 3600,
    ) -> str:
        target_bucket, target_object = self._resolve_bucket_and_object(arg1, arg2, bucket_name)
        try:
            return await self.client.presigned_get_object(
                bucket_name=target_bucket,
                object_name=target_object,
                expires=expires_sec,
            )
        except Exception as e:
            logger.error(f"[{self.provider_name}] Presigned URL error for {target_object}: {e}")
            raise exceptions.CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate download URL",
                error_code=constants.ErrorCode.INTERNAL_SERVER_ERROR,
            )

    async def copy_object(self, source_bucket: str, source_key: str, dest_bucket: str, dest_key: str) -> None:
        if not await self.client.bucket_exists(source_bucket):
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source bucket {source_bucket} not found",
                error_code=constants.ErrorCode.NOT_FOUND,
            )
        await self._ensure_bucket_exists(dest_bucket)
        try:
            await self.client.copy_object(
                bucket_name=dest_bucket,
                object_name=dest_key,
                source=CopySource(source_bucket, source_key),
            )
        except Exception as e:
            logger.error(f"[{self.provider_name}] Copy error for {source_key}: {e}")
            raise exceptions.CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to copy object in storage",
                error_code=constants.ErrorCode.INTERNAL_SERVER_ERROR,
            )

    async def move_model(self, source_bucket: str, source_model: str, dest_bucket: str, dest_model: str) -> None:
        await self.copy_object(source_bucket, source_model, dest_bucket, dest_model)
        await self.client.remove_object(source_bucket, source_model)

    async def download_model(self, bucket_name: str, object_name: str, local_temp_path: str) -> str:
        try:
            os.makedirs(os.path.dirname(local_temp_path), exist_ok=True)
            await self.client.fget_object(bucket_name, object_name, local_temp_path)
            logger.info(f"[{self.provider_name}] Downloaded model to {local_temp_path}")
            return local_temp_path
        except Exception as e:
            logger.error(f"[{self.provider_name}] Download error: {e}")
            raise exceptions.CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to download model to local system",
                error_code=constants.ErrorCode.INTERNAL_SERVER_ERROR,
            )

    async def list_objects(self, bucket_name: str | None = None) -> None:
        target_bucket = bucket_name or self.default_bucket
        try:
            async for obj in self.client.list_objects(target_bucket, recursive=True):
                logger.info(f"[{self.provider_name}] {obj.object_name}")
        except Exception as e:
            logger.error(f"[{self.provider_name}] List objects error: {e}")

    async def close(self) -> None:
        if self.client:
            try:
                await self.client.close_session()
                logger.info(f"[{self.provider_name}] Client session closed successfully")
            except Exception as e:
                logger.debug(f"[{self.provider_name}] Error closing session: {e}")


# MinIO Service (Internal Cluster Storage)
minio_service = S3Storage(
    endpoint=settings.MINIO.ENDPOINT,
    access_key=settings.MINIO.ACCESS_KEY,
    secret_key=settings.MINIO.SECRET_KEY,
    is_secure=settings.PROJECT.ENVIRONMENT != "development",
    provider_name="MinIO",
)

# Backblaze Service (Cloud Storage for User Assets)
backblaze_service = S3Storage(
    endpoint=settings.BACKBLAZE.ENDPOINT_URL,
    access_key=settings.BACKBLAZE.ACCESS_KEY_ID,
    secret_key=settings.BACKBLAZE.SECRET_ACCESS_KEY,
    default_bucket=settings.BACKBLAZE.BUCKET_NAME,
    is_secure=True,
    provider_name="Backblaze",
)
