from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from .base import BaseDatabaseAdapter, DatabaseConfig


class HiveAdapter(BaseDatabaseAdapter):
    """Adapter kết nối Apache Hive qua PyHive."""

    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        if not self.config.port:
            self.config.port = 10000  # Default HiveServer2 port

    def get_connection_url(self) -> str:
        user = quote_plus(self.config.user or "")
        password = quote_plus(self.config.password or "")
        if user and password:
            auth_part = f"{user}:{password}@"
        elif user:
            auth_part = f"{user}@"
        else:
            auth_part = ""
        db = quote_plus(self.config.database or "default")

        auth_param = self.config.extra_params.get("auth")
        query_str = f"?auth={quote_plus(auth_param)}" if auth_param else ""

        return f"hive://{auth_part}{self.config.host}:{self.config.port}/{db}{query_str}"

    def create_engine(self) -> Engine:
        url = self.get_connection_url()
        return create_engine(url)

    def quote_identifier(self, identifier: str) -> str:
        escaped = identifier.replace('`', '``')
        return f"`{escaped}`"
