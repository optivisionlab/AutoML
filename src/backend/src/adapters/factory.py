from typing import Dict, Type
from src.adapters.base import BaseDatabaseAdapter, DatabaseConfig
from src.adapters.postgres import PostgresAdapter
from src.adapters.mysql import MySQLAdapter
from src.adapters.sqlite import SQLiteAdapter
from src.adapters.mssql import MSSQLAdapter
from src.adapters.snowflake import SnowflakeAdapter
from src.adapters.bigquery import BigQueryAdapter
from src.adapters.duckdb import DuckDBAdapter
from src.adapters.clickhouse import ClickHouseAdapter
from src.adapters.oracle import OracleAdapter
from src.adapters.trino import TrinoAdapter
from src.adapters.hive import HiveAdapter
from src.adapters.redshift import RedshiftAdapter


# db_type (lower-case) -> adapter class; aliases point to the same class
ADAPTERS: Dict[str, Type[BaseDatabaseAdapter]] = {
    "postgres": PostgresAdapter,
    "postgresql": PostgresAdapter,
    "mysql": MySQLAdapter,
    "sqlite": SQLiteAdapter,
    "sqlite3": SQLiteAdapter,
    "mssql": MSSQLAdapter,
    "sqlserver": MSSQLAdapter,
    "snowflake": SnowflakeAdapter,
    "bigquery": BigQueryAdapter,
    "duckdb": DuckDBAdapter,
    "clickhouse": ClickHouseAdapter,
    "oracle": OracleAdapter,
    "trino": TrinoAdapter,
    "presto": TrinoAdapter,
    "hive": HiveAdapter,
    "redshift": RedshiftAdapter,
    "amazon_redshift": RedshiftAdapter,
}


class DatabaseAdapterFactory:
    @staticmethod
    def create(config: DatabaseConfig) -> BaseDatabaseAdapter:
        adapter_cls = ADAPTERS.get(config.db_type.lower().strip())
        if adapter_cls is None:
            supported = ", ".join(sorted(ADAPTERS))
            raise ValueError(f"Unsupported database type '{config.db_type}'. Supported types: [{supported}]")
        return adapter_cls(config)
