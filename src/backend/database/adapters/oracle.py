from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from .base import BaseDatabaseAdapter, DatabaseConfig


class OracleAdapter(BaseDatabaseAdapter):
    """Adapter kết nối Oracle Database qua oracledb."""

    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        if not self.config.port:
            self.config.port = 1521

    def get_connection_url(self) -> str:
        user = quote_plus(self.config.user or "")
        password = quote_plus(self.config.password or "")
        sid = self.config.extra_params.get("sid")
        service_name = self.config.extra_params.get("service_name") or self.config.database
        if sid:
            # Với SID, SQLAlchemy yêu cầu đặt trực tiếp vào path của database
            path = f"/{quote_plus(sid)}"
        elif service_name:
            # Với Service Name, SQLAlchemy yêu cầu truyền qua query parameter
            path = f"/?service_name={quote_plus(service_name)}"
        else:
            path = ""
        return f"oracle+oracledb://{user}:{password}@{self.config.host}:{self.config.port}{path}"

    def create_engine(self) -> Engine:
        url = self.get_connection_url()
        return create_engine(
            url,
            pool_pre_ping=True,
        )

    def get_test_query(self) -> str:
        return "SELECT 1 FROM DUAL"

    def quote_identifier(self, identifier: str) -> str:
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'

    def build_select_query(self, table_name: str, limit: int = 50000) -> str:
        """Oracle 12c+ dùng cú pháp FETCH FIRST n ROWS ONLY thay cho LIMIT"""
        safe_table = self.get_full_table_name(table_name)
        return f"SELECT * FROM {safe_table} FETCH FIRST {int(limit)} ROWS ONLY"

