import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from .base import BaseDatabaseAdapter, DatabaseConfig, DatabaseConnectionError


class SQLiteAdapter(BaseDatabaseAdapter):
    """Adapter kết nối CSDL SQLite (tương thích cả file vật lý và in-memory)."""

    def __init__(self, config: DatabaseConfig):
        super().__init__(config)

    def get_connection_url(self) -> str:
        db_path = self.config.database
        if db_path == ":memory:":
            return "sqlite:///:memory:"
        if db_path.startswith("/"):
            # Đường dẫn tuyệt đối chuẩn trong SQLAlchemy cần 4 dấu gạch chéo
            return f"sqlite:////{db_path.lstrip('/')}"
        return f"sqlite:///{db_path}"

    def create_engine(self) -> Engine:
        if self.config.database != ":memory:" and not os.path.exists(self.config.database):
            raise DatabaseConnectionError(
                f"Tệp CSDL SQLite '{self.config.database}' không tồn tại trên hệ thống máy chủ."
            )

        url = self.get_connection_url()
        if self.config.database == ":memory:":
            return create_engine(
                url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
        )

    def quote_identifier(self, identifier: str) -> str:
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'

