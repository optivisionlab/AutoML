# Third-party Libraries
from pydantic import BaseModel, Field

# Local Libraries
from src.modules.connectors.adapters import DatabaseConfig


class DatabaseConnection(BaseModel):
    """
    Connection parameters shared by every external database endpoint
    """
    db_type: str = Field(..., description="postgres, mysql, sqlite, mssql, snowflake, bigquery, duckdb, clickhouse, oracle, trino, hive, redshift")
    database: str
    host: str | None = "localhost"
    port: int | None = None
    user: str | None = None
    password: str | None = None
    schema_name: str | None = None
    extra_params: dict | None = None

    def to_config(self) -> DatabaseConfig:
        return DatabaseConfig(
            db_type=self.db_type,
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            schema_name=self.schema_name,
            extra_params=self.extra_params or {},
        )


class TableInfoRequest(DatabaseConnection):
    table_name: str
    limit: int = Field(10, ge=1, le=100, description="Number of sample rows to preview")


class ImportTableRequest(DatabaseConnection):
    table_name: str
    data_name: str
    description: str | None = None
    public: bool = False
