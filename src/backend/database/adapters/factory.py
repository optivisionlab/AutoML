from typing import Dict, Type
from .base import BaseDatabaseAdapter, DatabaseConfig
from .postgres import PostgresAdapter
from .mysql import MySQLAdapter
from .sqlite import SQLiteAdapter
from .mssql import MSSQLAdapter
from .snowflake import SnowflakeAdapter
from .bigquery import BigQueryAdapter
from .duckdb import DuckDBAdapter
from .clickhouse import ClickHouseAdapter
from .oracle import OracleAdapter
from .trino import TrinoAdapter
from .hive import HiveAdapter
from .redshift import RedshiftAdapter

class DatabaseAdapterFactory:
    _registry: Dict[str, Type[BaseDatabaseAdapter]] = {}

    @classmethod
    def register(cls, db_type: str, adapter_cls: Type[BaseDatabaseAdapter]) -> None:
        cls._registry[db_type.lower().strip()] = adapter_cls

    @classmethod
    def create(cls, config: DatabaseConfig) -> BaseDatabaseAdapter:
        key = config.db_type.lower().strip()
        adapter_cls = cls._registry.get(key)
        if not adapter_cls:
            supported = ", ".join(sorted(cls._registry.keys()))
            raise ValueError(f"Loại CSDL '{config.db_type}' chưa được hỗ trợ. Các loại hiện có: [{supported}]")
        return adapter_cls(config)

# Tự động đăng ký các adapter mặc định
DatabaseAdapterFactory.register("postgres", PostgresAdapter)
DatabaseAdapterFactory.register("postgresql", PostgresAdapter)
DatabaseAdapterFactory.register("mysql", MySQLAdapter)
DatabaseAdapterFactory.register("sqlite", SQLiteAdapter)
DatabaseAdapterFactory.register("sqlite3", SQLiteAdapter)
DatabaseAdapterFactory.register("mssql", MSSQLAdapter)
DatabaseAdapterFactory.register("sqlserver", MSSQLAdapter)
DatabaseAdapterFactory.register("snowflake", SnowflakeAdapter)
DatabaseAdapterFactory.register("bigquery", BigQueryAdapter)
DatabaseAdapterFactory.register("duckdb", DuckDBAdapter)
DatabaseAdapterFactory.register("clickhouse", ClickHouseAdapter)
DatabaseAdapterFactory.register("oracle", OracleAdapter)
DatabaseAdapterFactory.register("trino", TrinoAdapter)
DatabaseAdapterFactory.register("presto", TrinoAdapter)
DatabaseAdapterFactory.register("hive", HiveAdapter)
DatabaseAdapterFactory.register("redshift", RedshiftAdapter)
DatabaseAdapterFactory.register("amazon_redshift", RedshiftAdapter)

