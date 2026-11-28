# Standard Libraries
import os

# Third-party Libraries
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

# Local Libraries
from src.adapters.base import BaseDatabaseAdapter, DatabaseConfig, DatabaseConnectionError


class SQLiteAdapter(BaseDatabaseAdapter):
    """SQLite adapter, supports database files and in-memory databases."""

    query_dialect = "sqlite"

    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        if config.database != ":memory:":
            # Chỉ đọc file trong DB_SOURCE_FILES_DIR: trước đây nhận đường dẫn tuỳ ý trên server,
            # tức là ai gọi API cũng đọc được mọi file SQLite của máy chủ.
            from src.adapters.query_runner import SourceAccessError, resolve_source_file  # noqa: PLC0415
            from src.config import settings  # noqa: PLC0415

            try:
                self.config.database = str(resolve_source_file(config.database, settings.DATABASE_SOURCES.FILES_DIR))
            except SourceAccessError as error:
                raise DatabaseConnectionError(str(error)) from error

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

    # ---- Endpoint cũ /datasets/database/* (giao diện còn dùng) đi qua bộ chạy an toàn, không qua
    # SQLAlchemy: mở chỉ-đọc, tắt truy cập file/mạng ngoài, chạy trong tiến trình con có trần bộ nhớ
    # và thời gian. Nhờ vậy một VIEW định nghĩa bằng read_csv('/file-ngoài') cũng không đọc được.
    def _safe(self):
        from pathlib import Path  # noqa: PLC0415

        if self.config.database == ":memory:":
            raise DatabaseConnectionError("Database trong bộ nhớ không có dữ liệu để đọc.")
        return Path(self.config.database)

    def test_connection(self) -> bool:
        self.get_tables()
        return True

    def get_tables(self) -> list[str]:
        from src.adapters.query_runner import sqlite_tables  # noqa: PLC0415

        try:
            return sqlite_tables(self._safe())
        except DatabaseConnectionError:
            raise
        except Exception as error:  # noqa: BLE001
            raise DatabaseConnectionError(f"Không đọc được danh sách bảng SQLite.") from error

    def get_table_schema(self, table_name: str) -> dict:
        from src.adapters.base import TableNotFoundError  # noqa: PLC0415
        from src.adapters.query_runner import sqlite_columns  # noqa: PLC0415

        if table_name not in self.get_tables():
            raise TableNotFoundError(f"Table or view '{table_name}' does not exist in the database.")
        columns = sqlite_columns(self._safe(), table_name)
        return {"table_name": table_name, "columns": [{"name": c["name"], "type": c["type"]} for c in columns]}

    def fetch_table_to_dataframe(self, table_name: str, limit: int = 50000):
        import pandas as pd  # noqa: PLC0415
        from src.adapters.base import QueryExecutionError, TableNotFoundError  # noqa: PLC0415
        from src.adapters.query_policy import validate_sql  # noqa: PLC0415
        from src.adapters.query_runner import QueryFailedError, QueryTimeoutError, quote_identifier, run_sqlite  # noqa: PLC0415
        from src.config import settings  # noqa: PLC0415

        tables = self.get_tables()
        canonical = next((t for t in tables if t == table_name), None) or \
            next((t for t in tables if t.lower() == table_name.lower()), None)
        if canonical is None:
            raise TableNotFoundError(f"Table or view '{table_name}' does not exist in the database.")
        query = validate_sql(f"SELECT * FROM {quote_identifier(canonical)}", self.query_dialect, tables)
        sources = settings.DATABASE_SOURCES
        try:
            result = run_sqlite(self._safe(), query, {}, int(limit), sources.QUERY_TIMEOUT_SECONDS * 3,
                               max_bytes=sources.IMPORT_MAX_BYTES)
        except (QueryFailedError, QueryTimeoutError) as error:
            raise QueryExecutionError(f"Failed to read table '{table_name}': {error}") from error
        return pd.DataFrame(result.rows, columns=result.columns)
