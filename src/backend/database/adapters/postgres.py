from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from .base import BaseDatabaseAdapter, DatabaseConfig
class PostgresAdapter(BaseDatabaseAdapter):
    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        if not self.config.port:
            self.config.port = 5432
        if not self.config.schema_name:
            self.config.schema_name = "public"

    def get_connection_url(self) -> str:
        user = quote_plus(self.config.user or "")
        password = quote_plus(self.config.password or "")
        db = quote_plus(self.config.database)
        return f"postgresql+psycopg2://{user}:{password}@{self.config.host}:{self.config.port}/{db}"

    def create_engine(self) -> Engine:
        url = self.get_connection_url()
        connect_args = {"connect_timeout": self.config.connect_timeout}
        if self.config.schema_name:
            connect_args["options"] = f"-csearch_path={self.config.schema_name}"

        return create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    
    def quote_identifier(self, identifier: str) -> str:
        return f'"{identifier}"'

