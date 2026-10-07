import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from .base import BaseDatabaseAdapter, DatabaseConfig, DatabaseConnectionError


class DuckDBAdapter(BaseDatabaseAdapter):
    """Adapter kết nối DuckDB (hỗ trợ cả file .duckdb và in-memory) qua duckdb-engine."""

    def __init__(self, config: DatabaseConfig):
        super().__init__(config)

    def get_connection_url(self) -> str:
        db_path = self.config.database
        if db_path == ":memory:":
            return "duckdb:///:memory:"
        if db_path.startswith("/"):
            return f"duckdb:////{db_path.lstrip('/')}"
        return f"duckdb:///{db_path}"

    def create_engine(self) -> Engine:
        if self.config.database != ":memory:" and not os.path.exists(self.config.database):
            raise DatabaseConnectionError(
                f"Tệp CSDL DuckDB '{self.config.database}' không tồn tại trên hệ thống máy chủ."
            )
        url = self.get_connection_url()
        is_read_only = self.config.extra_params.get("read_only", True) if self.config.database != ":memory:" else False
        connect_args = {"read_only": is_read_only} if is_read_only else {}
        return create_engine(url, connect_args=connect_args) if connect_args else create_engine(url)

    def quote_identifier(self, identifier: str) -> str:
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'

