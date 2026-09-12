from typing import Dict, Type, List
from .base import BaseDatabaseAdapter, DatabaseConfig
from .postgres import PostgresAdapter
from .mysql import MySQLAdapter

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
