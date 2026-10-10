from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# --- 1. Standard adapter exceptions ---
class DatabaseAdapterError(Exception):
    """Base error for all database adapters."""
    pass

class DatabaseConnectionError(DatabaseAdapterError):
    """Raised when the database cannot be reached (wrong host/port, timeout)."""
    pass

class TableNotFoundError(DatabaseAdapterError):
    """Raised when the requested table or view does not exist."""
    pass

class QueryExecutionError(DatabaseAdapterError):
    """Raised when a query fails."""
    pass

# --- 2. Connection config ---
@dataclass
class DatabaseConfig:
    db_type: str
    database: str
    host: Optional[str] = "localhost"
    port: Optional[int] = None
    user: Optional[str] = None
    password: Optional[str] = None
    schema_name: Optional[str] = None
    connect_timeout: int = 5
    extra_params: Dict[str, Any] = field(default_factory=dict)

# --- 3. Base adapter ---
class BaseDatabaseAdapter(ABC):
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._engine: Optional[Engine] = None

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self._engine = self.create_engine()
        return self._engine

    # Abstract methods: every database adapter must implement these
    @abstractmethod
    def get_connection_url(self) -> str:
        """Build the SQLAlchemy connection URL for this database."""
        pass

    @abstractmethod
    def create_engine(self) -> Engine:
        """Create the SQLAlchemy engine with database-specific options (timeout, charset...)."""
        pass

    @abstractmethod
    def quote_identifier(self, identifier: str) -> str:
        """Quote an identifier using the database's rules (Postgres uses ", MySQL uses `)."""
        pass

    # Shared methods (work for every database)
    def get_test_query(self) -> str:
        """Query used to test the connection (SELECT 1 by default; Oracle needs SELECT 1 FROM DUAL)."""
        return "SELECT 1"

    def test_connection(self) -> bool:
        """Quickly check that the database is reachable."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text(self.get_test_query()))
            return True
        except Exception as e:
            raise DatabaseConnectionError(f"Could not connect to the database: {str(e)}") from e

    def get_tables(self) -> List[str]:
        """List table names (views included when available)."""
        try:
            schema = (
                self.config.schema_name.strip()
                if self.config.schema_name and self.config.schema_name.strip()
                else None
            )
            with self.engine.connect() as conn:
                inspector = inspect(conn)
                tables = inspector.get_table_names(schema=schema)
                try:
                    views = inspector.get_view_names(schema=schema) or []
                except Exception:
                    views = []
                all_tables = set(tables + views)
                return sorted(list(all_tables))
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to list tables: {str(e)}") from e

    def get_full_table_name(self, table_name: str) -> str:
        """Prefix the table name with schema_name when a schema is set."""
        safe_table = self.quote_identifier(table_name)
        schema = (
            self.config.schema_name.strip()
            if self.config.schema_name and self.config.schema_name.strip()
            else None
        )
        if schema:
            safe_schema = self.quote_identifier(schema)
            return f"{safe_schema}.{safe_table}"
        return safe_table

    def build_select_query(self, table_name: str, limit: int = 50000) -> str:
        """Build a row-limited SELECT (overridden for MSSQL and Oracle)."""
        safe_table = self.get_full_table_name(table_name)
        return f"SELECT * FROM {safe_table} LIMIT {int(limit)}"

    def fetch_table_to_dataframe(self, table_name: str, limit: int = 50000) -> pd.DataFrame:
        """Load a table into a DataFrame."""
        tables = self.get_tables()
        canonical_table = None
        if table_name in tables:
            canonical_table = table_name
        else:
            # Case-insensitive fallback for databases that return upper-case names (Snowflake, Oracle)
            lower_map = {t.lower(): t for t in tables}
            if table_name.lower() in lower_map:
                canonical_table = lower_map[table_name.lower()]
            else:
                raise TableNotFoundError(f"Table or view '{table_name}' does not exist in the database.")

        query = self.build_select_query(table_name=canonical_table, limit=limit)

        try:
            with self.engine.connect() as conn:
                return pd.read_sql(text(query), con=conn)
        except Exception as e:
            raise QueryExecutionError(f"Failed to read table '{table_name}': {str(e)}") from e

    def run_sql(self, sql: str, limit: Optional[int] = 1000) -> pd.DataFrame:
        """Run a read-only SQL query (SELECT / WITH only)."""
        cleaned_sql = sql.strip().upper()
        if not (cleaned_sql.startswith("SELECT") or cleaned_sql.startswith("WITH")):
            raise ValueError("Only read-only queries (SELECT / WITH) are allowed.")
        with self.engine.connect() as conn:
            df = pd.read_sql(text(sql), con=conn)
            if limit is not None and len(df) > limit:
                return df.head(limit)
            return df

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Return the column names and types of a table."""
        schema = (
            self.config.schema_name.strip()
            if self.config.schema_name and self.config.schema_name.strip()
            else None
        )
        with self.engine.connect() as conn:
            inspector = inspect(conn)
            try:
                columns = inspector.get_columns(table_name, schema=schema)
                if not columns and table_name not in self.get_tables():
                    raise TableNotFoundError(f"Table or view '{table_name}' does not exist in the database.")
            except Exception as e:
                if isinstance(e, TableNotFoundError):
                    raise
                raise TableNotFoundError(f"Table or view '{table_name}' does not exist in the database: {str(e)}") from e

            return {
                "table_name": table_name,
                "columns": [{"name": col["name"], "type": str(col["type"])} for col in columns],
            }


    def dispose(self):
        """Dispose the engine and release its connection pool."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    # Support "with adapter:" usage
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()
