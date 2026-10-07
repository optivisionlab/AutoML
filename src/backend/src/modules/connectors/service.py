# Standard Libraries
import io
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Any

# Third-party Libraries
import pandas as pd
from fastapi import status

# Local Libraries
from src.core import exceptions
from src.shared import constants, minio_service
from src.modules.connectors.adapters import DatabaseAdapterFactory, DatabaseAdapterError, DatabaseConfig
from src.modules.connectors.schemas import DatabaseConnection, TableInfoRequest, ImportTableRequest
from src.modules.datasets.schemas import DataTypeEnum, DatasetResponse
from src.modules.datasets.repository import DatasetRepository


def _bad_request(detail: str) -> exceptions.CustomException:
    return exceptions.CustomException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
        error_code=constants.ErrorCode.BAD_REQUEST,
    )


class ConnectorService:
    def __init__(self, repo: DatasetRepository):
        self.repo = repo

    @staticmethod
    def _list_tables(config: DatabaseConfig) -> list[str]:
        with DatabaseAdapterFactory.create(config) as adapter:
            adapter.test_connection()
            return adapter.get_tables()

    @staticmethod
    def _table_info(config: DatabaseConfig, table_name: str, limit: int) -> dict[str, Any]:
        with DatabaseAdapterFactory.create(config) as adapter:
            schema_info = adapter.get_table_schema(table_name)
            df = adapter.fetch_table_to_dataframe(table_name=table_name, limit=limit)

        # NaN / NaT / None are not JSON serializable
        preview = [
            {key: (None if pd.isna(value) else value) for key, value in row.items()}
            for row in df.to_dict(orient="records")
        ]
        return {
            "table_name": table_name,
            "columns": schema_info.get("columns", []),
            "preview_data": preview,
            "preview_count": len(preview),
        }

    @staticmethod
    def _extract_table_to_parquet(config: DatabaseConfig, table_name: str, limit: int) -> io.BytesIO:
        with DatabaseAdapterFactory.create(config) as adapter:
            df = adapter.fetch_table_to_dataframe(table_name=table_name, limit=limit)

        if df.empty:
            raise ValueError(f"Table '{table_name}' is empty.")

        df.columns = df.columns.astype(str).str.strip()
        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False)
        buffer.seek(0)
        return buffer

    @staticmethod
    async def _run(func, *args) -> Any:
        """
        Run a blocking SQLAlchemy call off the event loop and map adapter errors to HTTP 400
        """
        try:
            return await asyncio.to_thread(func, *args)
        except (DatabaseAdapterError, ValueError) as e:
            raise _bad_request(str(e))

    async def connect(self, conn: DatabaseConnection) -> list[str]:
        return await self._run(self._list_tables, conn.to_config())

    async def get_table_info(self, req: TableInfoRequest) -> dict[str, Any]:
        return await self._run(self._table_info, req.to_config(), req.table_name, req.limit)

    async def import_table(self, current_user: dict, req: ImportTableRequest, limit: int = 50000) -> DatasetResponse:
        parquet_buffer = await self._run(self._extract_table_to_parquet, req.to_config(), req.table_name, limit)

        user_id = str(current_user["_id"])
        bucket_name = "dataset"
        object_name = f"{user_id}/{uuid.uuid4()}.parquet"
        await minio_service.upload_dataset(bucket_name, object_name, parquet_buffer)

        now = datetime.now(timezone.utc).timestamp()
        data_doc = {
            "dataName": req.data_name,
            "dataType": DataTypeEnum.TABLE.value,
            "public": req.public,
            "data_link": {"bucket_name": bucket_name, "object_name": object_name},
            "latestUpdate": now,
            "createDate": now,
            "userId": user_id,
            "username": current_user.get("username", "unknown"),
            "role": current_user.get("role", "user"),
            "activate": 1,
            "thumbnail": None,
            "description": req.description,
        }

        inserted_doc = await self.repo.create_dataset(data_doc)
        inserted_doc["_id"] = str(inserted_doc["_id"])
        return DatasetResponse(**inserted_doc)
