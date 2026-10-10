import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from src.adapters.base import BaseDatabaseAdapter, DatabaseConfig, DatabaseConnectionError


class SQLiteAdapter(BaseDatabaseAdapter):
    """SQLite adapter, supports database files and in-memory databases."""

    def __init__(self, config: DatabaseConfig):
        super().__init__(config)

    def get_connection_url(self) -> str:
        db_path = self.config.database
        if db_path == ":memory:":
            return "sqlite:///:memory:"
        if db_path.startswith("/"):
            # SQLAlchemy needs four slashes for an absolute path
            return f"sqlite:////{db_path.lstrip('/')}"
        return f"sqlite:///{db_path}"

    def create_engine(self) -> Engine:
        if self.config.database != ":memory:" and not os.path.exists(self.config.database):
            raise DatabaseConnectionError(
                f"SQLite database file '{self.config.database}' does not exist on the server."
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

