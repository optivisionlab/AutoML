from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from src.adapters.base import BaseDatabaseAdapter, DatabaseConfig


class ClickHouseAdapter(BaseDatabaseAdapter):
    """ClickHouse adapter (clickhouse-connect)."""

    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        if not self.config.port:
            self.config.port = 8123  # Default ClickHouse HTTP port

    def get_connection_url(self) -> str:
        user = quote_plus(self.config.user or "default")
        password = quote_plus(self.config.password or "")
        db = quote_plus(self.config.database)
        return f"clickhousedb+connect://{user}:{password}@{self.config.host}:{self.config.port}/{db}"

    def create_engine(self) -> Engine:
        url = self.get_connection_url()
        return create_engine(
            url,
            connect_args={"connect_timeout": self.config.connect_timeout},
            pool_pre_ping=True,
        )

    def quote_identifier(self, identifier: str) -> str:
        escaped = identifier.replace('`', '``')
        return f"`{escaped}`"
