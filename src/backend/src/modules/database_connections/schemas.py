# Standard Libraries
from typing import Annotated, Any, Literal, Union

# Third-party Libraries
from pydantic import BaseModel, ConfigDict, Field, SecretStr


# Chỉ mở truy vấn cho nguồn có chính sách chỉ-đọc đã kiểm thử (src/adapters/query_runner.py,
# src/adapters/sql_server.py, src/adapters/mongodb.py).
SOURCE_TYPES = ("sqlite", "duckdb", "mongodb", "postgres", "mysql")
FILE_SOURCES = ("sqlite", "duckdb")
SERVER_SQL_SOURCES = ("postgres", "mysql")
# Tên schema Postgres: định danh thường (không dấu cách / dấu chấm / dấu nháy).
_SCHEMA_PATTERN = r"^[A-Za-z_][A-Za-z0-9_$]{0,62}$"


class ConnectionCreate(BaseModel):
    """
    Kết nối do NGƯỜI DÙNG tạo (giao diện / API), không qua LLM. Mật khẩu được mã hoá khi lưu và
    không bao giờ trả lại. SQLite/DuckDB: `database` là tên file trong DB_SOURCE_FILES_DIR.
    PostgreSQL/MySQL: host (phải nằm trong DB_SOURCE_SQL_ALLOWED_HOSTS), tài khoản CHỈ CÓ QUYỀN SELECT;
    `schema_name` chỉ dùng cho PostgreSQL (mặc định public).
    """
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    db_type: Literal["sqlite", "duckdb", "mongodb", "postgres", "mysql"]
    database: str = Field(..., min_length=1, max_length=255)
    host: str | None = Field(None, max_length=255)
    port: int | None = Field(None, ge=1, le=65535)
    username: str | None = Field(None, max_length=255)
    password: SecretStr | None = None
    schema_name: str | None = Field(None, pattern=_SCHEMA_PATTERN)
    description: str | None = Field(None, max_length=1000)


class ConnectionUpdate(BaseModel):
    """Bỏ trống `password` = giữ nguyên mật khẩu cũ."""
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=100)
    database: str | None = Field(None, min_length=1, max_length=255)
    host: str | None = Field(None, max_length=255)
    port: int | None = Field(None, ge=1, le=65535)
    username: str | None = Field(None, max_length=255)
    password: SecretStr | None = None
    schema_name: str | None = Field(None, pattern=_SCHEMA_PATTERN)
    description: str | None = Field(None, max_length=1000)


class ConnectionPublic(BaseModel):
    """Thông tin kết nối an toàn để trả ra (không host, username, đường dẫn thật hay mật khẩu)."""
    id: str
    name: str
    db_type: str
    database_label: str
    description: str | None = None
    version: int
    created_at: float
    updated_at: float


class DescribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str = Field(..., min_length=1, max_length=255)
    sample_rows: int = Field(5, ge=1, le=10)


class SqlQuerySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["sql"]
    sql: str = Field(..., min_length=1, max_length=20_000)
    params: dict[str, Any] = Field(default_factory=dict)
    row_limit: int = Field(20, ge=1, le=100)


class MongoFindSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["find"]
    collection: str = Field(..., min_length=1, max_length=255)
    filter: dict[str, Any] = Field(default_factory=dict)
    projection: dict[str, Any] = Field(default_factory=dict)
    sort: dict[str, int] = Field(default_factory=dict)
    row_limit: int = Field(20, ge=1, le=100)


class MongoAggregateSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["aggregate"]
    collection: str = Field(..., min_length=1, max_length=255)
    pipeline: list[dict[str, Any]] = Field(..., min_length=1, max_length=20)
    row_limit: int = Field(20, ge=1, le=100)


QuerySpec = Annotated[Union[SqlQuerySpec, MongoFindSpec, MongoAggregateSpec], Field(discriminator="kind")]


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: QuerySpec


class PreviewResult(BaseModel):
    preview_id: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    row_limit: int
    truncated: bool
    expires_at: float
    query: dict[str, Any]


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_id: str = Field(..., min_length=1, max_length=64)
    data_name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    allow_truncated: bool = False


class ImportResult(BaseModel):
    dataset_id: str
    data_name: str
    row_count: int
    columns: list[str]
    truncated: bool
    already_imported: bool = False
    notes: list[str] = []
