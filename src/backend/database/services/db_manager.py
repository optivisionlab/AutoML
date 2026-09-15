import io
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any
from ..adapters import DatabaseAdapterFactory, DatabaseConfig

class DatabaseManager:
    """Tầng trung gian (Intermediary / Facade) xử lý nghiệp vụ kết nối và import dữ liệu"""

    @staticmethod
    def test_connection_and_get_tables(config: DatabaseConfig) -> List[str]:
        """Tạo adapter -> Lấy bảng -> Tự động đóng Engine qua Context Manager"""
        with DatabaseAdapterFactory.create(config) as adapter:
            adapter.test_connection()
            return adapter.get_tables()

    @staticmethod
    async def import_table_to_dataset(
        config: DatabaseConfig,
        table_name: str,
        data_name: str,
        user_id: str,
        username: str,
        role: str,
        minio_storage: Any,
        db_mongo: Any,
        limit: int = 50000
    ) -> Dict[str, Any]:
        """Trích xuất bảng -> Nén Parquet -> Tải lên MinIO -> Ghi bản ghi vào MongoDB"""

        # 1. Kéo dữ liệu bằng Adapter (tự động dispose khi thoát khối with)
        with DatabaseAdapterFactory.create(config) as adapter:
            df = adapter.fetch_table_to_dataframe(table_name=table_name, limit=limit)

        if df.empty:
            raise ValueError(f"Bảng dữ liệu '{table_name}' đang rỗng.")

        # 2. Chuẩn hóa tên cột & ghi vào buffer Parquet in-memory
        df.columns = df.columns.str.strip()
        parquet_buffer = io.BytesIO()
        df.to_parquet(parquet_buffer, index=False)
        parquet_buffer.seek(0)

        # 3. Đẩy file Parquet vào MinIO
        storage_user_id = "0" if role == "admin" else user_id
        storage_id = str(uuid.uuid4())
        object_name = f"{storage_user_id}/{storage_id}.parquet"

        minio_storage.uploaded_dataset(
            bucket_name="dataset",
            object_name=object_name,
            parquet_buffer=parquet_buffer
        )

        # 4. Ghi metadata vào MongoDB tbl_Data
        now = datetime.now(timezone.utc).timestamp()
        data_to_insert = {
            "dataName": data_name,
            "dataType": "table",
            "data_link": {
                "bucket_name": "dataset",
                "object_name": object_name
            },
            "latestUpdate": now,
            "createDate": now,
            "userId": user_id,
            "username": username,
            "role": role,
            "activate": 1
        }
        await db_mongo.tbl_Data.insert_one(data_to_insert)
        data_to_insert["_id"] = str(data_to_insert["_id"])

        return data_to_insert
