# Standard Libraries
from enum import Enum
from datetime import datetime

# Third-party Libraries
from pydantic import BaseModel, Field, field_serializer

# Local Libraries
from src.adapters import DatabaseConfig


class DataTypeEnum(str, Enum):
    TABLE = "table"
    IMAGE = "image"
    TEXT = "text"


class SortNameEnum(str, Enum):
    AZ = "asc"
    ZA = "desc"


class SortTimeEnum(str, Enum):
    NEWEST = "desc"
    OLDEST = "asc"


class DatasetResponse(BaseModel):
    id: str = Field(alias="_id")
    dataName: str
    dataType: DataTypeEnum
    createDate: float
    latestUpdate: float

    thumbnail: str | None = None
    description: str | None = None
    public: bool = False

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

    @field_serializer("createDate", "latestUpdate")
    def serialize_dt_to_float(self, dt: datetime | float) -> float:
        if isinstance(dt, datetime):
            return dt.timestamp()
        return dt


class DatasetAdminResponse(DatasetResponse):
    userId: str
    username: str
    role: str


class DatasetCreate(BaseModel):
    dataName: str
    dataType: DataTypeEnum
    description: str | None = None
    public: bool = False


class DatasetUpdate(BaseModel):
    dataName: str | None = None
    description: str | None = None
    public: bool | None = None


class TrainingConfig(BaseModel):
    choose: str | None = None
    timeout: int | None = None # seconds
    metric_sort: str
    list_feature: list
    problem_type: str
    search_algorithm: str | None = None
    target: str


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
