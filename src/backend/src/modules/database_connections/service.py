"""
Kết nối database đã lưu: metadata -> xem trước truy vấn -> nhập kết quả thành dataset.

Luồng cho người dùng và SQL agent:
    tạo kết nối (người dùng, có mật khẩu)  ->  liệt kê bảng / mô tả bảng (metadata)
    ->  preview truy vấn đã kiểm (<= 100 dòng, có preview_id)  ->  import preview_id thành dataset
    ->  dataset_id đi tiếp vào luồng AutoML có sẵn.
Agent chỉ cầm connection_id / preview_id: không bao giờ thấy host, tài khoản hay mật khẩu.
"""
# Standard Libraries
import asyncio
import datetime as dt
import decimal
import hashlib
import json
import time
import uuid
from typing import Any, Callable

# Third-party Libraries
import pandas as pd
from bson import ObjectId
from fastapi import status
from sqlglot import exp

# Local Libraries
from src.adapters.mongodb import MongoSource
from src.adapters.query_policy import MAX_SQL_LENGTH, UnsafeQueryError, validate_sql
from src.adapters.query_runner import (
    MAX_COLUMN_NAME_CHARS,
    MAX_COLUMNS,
    QueryFailedError,
    QueryResult,
    QueryTimeoutError,
    SourceAccessError,
    check_column_names,
    duckdb_columns,
    duckdb_tables,
    json_safe,
    resolve_source_file,
    run_duckdb,
    run_server,
    run_sqlite,
    server_columns,
    server_tables,
    sqlite_columns,
    sqlite_tables,
)
from src.adapters.sql_server import DEFAULT_PORTS
from src.config import settings
from src.core import exceptions
from src.core.connection_crypto import ConnectionCryptoError, KEY_VERSION, decrypt_secret, encrypt_secret, ensure_configured
from src.modules.database_connections.repository import ConnectionRepository
from src.modules.database_connections.schemas import (
    FILE_SOURCES,
    SERVER_SQL_SOURCES,
    ConnectionCreate,
    ConnectionPublic,
    ConnectionUpdate,
    DescribeRequest,
    ImportRequest,
    ImportResult,
    PreviewResult,
)
from src.modules.datasets.service import DatasetService


def _describable(columns: list[dict]) -> list[dict]:
    """Cột đưa ra được khi mô tả bảng: tên không quá dài, tối đa MAX_COLUMNS cột."""
    return [c for c in columns if len(str(c.get("name", ""))) <= MAX_COLUMN_NAME_CHARS][:MAX_COLUMNS]


def _sample_columns(columns: list[dict], table: str, dialect: str = "sqlite") -> tuple[list[dict], str | None]:
    """
    (cột dùng để mô tả, câu SQL lấy dòng mẫu hoặc None). Đủ mọi cột thì `SELECT *`; phải bỏ cột thì
    liệt kê tường minh, và chỉ lấy số cột mà câu SQL (sau khi quote) còn vừa trần MAX_SQL_LENGTH -
    200 cột tên 128 ký tự đã ~26.000 ký tự, vượt trần thì bộ kiểm từ chối cả lần mô tả.
    """
    usable = _describable(columns)

    def ident(name: str) -> str:
        return exp.to_identifier(str(name), quoted=True).sql(dialect=dialect)

    source = ident(table)
    if len(usable) == len(columns):
        return usable, (f"SELECT * FROM {source}" if usable else None)
    budget = MAX_SQL_LENGTH - len("SELECT  FROM ") - len(source) - 100
    picked, used = [], 0
    for column in usable:
        cost = len(ident(column["name"])) + (2 if picked else 0)
        if used + cost > budget:
            break
        picked.append(column)
        used += cost
    if not picked:
        return [], None
    return picked, f"SELECT {', '.join(ident(c['name']) for c in picked)} FROM {source}"


def _bound_describe(info: dict) -> dict:
    """
    Metadata trả ra API (và vào context agent) có trần: bỏ cột tên quá dài, tối đa MAX_COLUMNS cột,
    dòng mẫu chỉ giữ các cột còn lại; số cột bị bỏ ghi ở `omitted_columns`.
    """
    columns = info.get("columns") or []
    keep = _describable(columns)
    names = {c["name"] for c in keep}
    rows = [{k: v for k, v in row.items() if k in names} for row in info.get("rows") or []]
    bounded = {**info, "columns": keep, "rows": rows}
    omitted = int(info.get("omitted_columns") or 0) + len(columns) - len(keep)
    if omitted:
        bounded["omitted_columns"] = omitted
    return bounded


# Bản xem trước: giữ tối đa bấy nhiêu bản / người dùng, và xoá bản đã hết hạn quá một ngày.
PREVIEW_RETENTION_SECONDS = 24 * 3600
MAX_PREVIEWS_PER_USER = 200


def _error(status_code: int, detail: str, code: str) -> exceptions.CustomException:
    return exceptions.CustomException(status_code=status_code, detail=detail, error_code=code)


def _not_found() -> exceptions.CustomException:
    # Kết nối của người khác cũng trả 404: không lộ là nó tồn tại.
    return _error(status.HTTP_404_NOT_FOUND, "Không tìm thấy kết nối database.", "NOT_FOUND")


def _allowed_mongo_hosts() -> set[str]:
    return {h.strip().lower() for h in settings.DATABASE_SOURCES.MONGO_ALLOWED_HOSTS.split(",") if h.strip()}


def _allowed_sql_targets() -> dict[str, set[int | None]]:
    """
    DB_SOURCE_SQL_ALLOWED_HOSTS: "host" (chỉ port mặc định 5432 / 3306) hoặc "host:port" / "[ipv6]:port".
    Ghim cả port: chỉ ghim host thì người dùng vẫn trỏ được tới mọi dịch vụ khác trên máy đó.
    """
    targets: dict[str, set[int | None]] = {}
    for raw in settings.DATABASE_SOURCES.SQL_ALLOWED_HOSTS.split(","):
        entry = raw.strip().lower()
        if not entry:
            continue
        port: int | None = None
        if entry.startswith("["):
            host, _, rest = entry[1:].partition("]")
            if rest.startswith(":") and rest[1:].isdigit():
                port = int(rest[1:])
        elif entry.count(":") == 1 and entry.split(":")[1].isdigit():
            host, port = entry.split(":")[0], int(entry.split(":")[1])
        else:
            host = entry
        targets.setdefault(host, set()).add(port)
    return targets


def _sql_target_allowed(host: str, port: int | None, db_type: str) -> bool:
    ports = _allowed_sql_targets().get((host or "").strip().lower())
    if ports is None:
        return False
    default = DEFAULT_PORTS[db_type]
    return (port or default) in {p or default for p in ports}


# Database / schema hệ thống: không phải dữ liệu người dùng, chứa tài khoản và cấu hình server.
_MYSQL_SYSTEM_DATABASES = {"mysql", "information_schema", "performance_schema", "sys"}
_POSTGRES_SYSTEM_DATABASES = {"template0", "template1"}
_POSTGRES_SYSTEM_SCHEMAS = {"information_schema"}


def _app_databases() -> set[str]:
    # Database của chính HAutoML (người dùng, kết nối, job...): không bao giờ là nguồn dữ liệu.
    return {settings.MONGODB.NAME.lower()}


def _kind(value: Any) -> str:
    """Loại giá trị theo isinstance (bool xét trước int; lớp con như bson Int64 vẫn là int)."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, decimal.Decimal):
        return "decimal"
    if isinstance(value, str):
        return "str"
    if isinstance(value, (dt.datetime, dt.date)):
        return "datetime"
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "bytes"
    if isinstance(value, (dict, list, tuple)):
        return "nested"
    return type(value).__name__


def frame_for_import(columns: list[str], rows: list[dict]) -> tuple[pd.DataFrame, list[str]]:
    """
    Kết quả truy vấn -> DataFrame GIỮ ĐÚNG KIỂU: số nguyên có NULL dùng Int64 (không thành float làm
    sai số lớn), DECIMAL đổi sang số thực có ghi chú, cột trộn số và chữ hay dữ liệu nhị phân thì báo
    rõ để sửa truy vấn (thay vì lỗi parquet khó hiểu).

    Tên cột được bỏ khoảng trắng hai đầu như mọi dataset của HAutoML (DatasetService cũng làm vậy) -
    làm Ở ĐÂY để tên báo về / ghi provenance khớp đúng tên trong file, và hai cột chỉ khác khoảng
    trắng (`x` và `" x "`) bị báo rõ thay vì lỗi parquet trùng tên.
    """
    names = [str(c).strip() for c in columns]
    clashes = sorted({n for n in names if names.count(n) > 1})
    if clashes:
        raise _error(status.HTTP_400_BAD_REQUEST,
                     f"Các cột {_column_list(clashes)} trùng tên sau khi bỏ khoảng trắng hai đầu - đặt alias khác nhau.",
                     "QUERY_INVALID")
    data: dict[str, Any] = {}
    decimal_columns: list[str] = []
    big_int_columns: list[str] = []
    for column, name in zip(columns, names):
        # NaN (MongoDB / số thực) là giá trị thiếu như NULL - chuẩn hoá trước khi ép kiểu.
        values = [None if _missing(row.get(column)) else row.get(column) for row in rows]
        present = [v for v in values if v is not None]
        kinds = {_kind(v) for v in present}
        ints_fit = all(_INT64_MIN <= v <= _INT64_MAX for v in present if _kind(v) == "int")
        if not present:
            data[name] = pd.Series(values, dtype="float64")
        elif kinds <= {"bool"}:
            data[name] = pd.array(values, dtype="boolean")
        elif kinds <= {"int", "bool"} and ints_fit:
            data[name] = pd.array([None if v is None else int(v) for v in values], dtype="Int64")
        elif kinds <= {"int", "float", "bool", "decimal"}:
            # Gồm cả cột số nguyên ngoài miền Int64 (vd UBIGINT 2^63 của DuckDB): đổi sang số thực, có ghi chú.
            if "decimal" in kinds:
                decimal_columns.append(name)
            if "int" in kinds and any(_kind(v) == "int" and abs(v) > 2 ** 53 for v in present):
                big_int_columns.append(name)
            data[name] = pd.Series([None if v is None else float(v) for v in values], dtype="float64")
        elif kinds <= {"str"}:
            data[name] = pd.Series(values, dtype="object")
        elif kinds <= {"datetime"}:
            data[name] = pd.to_datetime(pd.Series(values, dtype="object"))
        elif "bytes" in kinds:
            raise _error(status.HTTP_400_BAD_REQUEST,
                         f"Cột '{column}' là dữ liệu nhị phân - bỏ khỏi truy vấn trước khi nhập.", "QUERY_INVALID")
        elif "nested" in kinds:
            raise _error(status.HTTP_400_BAD_REQUEST,
                         f"Cột '{column}' chứa object/mảng lồng - dùng $project để lấy giá trị đơn trước khi nhập.",
                         "QUERY_INVALID")
        else:
            raise _error(status.HTTP_400_BAD_REQUEST,
                         f"Cột '{column}' trộn nhiều kiểu ({', '.join(sorted(kinds))}) - CAST về một kiểu trong "
                         "truy vấn trước khi nhập.", "QUERY_INVALID")
    notes = []
    if decimal_columns:
        notes.append(f"{_column_list(decimal_columns)} kiểu DECIMAL đã đổi sang số thực (float64).")
    if big_int_columns:
        notes.append(f"{_column_list(big_int_columns)} có số nguyên lớn (> 2^53) đã đổi sang số thực - có thể "
                     "mất chính xác; CAST sang TEXT nếu đó là mã định danh.")
    return pd.DataFrame(data, columns=names), notes


_INT64_MIN, _INT64_MAX = -(2 ** 63), 2 ** 63 - 1


def _missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(isinstance(value, (float, decimal.Decimal)) and value != value)
    except decimal.InvalidOperation:  # Decimal sNaN không so sánh được
        return True


def _column_list(names: list[str], shown: int = 10) -> str:
    listed = ", ".join(f"'{n}'" for n in names[:shown])
    more = f" và {len(names) - shown} cột khác" if len(names) > shown else ""
    return f"{len(names)} cột ({listed}{more})"


class ConnectionService:
    # Test thay bằng client giả (mongomock); None = MongoClient thật.
    mongo_client_factory: Callable[[dict], Any] | None = None

    def __init__(self, repo: ConnectionRepository, dataset_service: DatasetService):
        self.repo = repo
        self.datasets = dataset_service

    # ------------------------------------------------------------------ chuyển đổi
    @staticmethod
    def to_public(doc: dict) -> ConnectionPublic:
        return ConnectionPublic(
            id=str(doc["_id"]),
            name=doc["name"],
            db_type=doc["db_type"],
            database_label=(f"{doc['database']}.{doc['schema_name']}" if doc.get("schema_name") else doc["database"]),
            description=doc.get("description"),
            version=int(doc.get("version", 1)),
            created_at=float(doc["created_at"]),
            updated_at=float(doc["updated_at"]),
        )

    @staticmethod
    def _validate_fields(doc: dict) -> None:
        """Ràng buộc theo loại nguồn - chạy cả lúc tạo lẫn lúc sửa."""
        if doc["db_type"] in FILE_SOURCES:
            if (doc.get("host") or doc.get("port") or doc.get("username") or doc.get("password_ciphertext")
                    or doc.get("schema_name")):
                raise _error(status.HTTP_400_BAD_REQUEST,
                             "SQLite/DuckDB chỉ nhận tên file (database); không dùng host, port, tài khoản.",
                             "BAD_REQUEST")
            try:
                resolve_source_file(doc["database"], settings.DATABASE_SOURCES.FILES_DIR)
            except SourceAccessError as error:
                raise _error(status.HTTP_400_BAD_REQUEST, str(error), "SOURCE_ACCESS") from None
        elif doc["db_type"] in SERVER_SQL_SOURCES:
            label = "PostgreSQL" if doc["db_type"] == "postgres" else "MySQL"
            host = (doc.get("host") or "").strip().lower()
            if not host or not doc.get("username"):
                raise _error(status.HTTP_400_BAD_REQUEST, f"{label} cần host và username.", "BAD_REQUEST")
            if not _allowed_sql_targets():
                raise _error(status.HTTP_400_BAD_REQUEST,
                             f"Nguồn {label} đang tắt: quản trị chưa khai DB_SOURCE_SQL_ALLOWED_HOSTS.", "SOURCE_ACCESS")
            # So khớp NGUYÊN chuỗi host và cả port: "a,b" (nhiều host của libpq) hay "/run/postgresql"
            # (socket) không lọt; host đúng nhưng port khác cũng bị chặn.
            if not _sql_target_allowed(host, doc.get("port"), doc["db_type"]):
                raise _error(status.HTTP_400_BAD_REQUEST,
                             f"Host / port '{host}:{doc.get('port') or DEFAULT_PORTS[doc['db_type']]}' không nằm trong "
                             "DB_SOURCE_SQL_ALLOWED_HOSTS.", "SOURCE_ACCESS")
            database = doc["database"].lower()
            schema = (doc.get("schema_name") or "").lower()
            if doc["db_type"] == "mysql":
                if schema:
                    raise _error(status.HTTP_400_BAD_REQUEST,
                                 "MySQL không dùng schema_name (database chính là schema).", "BAD_REQUEST")
                if database in _MYSQL_SYSTEM_DATABASES:
                    raise _error(status.HTTP_400_BAD_REQUEST, "Không được kết nối database hệ thống của MySQL.",
                                 "SOURCE_ACCESS")
            elif database in _POSTGRES_SYSTEM_DATABASES or schema in _POSTGRES_SYSTEM_SCHEMAS or schema.startswith("pg_"):
                raise _error(status.HTTP_400_BAD_REQUEST, "Không được kết nối database / schema hệ thống của PostgreSQL.",
                             "SOURCE_ACCESS")
        else:
            if doc.get("schema_name"):
                raise _error(status.HTTP_400_BAD_REQUEST, "schema_name chỉ dùng cho PostgreSQL.", "BAD_REQUEST")
            host = (doc.get("host") or "").strip().lower()
            if not host:
                raise _error(status.HTTP_400_BAD_REQUEST, "MongoDB cần host.", "BAD_REQUEST")
            if not _allowed_mongo_hosts():
                raise _error(status.HTTP_400_BAD_REQUEST,
                             "Nguồn MongoDB đang tắt: quản trị chưa khai DB_SOURCE_MONGO_ALLOWED_HOSTS.", "SOURCE_ACCESS")
            if host not in _allowed_mongo_hosts():
                raise _error(status.HTTP_400_BAD_REQUEST,
                             f"Host '{host}' không nằm trong DB_SOURCE_MONGO_ALLOWED_HOSTS.", "SOURCE_ACCESS")
            if doc["database"].lower() in {"admin", "local", "config"} | _app_databases():
                raise _error(status.HTTP_400_BAD_REQUEST,
                             "Không được kết nối database hệ thống hay database của chính HAutoML.", "SOURCE_ACCESS")

    async def _get_doc(self, current_user: dict, connection_id: str) -> dict:
        doc = await self.repo.get(connection_id, str(current_user["_id"]))
        if not doc:
            raise _not_found()
        return doc

    # ------------------------------------------------------------------ CRUD
    async def create_connection(self, current_user: dict, payload: ConnectionCreate) -> ConnectionPublic:
        try:
            ensure_configured()
            ciphertext = encrypt_secret(payload.password.get_secret_value() if payload.password else None)
        except ConnectionCryptoError as error:
            raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, str(error), "FEATURE_DISABLED") from None
        now = time.time()
        doc = {
            "userId": str(current_user["_id"]),
            "name": payload.name.strip(),
            "db_type": payload.db_type,
            "database": payload.database.strip(),
            "host": (payload.host or "").strip() or None,
            "port": payload.port,
            "username": payload.username or None,
            "schema_name": payload.schema_name or None,
            "password_ciphertext": ciphertext,
            "key_version": KEY_VERSION,
            "description": payload.description,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        self._validate_fields(doc)
        return self.to_public(await self.repo.create(doc))

    async def list_connections(self, current_user: dict, current_page: int, page_size: int) -> tuple[list[ConnectionPublic], dict]:
        docs, total = await self.repo.list_by_user(str(current_user["_id"]), (current_page - 1) * page_size, page_size)
        meta = {"total_items": total, "current_page": current_page, "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if page_size else 0}
        return [self.to_public(d) for d in docs], meta

    async def get_connection(self, current_user: dict, connection_id: str) -> ConnectionPublic:
        return self.to_public(await self._get_doc(current_user, connection_id))

    async def update_connection(self, current_user: dict, connection_id: str, payload: ConnectionUpdate) -> ConnectionPublic:
        doc = await self._get_doc(current_user, connection_id)
        fields: dict[str, Any] = {}
        for key in ("name", "database", "host", "port", "username", "schema_name", "description"):
            value = getattr(payload, key)
            if value is not None:
                fields[key] = value.strip() if isinstance(value, str) else value
        if payload.password is not None:
            try:
                fields["password_ciphertext"] = encrypt_secret(payload.password.get_secret_value())
                fields["key_version"] = KEY_VERSION
            except ConnectionCryptoError as error:
                raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, str(error), "FEATURE_DISABLED") from None
        self._validate_fields({**doc, **fields})
        updated = await self.repo.update(connection_id, str(current_user["_id"]), fields, time.time())
        if not updated:
            raise _not_found()
        return self.to_public(updated)

    async def delete_connection(self, current_user: dict, connection_id: str) -> None:
        if not await self.repo.delete(connection_id, str(current_user["_id"])):
            raise _not_found()

    # ------------------------------------------------------------------ nguồn dữ liệu (chạy trong thread)
    def _mongo(self, doc: dict) -> MongoSource:
        password = decrypt_secret(doc.get("password_ciphertext"))
        client = self.mongo_client_factory(doc) if self.mongo_client_factory else None
        return MongoSource(
            database=doc["database"], host=doc.get("host"), port=doc.get("port"), username=doc.get("username"),
            password=password, allowed_hosts=_allowed_mongo_hosts(),
            timeout=settings.DATABASE_SOURCES.QUERY_TIMEOUT_SECONDS, client=client,
            forbidden_databases=_app_databases(),
        )

    @staticmethod
    def _path(doc: dict):
        return resolve_source_file(doc["database"], settings.DATABASE_SOURCES.FILES_DIR)

    @staticmethod
    def _server(doc: dict) -> dict:
        """Cấu hình PostgreSQL / MySQL cho tiến trình con. Kiểm lại host: allowlist có thể đã đổi sau khi tạo."""
        host = (doc.get("host") or "").strip()
        if not _sql_target_allowed(host, doc.get("port"), doc["db_type"]):
            raise SourceAccessError("Host / port của kết nối không còn nằm trong DB_SOURCE_SQL_ALLOWED_HOSTS.")
        return {
            "engine": doc["db_type"], "host": host, "port": int(doc.get("port") or DEFAULT_PORTS[doc["db_type"]]),
            "username": doc.get("username"), "password": decrypt_secret(doc.get("password_ciphertext")),
            "database": doc["database"], "schema": doc.get("schema_name") or "public",
        }

    def _tables_sync(self, doc: dict) -> list[str]:
        if doc["db_type"] == "sqlite":
            return sqlite_tables(self._path(doc))
        if doc["db_type"] == "duckdb":
            return duckdb_tables(self._path(doc))
        if doc["db_type"] in SERVER_SQL_SOURCES:
            return server_tables(self._server(doc), settings.DATABASE_SOURCES.QUERY_TIMEOUT_SECONDS)
        with self._mongo(doc) as source:
            return source.list_tables()

    def _describe_sync(self, doc: dict, table: str, sample_rows: int) -> dict:
        tables = self._tables_sync(doc)
        if doc["db_type"] == "mongodb":
            with self._mongo(doc) as source:
                info = source.describe(table, sample_rows, settings.DATABASE_SOURCES.PREVIEW_MAX_BYTES)
            return {"table": table, **info}
        if table not in tables:
            raise QueryFailedError(f"Bảng '{table}' không tồn tại trong kết nối này.")
        if doc["db_type"] in SERVER_SQL_SOURCES:
            columns = server_columns(self._server(doc), table, settings.DATABASE_SOURCES.QUERY_TIMEOUT_SECONDS)
        else:
            path = self._path(doc)
            columns = sqlite_columns(path, table) if doc["db_type"] == "sqlite" else duckdb_columns(path, table)
        # Bảng có cột tên quá dài / quá nhiều cột: metadata và dòng mẫu dùng CÙNG tập cột hiển thị được.
        shown, sql = _sample_columns(columns, table, doc["db_type"])
        rows = self._execute_sync(doc, {"kind": "sql", "sql": sql, "params": {}}, sample_rows, tables)[0].rows if sql else []
        info = {"table": table, "columns": shown, "rows": rows, "schema_inferred": False}
        if len(columns) > len(shown):
            info["omitted_columns"] = len(columns) - len(shown)
        return info

    def _execute_sync(self, doc: dict, query: dict, cap: int, tables: list[str] | None = None,
                      max_bytes: int | None = None) -> tuple[QueryResult, dict]:
        """(kết quả, truy vấn chuẩn hoá để lưu). Truy vấn SQL luôn qua validate_sql với danh sách bảng thật."""
        timeout = settings.DATABASE_SOURCES.QUERY_TIMEOUT_SECONDS
        max_bytes = max_bytes or settings.DATABASE_SOURCES.PREVIEW_MAX_BYTES
        if doc["db_type"] in FILE_SOURCES or doc["db_type"] in SERVER_SQL_SOURCES:
            if query.get("kind") != "sql":
                raise UnsafeQueryError("Nguồn SQL chỉ nhận truy vấn kind='sql'.")
            tables = tables if tables is not None else self._tables_sync(doc)
            validated = validate_sql(query["sql"], doc["db_type"], tables)
            params = query.get("params") or {}
            if doc["db_type"] in SERVER_SQL_SOURCES:
                result = run_server(self._server(doc), validated, params, cap, timeout, max_bytes=max_bytes)
            else:
                runner = run_sqlite if doc["db_type"] == "sqlite" else run_duckdb
                result = runner(self._path(doc), validated, params, cap, timeout, max_bytes=max_bytes)
            check_column_names(result.columns)
            return result, {"kind": "sql", "sql": validated.sql, "params": query.get("params") or {},
                            "tables": sorted(validated.tables)}
        if query.get("kind") not in ("find", "aggregate"):
            raise UnsafeQueryError("Nguồn MongoDB chỉ nhận truy vấn kind='find' hoặc 'aggregate'.")
        spec = {k: v for k, v in query.items() if k != "row_limit"}
        with self._mongo(doc) as source:
            result = source.execute(spec, cap, max_bytes=max_bytes)
        check_column_names(result.columns)
        return result, spec

    async def _run(self, func, *args):
        """Chạy lời gọi chặn (driver) ngoài event loop; lỗi nguồn -> lỗi HTTP rõ ràng, không lộ chi tiết driver thô."""
        try:
            return await asyncio.to_thread(func, *args)
        except UnsafeQueryError as error:
            raise _error(status.HTTP_400_BAD_REQUEST, str(error), "UNSAFE_QUERY") from None
        except QueryTimeoutError as error:
            raise _error(status.HTTP_504_GATEWAY_TIMEOUT, str(error), "QUERY_TIMEOUT") from None
        except QueryFailedError as error:
            raise _error(status.HTTP_400_BAD_REQUEST, str(error), "QUERY_INVALID") from None
        except SourceAccessError as error:
            raise _error(status.HTTP_400_BAD_REQUEST, str(error), "SOURCE_ACCESS") from None
        except ConnectionCryptoError as error:
            raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, str(error), "FEATURE_DISABLED") from None

    # ------------------------------------------------------------------ metadata
    async def test_connection(self, current_user: dict, connection_id: str) -> dict:
        doc = await self._get_doc(current_user, connection_id)
        tables = await self._run(self._tables_sync, doc)
        return {"connected": True, "table_count": len(tables)}

    async def list_tables(self, current_user: dict, connection_id: str) -> dict:
        doc = await self._get_doc(current_user, connection_id)
        tables = await self._run(self._tables_sync, doc)
        kind = "collection" if doc["db_type"] == "mongodb" else "table"
        return {"tables": [{"name": t, "kind": kind} for t in tables]}

    async def describe_table(self, current_user: dict, connection_id: str, payload: DescribeRequest) -> dict:
        doc = await self._get_doc(current_user, connection_id)
        info = await self._run(self._describe_sync, doc, payload.table, payload.sample_rows)
        return json_safe(_bound_describe(info))

    # ------------------------------------------------------------------ preview / import
    async def preview_query(self, current_user: dict, connection_id: str, query: dict) -> PreviewResult:
        doc = await self._get_doc(current_user, connection_id)
        row_limit = min(int(query.get("row_limit") or 20), settings.DATABASE_SOURCES.PREVIEW_MAX_ROWS)
        result, normalized = await self._run(self._execute_sync, doc, query, row_limit)
        now = time.time()
        expires_at = now + settings.DATABASE_SOURCES.PREVIEW_TTL_SECONDS
        # Giữ thêm một ngày sau khi hết hạn (gửi lại import vẫn nhận "already_imported"), rồi dọn.
        await self.repo.prune_previews(str(current_user["_id"]), now - PREVIEW_RETENTION_SECONDS,
                                       MAX_PREVIEWS_PER_USER - 1)
        preview = await self.repo.create_preview({
            "userId": str(current_user["_id"]),
            "connection_id": connection_id,
            "connection_version": int(doc.get("version", 1)),
            # Chuỗi JSON: truy vấn MongoDB có khoá bắt đầu bằng "$", không lưu thẳng làm document được.
            "query_json": json.dumps(normalized, ensure_ascii=False, sort_keys=True),
            "columns": result.columns,
            "created_at": now,
            "expires_at": expires_at,
            "import_state": None,
            # Dataset của lần nhập preview này có _id cố định: thử lại / tiến trình chết giữa chừng
            # thì đối soát theo _id này, không tạo dataset thứ hai.
            "dataset_id": str(ObjectId()),
        })
        return PreviewResult(
            preview_id=str(preview["_id"]), columns=result.columns, rows=json_safe(result.rows),
            row_count=result.row_count, row_limit=row_limit, truncated=result.truncated,
            expires_at=expires_at, query=normalized,
        )

    async def import_preview(self, current_user: dict, connection_id: str, payload: ImportRequest) -> ImportResult:
        user_id = str(current_user["_id"])
        doc = await self._get_doc(current_user, connection_id)
        preview = await self.repo.get_preview(payload.preview_id, user_id)
        if not preview or preview.get("connection_id") != connection_id:
            raise _error(status.HTTP_404_NOT_FOUND, "Không tìm thấy bản xem trước (preview_id) của kết nối này.", "NOT_FOUND")
        if preview.get("import_state") == "done" and preview.get("import_result"):
            # Gửi lại cùng preview_id (vd mạng chập chờn): trả đúng dataset đã tạo, không tạo bản thứ hai.
            return ImportResult(**preview["import_result"], already_imported=True)
        existing = await self.datasets.repo.get_dataset_by_id(ObjectId(preview["dataset_id"]))
        if existing and existing.get("userId") == user_id:
            # Lần nhập trước đã tạo dataset rồi chết trước khi ghi kết quả: trả lại đúng dataset đó
            # (kể cả khi preview đã hết hạn) - không tạo bản thứ hai.
            source = existing.get("source") or {}
            finished = {"dataset_id": preview["dataset_id"], "data_name": existing.get("dataName"),
                        "row_count": source.get("row_count", 0), "columns": source.get("columns", []),
                        "truncated": bool(source.get("truncated")), "notes": source.get("notes", [])}
            await self.repo.finish_preview_import(payload.preview_id, user_id, finished)
            return ImportResult(**finished, already_imported=True)
        if preview["expires_at"] < time.time() or preview["connection_version"] != int(doc.get("version", 1)):
            raise _error(status.HTTP_409_CONFLICT,
                         "Bản xem trước đã hết hạn hoặc kết nối đã đổi - chạy preview lại.", "PREVIEW_STALE")
        sources = settings.DATABASE_SOURCES
        token = uuid.uuid4().hex
        if not await self.repo.claim_preview_import(payload.preview_id, user_id, time.time(),
                                                    sources.IMPORT_LEASE_SECONDS, token):
            raise _error(status.HTTP_409_CONFLICT, "Bản xem trước này đang được nhập.", "IMPORT_IN_PROGRESS")

        finished = None
        try:
            query = json.loads(preview["query_json"])
            cap = sources.IMPORT_MAX_ROWS
            result, _ = await self._run(self._execute_sync, doc, query, cap, None, sources.IMPORT_MAX_BYTES)
            if result.truncated and not payload.allow_truncated:
                raise _error(status.HTTP_409_CONFLICT,
                             f"Kết quả vượt {cap} dòng; thêm điều kiện lọc / LIMIT, hoặc gửi allow_truncated=true "
                             f"để chỉ nhập {cap} dòng đầu.", "RESULT_TRUNCATED")
            df, notes = frame_for_import(result.columns, result.rows)
            if result.truncated:
                notes.append(f"Đã cắt: chỉ nhập {cap} dòng đầu theo đồng ý của người dùng.")
            provenance = {
                "kind": "database_query",
                "connection_id": connection_id,
                "db_type": doc["db_type"],
                "query_sha256": hashlib.sha256(preview["query_json"].encode()).hexdigest(),
                "row_count": len(df),
                "columns": list(df.columns),
                "truncated": result.truncated,
                "notes": notes,
                "imported_at": time.time(),
            }
            dataset = await self.datasets.import_dataframe(current_user, df, payload.data_name,
                                                           payload.description, provenance,
                                                           dataset_id=preview["dataset_id"])
            # Báo đúng cái THẬT SỰ được lưu: hai lượt chồng nhau thì dataset có thể là của lượt kia.
            stored = await self.datasets.repo.get_dataset_by_id(ObjectId(str(dataset.id))) or {}
            source = stored.get("source") or provenance
            finished = {"dataset_id": str(dataset.id), "data_name": stored.get("dataName", dataset.dataName),
                        "row_count": source.get("row_count", len(df)), "columns": source.get("columns", list(df.columns)),
                        "truncated": bool(source.get("truncated")), "notes": source.get("notes", notes)}
            return ImportResult(**finished)
        finally:
            await self.repo.finish_preview_import(payload.preview_id, user_id, finished, token)
