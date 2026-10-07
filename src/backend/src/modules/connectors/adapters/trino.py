from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from .base import BaseDatabaseAdapter, DatabaseConfig


class TrinoAdapter(BaseDatabaseAdapter):
    """Adapter kết nối Presto / Trino Distributed Query Engine qua trino-python-client."""

    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        if not self.config.port:
            self.config.port = 8080
        if not self.config.schema_name:
            self.config.schema_name = "default"

    def get_connection_url(self) -> str:
        user = quote_plus(self.config.user or "admin")
        password = quote_plus(self.config.password or "")
        auth_part = f"{user}:{password}@" if password else f"{user}@"
        catalog = quote_plus(self.config.database)
        schema = quote_plus(self.config.schema_name)

        return f"trino://{auth_part}{self.config.host}:{self.config.port}/{catalog}/{schema}"

    def create_engine(self) -> Engine:
        url = self.get_connection_url()
        return create_engine(url)

    def quote_identifier(self, identifier: str) -> str:
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'
