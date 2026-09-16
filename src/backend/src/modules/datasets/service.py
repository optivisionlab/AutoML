# Standard Libraries
import io
import csv
import uuid
import math
import base64
import asyncio
import pandas as pd
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime, timezone

# Third-party Libraries
from fastapi import status, UploadFile

# Local Libraries
from src.core.exceptions import CustomException
from src.shared.constants import ErrorCode
from src.modules.datasets.schemas import DatasetResponse, DatasetAdminResponse, DatasetCreate, DataTypeEnum, DatasetUpdate
from src.modules.datasets.repository import DatasetRepository
from src.shared.minio_client import minio_client


class DatasetService:
    def __init__(self, repo: DatasetRepository):
        self.repo = repo

    """
    Get All Datasets For A User
    """
    async def get_user_datasets(self, user_id: str, current_page: int, page_size: int, data_type: str | None = None, sort_name: str | None = None, sort_time: str | None = None) -> tuple[list[DatasetResponse], dict]:
        skip = (current_page - 1) * page_size

        db_sort = []

        # Sort by dataName
        if sort_name:
            db_sort.append(("dataName", 1 if sort_name == "asc" else -1))

        # Sort by latestUpdate
        if sort_time:
            db_sort.append(("latestUpdate", 1 if sort_time == "asc" else -1))

        raw_datasets, total_items = await self.repo.get_datasets_with_count(
            user_id=user_id,
            skip=skip,
            limit=page_size,
            data_type=data_type,
            sort_params=db_sort
        )

        formatted_datasets = [DatasetResponse(**doc) for doc in raw_datasets]

        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0
        meta = {
            "total_items": total_items,
            "current_page": current_page,
            "page_size": page_size,
            "total_pages": total_pages
        }

        return formatted_datasets, meta

    """
    Get All Datasets
    """
    async def get_all_datasets(self, current_page: int, page_size: int, data_type: str | None = None, sort_name: str | None = None, sort_time: str | None = None) -> tuple[list[DatasetResponse], dict]:
        skip = (current_page - 1) * page_size

        db_sort = []

        # Sort by dataName
        if sort_name:
            db_sort.append(("dataName", 1 if sort_name == "asc" else -1))

        # Sort by latestUpdate
        if sort_time:
            db_sort.append(("latestUpdate", 1 if sort_time == "asc" else -1))

        raw_datasets, total_items = await self.repo.get_all_datasets_with_count(
            skip=skip,
            limit=page_size,
            data_type=data_type,
            sort_params=db_sort
        )

        formatted_datasets = [DatasetAdminResponse(**doc) for doc in raw_datasets]

        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0
        meta = {
            "total_items": total_items,
            "current_page": current_page,
            "page_size": page_size,
            "total_pages": total_pages
        }

        return formatted_datasets, meta

    """
    Retrieve Detail Dataset
    """
    async def get_dataset_detail(self, user_id: str, dataset_id: str) -> DatasetResponse:
        try:
            dataset_id = ObjectId(dataset_id)
        except InvalidId:
            raise CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid dataset ID format",
                error_code=ErrorCode.BAD_REQUEST,
            )

        dataset = await self.repo.get_dataset_by_id(dataset_id=dataset_id, user_id=user_id)

        if not dataset:
            raise CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or access denied",
                error_code=ErrorCode.NOT_FOUND
            )

        dataset['_id'] = str(dataset['_id'])

        return DatasetResponse(**dataset)

    @staticmethod
    def _detect_csv_delimiter(file_bytes: bytes) -> str:
        sample_str = file_bytes[:2048].decode('utf-8', errors='ignore')
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample_str, delimiters=[',', ';', '\t', '|'])
            return dialect.delimiter
        except csv.Error:
            # Fallback
            return ','

    def _process_dataframe_to_parquet(self, file_bytes: bytes, filename: str) -> io.BytesIO:
        csv_stream = io.BytesIO(file_bytes)

        try:
            if filename.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(csv_stream)
            else:
                detected_delimiter = self._detect_csv_delimiter(file_bytes)
                df = pd.read_csv(
                    csv_stream,
                    sep=detected_delimiter,
                    engine='python',
                    on_bad_lines='skip'
                )
        except Exception as e:
            raise ValueError(f"Unable to read data file: {str(e)}")

        # Clean data
        df = df.loc[:, ~df.columns.str.contains('Unnamed')]
        df.dropna(axis=1, how='all', inplace=True)
        df.columns = df.columns.astype(str).str.strip()

        # Convert parquet format
        parquet_buffer = io.BytesIO()
        df.to_parquet(parquet_buffer, index=False)
        parquet_buffer.seek(0)

        return parquet_buffer

    """
    Upload Dataset
    """
    async def upload_and_process_dataset(self, current_user: dict, payload: DatasetCreate, file: UploadFile, thumbnail_file: UploadFile | None = None) -> DatasetResponse:
        username = current_user.get("username", "unknown")
        role = current_user.get("role", "user")
        user_id = "0" if role == "admin" else str(current_user["_id"])

        try:
            file_content_bytes = await file.read()
        except Exception as e:
            raise CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error when downloading file",
                error_code=ErrorCode.BAD_REQUEST
            )

        # Handle thumbnail
        thumbnail_base64 = None
        if thumbnail_file:
            if not thumbnail_file.content_type.startswith("image/"):
                raise CustomException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only image file uploads are supported for thumbnail",
                    error_code=ErrorCode.BAD_REQUEST
                )
            try:
                thumbnail_data = await thumbnail_file.read()
                thumbnail_base64 = base64.b64encode(thumbnail_data).decode('utf-8')
            except Exception as e:
                raise CustomException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Error reading thumbnail file",
                    error_code=ErrorCode.BAD_REQUEST
                )

        storage_place = uuid.uuid4()
        bucket_name = "dataset"
        
        if payload.dataType == DataTypeEnum.TABLE:
            try:
                parquet_buffer = await asyncio.to_thread(
                    self._process_dataframe_to_parquet,
                    file_bytes=file_content_bytes,
                    filename=file.filename
                )
            except ValueError as e:
                raise CustomException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=str(e),
                    error_code=ErrorCode.BAD_REQUEST
                )

            # Upload MinIO
            object_name = f"{user_id}/{storage_place}.parquet"
            await minio_client.upload_dataset(bucket_name, object_name, parquet_buffer)
        else:
            # Handle IMAGE or TEXT types
            file_extension = file.filename.split(".")[-1] if "." in file.filename else "bin"
            object_name = f"{user_id}/{storage_place}.{file_extension}"
            
            await minio_client.upload_object(bucket_name, object_name, file_content_bytes)

        # Save Database
        now = datetime.now(timezone.utc).timestamp()
        data_doc = {
            "dataName": payload.dataName,
            "dataType": payload.dataType.value,
            "data_link": {
                "bucket_name": bucket_name,
                "object_name": object_name
            },
            "latestUpdate": now,
            "createDate": now,
            "userId": user_id,
            "username": username,
            "role": role,
            "activate": 1,
            "thumbnail": thumbnail_base64,
            "description": payload.description
        }

        inserted_doc = await self.repo.create_dataset(data_doc)
        inserted_doc["_id"] = str(inserted_doc["_id"])

        return DatasetResponse(**inserted_doc)

    """
    Update Dataset Info
    """
    async def update_dataset_info(self, user_id: str, dataset_id: str, payload: DatasetUpdate, thumbnail_file: UploadFile | None = None) -> DatasetResponse:
        try:
            oid = ObjectId(dataset_id)
        except InvalidId:
            raise CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid dataset ID format",
                error_code=ErrorCode.BAD_REQUEST,
            )

        update_data = payload.model_dump(exclude_none=True)

        if thumbnail_file:
            if not thumbnail_file.content_type.startswith("image/"):
                raise CustomException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only image file uploads are supported for thumbnail",
                    error_code=ErrorCode.BAD_REQUEST
                )
            try:
                thumbnail_data = await thumbnail_file.read()
                update_data["thumbnail"] = base64.b64encode(thumbnail_data).decode('utf-8')
            except Exception as e:
                raise CustomException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Error reading thumbnail file",
                    error_code=ErrorCode.BAD_REQUEST
                )

        if not update_data:
            raise CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No data is provided for updating",
                error_code=ErrorCode.BAD_REQUEST
            )

        update_data["latestUpdate"] = datetime.now(timezone.utc).timestamp()

        is_updated = await self.repo.update_dataset(oid, user_id, update_data)

        if not is_updated:
            raise CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or access denied",
                error_code=ErrorCode.NOT_FOUND
            )

        return await self.get_dataset_detail(user_id, dataset_id)

    """
    Soft Delete Dataset
    """
    async def delete_dataset(self, current_user: dict, dataset_id: str) -> None:
        role = current_user.get("role", "user")
        user_id = "0" if role == "admin" else str(current_user["_id"])

        try:
            oid = ObjectId(dataset_id)
        except InvalidId:
            raise CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid dataset ID format",
                error_code=ErrorCode.BAD_REQUEST,
            )

        is_deleted = await self.repo.delete_dataset(oid, user_id)

        if not is_deleted:
            raise CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or access denied",
                error_code=ErrorCode.NOT_FOUND
            )
