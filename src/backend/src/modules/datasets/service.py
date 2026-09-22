# Standard Libraries
import io
import re
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
import numpy as np
import pyarrow.parquet as pq
from fastapi import status, UploadFile

# Local Libraries
from src.core import exceptions
from src.shared import constants, minio_service
from src.modules.datasets.schemas import DatasetResponse, DatasetAdminResponse, DatasetCreate, DataTypeEnum, DatasetUpdate, TrainingConfig
from src.modules.datasets.repository import DatasetRepository


class DatasetService:
    def __init__(self, repo: DatasetRepository):
        self.repo = repo

    @staticmethod
    def _is_dataset_public(dataset: dict) -> bool:
        """
        Check if dataset is public (public is True or legacy dataset with userId '0')
        """
        return dataset.get("public") is True or dataset.get("userId") == "0"

    def _has_read_permission(self, dataset: dict, current_user: dict) -> bool:
        """
        Check if user has permission to read/view/preview/train dataset
        """
        if current_user.get("role") == "admin":
            return True
        if dataset.get("userId") == current_user.get("_id"):
            return True
        return self._is_dataset_public(dataset)

    def _has_write_permission(self, dataset: dict, current_user: dict) -> bool:
        """
        Check if user has permission to update/delete dataset.
        Only dataset creator has permission.
        For legacy dataset (userId '0'), only admin has permission.
        """
        if current_user.get("role") == "admin":
            return True
        return dataset.get("userId") == current_user.get("_id") and dataset.get("userId") != "0"

    """
    Get All Datasets For A User
    """
    async def get_user_datasets(self, user_id: str, current_page: int, page_size: int, public: bool = False, data_type: str | None = None, sort_name: str | None = None, sort_time: str | None = None) -> tuple[list[DatasetResponse], dict]:
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
            public=public,
            data_type=data_type,
            sort_params=db_sort
        )

        for doc in raw_datasets:
            if doc.get("userId") == "0":
                doc["public"] = True

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

        for doc in raw_datasets:
            if doc.get("userId") == "0":
                doc["public"] = True

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
    async def get_dataset_detail(self, current_user: dict, dataset_id: str) -> DatasetResponse:
        try:
            oid = ObjectId(dataset_id)
        except InvalidId:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid dataset ID format",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        dataset = await self.repo.get_dataset_by_id(dataset_id=oid)

        if not dataset or not self._has_read_permission(dataset, current_user):
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or access denied",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        if dataset.get("userId") == "0":
            dataset["public"] = True

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
        user_id = str(current_user["_id"])

        try:
            file_content_bytes = await file.read()
        except Exception as e:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error when downloading file",
                error_code=constants.ErrorCode.BAD_REQUEST
            )

        # Handle thumbnail
        thumbnail_base64 = None
        if thumbnail_file:
            if not thumbnail_file.content_type.startswith("image/"):
                raise exceptions.CustomException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only image file uploads are supported for thumbnail",
                    error_code=constants.ErrorCode.BAD_REQUEST
                )
            try:
                thumbnail_data = await thumbnail_file.read()
                thumbnail_base64 = base64.b64encode(thumbnail_data).decode('utf-8')
            except Exception as e:
                raise exceptions.CustomException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Error reading thumbnail file",
                    error_code=constants.ErrorCode.BAD_REQUEST
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
                raise exceptions.CustomException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=str(e),
                    error_code=constants.ErrorCode.BAD_REQUEST
                )

            # Upload MinIO
            object_name = f"{user_id}/{storage_place}.parquet"
            await minio_service.upload_dataset(bucket_name, object_name, parquet_buffer)
        else:
            # Handle IMAGE or TEXT types
            file_extension = file.filename.split(".")[-1] if "." in file.filename else "bin"
            object_name = f"{user_id}/{storage_place}.{file_extension}"

            await minio_service.upload_object(bucket_name, object_name, file_content_bytes)

        # Save Database
        now = datetime.now(timezone.utc).timestamp()
        data_doc = {
            "dataName": payload.dataName,
            "dataType": payload.dataType.value,
            "public": payload.public,
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
    async def update_dataset_info(self, current_user: dict, dataset_id: str, payload: DatasetUpdate, thumbnail_file: UploadFile | None = None) -> DatasetResponse:
        try:
            oid = ObjectId(dataset_id)
        except InvalidId:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid dataset ID format",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        dataset = await self.repo.get_dataset_by_id(dataset_id=oid)
        if not dataset:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        if not self._has_write_permission(dataset, current_user):
            raise exceptions.CustomException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to update this dataset",
                error_code=constants.ErrorCode.FORBIDDEN
            )

        update_data = payload.model_dump(exclude_none=True)

        if thumbnail_file:
            if not thumbnail_file.content_type.startswith("image/"):
                raise exceptions.CustomException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only image file uploads are supported for thumbnail",
                    error_code=constants.ErrorCode.BAD_REQUEST
                )
            try:
                thumbnail_data = await thumbnail_file.read()
                update_data["thumbnail"] = base64.b64encode(thumbnail_data).decode('utf-8')
            except Exception as e:
                raise exceptions.CustomException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Error reading thumbnail file",
                    error_code=constants.ErrorCode.BAD_REQUEST
                )

        if not update_data:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No data is provided for updating",
                error_code=constants.ErrorCode.BAD_REQUEST
            )

        update_data["latestUpdate"] = datetime.now(timezone.utc).timestamp()

        is_updated = await self.repo.update_dataset(oid, update_data)

        if not is_updated:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or access denied",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        return await self.get_dataset_detail(current_user, dataset_id)

    """
    Soft Delete Dataset
    """
    async def delete_dataset(self, current_user: dict, dataset_id: str) -> None:
        try:
            oid = ObjectId(dataset_id)
        except InvalidId:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid dataset ID format",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        dataset = await self.repo.get_dataset_by_id(dataset_id=oid)
        if not dataset:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        if not self._has_write_permission(dataset, current_user):
            raise exceptions.CustomException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this dataset",
                error_code=constants.ErrorCode.FORBIDDEN
            )

        is_deleted = await self.repo.delete_dataset(oid)

        if not is_deleted:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or access denied",
                error_code=constants.ErrorCode.NOT_FOUND
            )

    @staticmethod
    def analyze_column_for_target(series: pd.Series, threshold_unique=50) -> str:
        try:
            clean_series = series.dropna()
            if clean_series.empty: return "none"

            if pd.api.types.is_datetime64_any_dtype(clean_series) or pd.api.types.is_timedelta64_dtype(clean_series):
                return "none"

            series_numeric = pd.to_numeric(clean_series, errors='coerce').dropna()
            is_numeric_column = len(series_numeric) >= 0.5 * len(clean_series)

            if not is_numeric_column:
                return "classification"
            else:
                clean_series = series_numeric

            if clean_series.nunique() <= 2:
                return "classification"

            is_float = not np.all(np.isclose(clean_series % 1, 0))
            if is_float:
                return "regression"

            num_unique = clean_series.nunique()

            if num_unique > 0.9 * len(clean_series):
                return "regression"

            if num_unique <= threshold_unique:
                return "both"

            return "regression"
        except Exception as e:
            return "none"

    """
    Get Dataset Features
    """
    async def get_dataset_features(self, current_user: dict, dataset_id: str, problem_type: str, num_row: int = 1000) -> dict:
        try:
            oid = ObjectId(dataset_id)
        except InvalidId:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid dataset ID format",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        dataset = await self.repo.get_dataset_by_id(oid, include_data_link=True)
        if not dataset or not self._has_read_permission(dataset, current_user):
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or access denied",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        data_link = dataset.get("data_link")
        if not data_link:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found, access denied, or data link missing",
                error_code=constants.ErrorCode.NOT_FOUND
            )
            
        bucket_name = data_link.get("bucket_name")
        object_name = data_link.get("object_name")

        pattern = r"^(?i:id|stt|no|key|code|uuid|guid)$|(?i:.*_id)$|^ID_.*$"
        features = {}

        try:
            response_buffer = await minio_service.get_object(bucket_name, object_name)
            
            parquet_file = pq.ParquetFile(response_buffer)
            schema_names = parquet_file.schema.names

            table = parquet_file.read_row_group(0)
            df_preview = table.to_pandas().head(num_row)

            for col_name in schema_names:
                if re.match(pattern, col_name):
                    features[col_name] = False
                    continue

                series = df_preview[col_name]
    
                if series.isnull().all() or series.nunique() <= 1:
                    features[col_name] = False
                    continue

                suggested_type = self.analyze_column_for_target(series)

                if problem_type == "classification":
                    if suggested_type in ["classification", "both"]:
                        features[col_name] = True
                    else:
                        features[col_name] = False
                elif problem_type == "regression":
                    if suggested_type in ["regression", "both"]:
                        features[col_name] = True
                    else:
                        features[col_name] = False
                else:
                    features[col_name] = False

            return features
        except Exception as e:
            print(f"Exception when getting dataset features: {str(e)}")
            raise exceptions.CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process features: {str(e)}",
                error_code=constants.ErrorCode.INTERNAL_SERVER_ERROR
            )

    """
    Get Data To Preview
    """
    async def get_data_preview(self, current_user: dict, dataset_id: str, num_rows: int = 50) -> tuple[list[dict], int]:
        try:
            oid = ObjectId(dataset_id)
        except InvalidId:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid dataset ID format",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        dataset = await self.repo.get_dataset_by_id(oid, include_data_link=True)
        if not dataset or not self._has_read_permission(dataset, current_user):
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or access denied",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        data_link = dataset.get("data_link")
        if not data_link:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found, access denied, or data link missing",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        bucket_name = data_link.get("bucket_name")
        object_name = data_link.get("object_name")

        try:
            response_buffer = await minio_service.get_object(bucket_name, object_name)
            df_retrieved = pd.read_parquet(response_buffer)

            total_rows = len(df_retrieved)
            df_preview = df_retrieved.head(num_rows)

            # replace NaN with None for JSON serialization
            df_preview = df_preview.replace({np.nan: None})

            return df_preview.to_dict(orient='records'), total_rows
        except Exception as e:
            print(f"Exception when getting dataset preview: {str(e)}")
            raise exceptions.CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read dataset: {str(e)}",
                error_code=constants.ErrorCode.INTERNAL_SERVER_ERROR
            )

    """
    Create Metadata Of Job
    """
    async def create_metadata_job(self, current_user: dict, dataset_id: str, config: TrainingConfig) -> str:
        try:
            oid = ObjectId(dataset_id)
        except InvalidId:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid dataset ID format",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        data_doc = await self.repo.get_dataset_by_id(oid)
        if not data_doc or not self._has_read_permission(data_doc, current_user):
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or access denied",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        # Save Job
        now = datetime.now(timezone.utc).timestamp()
        job_doc = {
            "config": config,
            "data": {
                "id": dataset_id,
                "name": data_doc.get("dataName")
            },
            "user": {
                "id": str(current_user.get("_id")),
                "name": current_user.get("username")
            },
            "status": 0,
            "activate": 0,
            "create_at": now
        }

        inserted_doc = await self.repo.create_job(job_doc)
        inserted_doc["_id"] = str(inserted_doc["_id"])

        return inserted_doc["_id"]
