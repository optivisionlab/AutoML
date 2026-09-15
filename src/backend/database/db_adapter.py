import warnings
from typing import List
import pandas as pd
from .adapters import DatabaseAdapterFactory, DatabaseConfig

class DatabaseAdapter:
    """Wrapper tương thích ngược (Deprecated) chuyển tiếp sang DatabaseAdapterFactory"""
    def __init__(self, db_type: str, host: str, port: int, user: str, password: str, database: str):
        warnings.warn(
            "DatabaseAdapter trực tiếp đã bị deprecated. Hãy chuyển sang sử dụng DatabaseManager hoặc DatabaseAdapterFactory.",
            DeprecationWarning,
            stacklevel=2
        )
        self.config = DatabaseConfig(
            db_type=db_type,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )

    def test_connection_and_get_tables(self) -> List[str]:
        with DatabaseAdapterFactory.create(self.config) as adapter:
            return adapter.get_tables()

    def fetch_table_to_dataframe(self, table_name: str, limit: int = 50000) -> pd.DataFrame:
        with DatabaseAdapterFactory.create(self.config) as adapter:
            return adapter.fetch_table_to_dataframe(table_name=table_name, limit=limit)
