from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from .base import BaseDatabaseAdapter, DatabaseConfig


class SnowflakeAdapter(BaseDatabaseAdapter):
    """Adapter kết nối Snowflake Data Warehouse qua snowflake-sqlalchemy."""

    def __init__(self, config: DatabaseConfig):
        super().__init__(config)

    def get_connection_url(self) -> str:
        user = quote_plus(self.config.user or "")
        password = quote_plus(self.config.password or "")
        account = (
            self.config.extra_params.get("account")
            or (self.config.host if self.config.host and self.config.host != "localhost" else "")
        )
        db = quote_plus(self.config.database)
        schema = self.config.schema_name or self.config.extra_params.get("schema")

        path = f"/{db}"
        if schema:
            path = f"/{db}/{quote_plus(schema)}"

        query_params = []
        warehouse = self.config.extra_params.get("warehouse")
        if warehouse:
            query_params.append(f"warehouse={quote_plus(str(warehouse))}")

        role = self.config.extra_params.get("role")
        if role:
            query_params.append(f"role={quote_plus(str(role))}")

        query_str = f"?{'&'.join(query_params)}" if query_params else ""
        return f"snowflake://{user}:{password}@{account}{path}{query_str}"

    def create_engine(self) -> Engine:
        url = self.get_connection_url()
        return create_engine(url, pool_pre_ping=True)

    def quote_identifier(self, identifier: str) -> str:
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'

