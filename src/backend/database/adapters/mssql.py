from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from .base import BaseDatabaseAdapter, DatabaseConfig


class MSSQLAdapter(BaseDatabaseAdapter):
    """Adapter kết nối Microsoft SQL Server (MSSQL) qua pyodbc."""

    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        if not self.config.port:
            self.config.port = 1433

    def get_connection_url(self) -> str:
        user = quote_plus(self.config.user or "")
        password = quote_plus(self.config.password or "")
        db = quote_plus(self.config.database)
        
        # Lấy tên ODBC driver từ extra_params (mặc định ODBC Driver 17 for SQL Server)
        driver = (
            self.config.extra_params.get("driver")
            or self.config.extra_params.get("odbc_driver")
            or "ODBC Driver 17 for SQL Server"
        )
        driver_param = quote_plus(str(driver))

        url = f"mssql+pyodbc://{user}:{password}@{self.config.host}:{self.config.port}/{db}?driver={driver_param}"

        # Bổ sung tùy chọn TrustServerCertificate nếu có
        trust_cert = self.config.extra_params.get("trust_server_certificate") or self.config.extra_params.get("TrustServerCertificate")
        if trust_cert is not None:
            url += f"&TrustServerCertificate={str(trust_cert).lower()}"

        return url

    def create_engine(self) -> Engine:
        url = self.get_connection_url()
        return create_engine(
            url,
            connect_args={"connect_timeout": self.config.connect_timeout},
            pool_pre_ping=True,
        )

    def quote_identifier(self, identifier: str) -> str:
        escaped = identifier.replace("]", "]]")
        return f"[{escaped}]"

    def build_select_query(self, table_name: str, limit: int = 50000) -> str:
        """MSSQL dùng SELECT TOP thay vì LIMIT"""
        safe_table = self.get_full_table_name(table_name)
        return f"SELECT TOP ({int(limit)}) * FROM {safe_table}"

