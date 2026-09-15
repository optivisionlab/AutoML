from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from .base import BaseDatabaseAdapter, DatabaseConfig

class MySQLAdapter(BaseDatabaseAdapter):
    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        if not self.config.port:
            self.config.port = 3306

    def get_connection_url(self) -> str:
        user = quote_plus(self.config.user or "")
        password = quote_plus(self.config.password or "")
        db = quote_plus(self.config.database)
        return f"mysql+pymysql://{user}:{password}@{self.config.host}:{self.config.port}/{db}"

    def create_engine(self) -> Engine:
        url = self.get_connection_url()
        return create_engine(
            url,
            connect_args={
                "connect_timeout": self.config.connect_timeout,
                "charset": "utf8mb4"
            },
            pool_pre_ping=True
        )

    def quote_identifier(self, identifier: str) -> str:
        return f"`{identifier}`"
