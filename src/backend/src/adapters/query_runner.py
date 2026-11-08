"""
Chạy truy vấn CHỈ ĐỌC đã qua query_policy trên nguồn dữ liệu ngoài, có hạn thời gian và hạn số dòng.

Hai lớp bảo vệ độc lập với bộ kiểm cú pháp:
- SQLite: mở file với `mode=ro`, `PRAGMA query_only`, authorizer chỉ cho SELECT/READ/FUNCTION
  (không ATTACH, không PRAGMA, không ghi), progress handler cắt khi quá hạn.
- DuckDB: `read_only=True`, tắt truy cập file/mạng ngoài và tự cài/nạp extension, khoá cấu hình,
  giới hạn bộ nhớ/luồng; quá hạn thì `interrupt()`.
Mọi file database phải nằm trong DB_SOURCE_FILES_DIR (resolve cả symlink).

Mỗi truy vấn chạy trong TIẾN TRÌNH CON riêng (trình thông dịch mới qua subprocess) có trần bộ nhớ (RLIMIT_AS) và bị kill khi
quá hạn: một hàm như printf('%1000000000s') hay repeat('x', 2e9) cấp phát ngay trong một dòng -
progress handler / memory_limit của DuckDB không chặn được, chỉ giới hạn tiến trình mới chặn được.
Kết quả vượt trần dung lượng thì bị từ chối, không cắt âm thầm.
"""
# Standard Libraries
import base64
import datetime as dt
import decimal
import math
import pickle
import resource
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

# Local Libraries
from src.adapters.query_policy import UnsafeQueryError, ValidatedQuery


MAX_COLUMNS = 200
# Tên cột / trường dài quá mức (vd trường MongoDB tên hàng triệu ký tự) làm phình metadata trả ra
# API và context agent; 128 = trần định danh của SQL Server, rộng hơn PostgreSQL (63) / MySQL (64).
MAX_COLUMN_NAME_CHARS = 128


class SourceAccessError(ValueError):
    """Không được / không thể truy cập nguồn dữ liệu (file ngoài thư mục cho phép, host bị chặn...)."""


class QueryTimeoutError(RuntimeError):
    """Truy vấn chạy quá thời gian cho phép và đã bị huỷ."""


class QueryFailedError(RuntimeError):
    """Database báo lỗi khi chạy truy vấn (tên cột sai, kiểu sai...)."""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return len(self.rows)


def resolve_source_file(name: str, base_dir: Path) -> Path:
    """
    Đường dẫn thật của file database, BẮT BUỘC nằm trong base_dir. Nhận tên tương đối
    (vd "concrete.sqlite"); đường dẫn tuyệt đối, "..", hay symlink trỏ ra ngoài đều bị từ chối.
    """
    if not isinstance(name, str) or not name.strip() or "\x00" in name:
        raise SourceAccessError("Tên file database không hợp lệ.")
    base = Path(base_dir).resolve()
    candidate = (base / name.strip()).resolve()
    if candidate != base and base not in candidate.parents:
        raise SourceAccessError("File database phải nằm trong thư mục nguồn dữ liệu được cấu hình.")
    if not candidate.is_file():
        raise SourceAccessError(f"Không có file database '{name}' trong thư mục nguồn dữ liệu.")
    return candidate


def json_safe(value: Any) -> Any:
    """Giá trị trả qua API: ngày giờ -> ISO, Decimal -> float, bytes -> base64, NaN -> None."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return str(value)


def check_column_names(columns: list) -> None:
    """Từ chối kết quả có tên cột quá dài (không lặp lại nguyên tên trong thông báo lỗi)."""
    too_long = [str(c) for c in columns if len(str(c)) > MAX_COLUMN_NAME_CHARS]
    if too_long:
        raise QueryFailedError(
            f"Có {len(too_long)} tên cột dài hơn {MAX_COLUMN_NAME_CHARS} ký tự (vd '{too_long[0][:40]}…') - "
            "đặt alias ngắn (AS ...) hoặc dùng $project đổi tên trường."
        )


def _result(columns: list[str], raw_rows: list[tuple], cap: int) -> QueryResult:
    if len(columns) > MAX_COLUMNS:
        raise QueryFailedError(f"Kết quả có {len(columns)} cột, vượt giới hạn {MAX_COLUMNS} cột - chọn bớt cột.")
    if len(set(columns)) != len(columns):
        raise QueryFailedError("Kết quả có tên cột trùng nhau - đặt alias (AS) cho từng cột.")
    truncated = len(raw_rows) > cap
    rows = [dict(zip(columns, row)) for row in raw_rows[:cap]]
    return QueryResult(columns=list(columns), rows=rows, truncated=truncated)


# ------------------------------------------------------------------------- SQLite

_SQLITE_CATALOGS = {"sqlite_master", "sqlite_schema", "sqlite_temp_master", "sqlite_temp_schema"}
_SQLITE_DENIED_FUNCTIONS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"}


def _sqlite_authorizer(allowed_tables: set[str] | None):
    """
    Chỉ đọc: SELECT, đọc cột của ĐÚNG các bảng bộ kiểm đã duyệt, gọi hàm (trừ hàm nguy hiểm).
    Mọi thứ khác (ghi, ATTACH, PRAGMA, bảng catalog, bảng tạm...) bị SQLite từ chối, kể cả khi
    bộ kiểm cú pháp sót.
    """
    allowed = {t.lower() for t in allowed_tables} if allowed_tables is not None else None

    def authorize(action, arg1, arg2, db_name, trigger):
        if action == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ:
            table = (arg1 or "").lower()
            if table in _SQLITE_CATALOGS or (db_name not in (None, "main")):
                return sqlite3.SQLITE_DENY
            # Bảng / CTE đã duyệt, hoặc lượt đọc có tham số thứ 5 khác rỗng: SQLite đặt tên view trong
            # cùng (view lồng v2 -> v1 -> t báo v1) - và cả tên CTE (WITH a AS (SELECT * FROM t) báo a).
            # Vì vậy ở đây authorizer KHÔNG tự bảo vệ danh sách bảng: tầng đó là validate_sql, vốn phân
            # giải bảng thật theo scope (kể cả bên trong CTE) trước khi chạy. Authorizer giữ phần chặn
            # cứng: catalog, database khác main, ghi, hàm nguy hiểm.
            if allowed is not None and table not in allowed and not trigger:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION:
            return sqlite3.SQLITE_DENY if (arg2 or "").lower() in _SQLITE_DENIED_FUNCTIONS else sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    return authorize


def _sqlite_exec(path: str, sql_text: str, params: dict | None, cap: int, timeout: float,
                 tables: list[str] | None) -> tuple[list[str], list[tuple]]:
    uri = f"file:{quote(str(path))}?mode=ro"
    try:
        con = sqlite3.connect(uri, uri=True, timeout=min(timeout, 5), check_same_thread=False)
    except sqlite3.Error as error:
        raise SourceAccessError("Không mở được file SQLite ở chế độ chỉ đọc.") from error
    deadline = time.monotonic() + timeout
    try:
        con.execute("PRAGMA query_only = ON")
        if hasattr(con, "enable_load_extension"):
            con.enable_load_extension(False)
        con.set_authorizer(_sqlite_authorizer(set(tables) if tables is not None else None))
        con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        cursor = con.execute(sql_text, params or {})
        columns = [d[0] for d in cursor.description or []]
        raw = cursor.fetchmany(cap + 1)
    except sqlite3.OperationalError as error:
        if "interrupt" in str(error).lower():
            raise QueryTimeoutError(f"Truy vấn chạy quá {timeout:g} giây và đã bị huỷ.") from None
        raise QueryFailedError(f"SQLite báo lỗi: {error}") from None
    except sqlite3.DatabaseError as error:
        raise QueryFailedError(f"SQLite báo lỗi: {error}") from None
    finally:
        con.close()
    return columns, raw


# ------------------------------------------------------------------------- tiến trình cách ly

def _limits():
    from src.config import settings  # noqa: PLC0415 - tránh vòng import khi chỉ dùng phần thuần

    return settings.DATABASE_SOURCES.WORKER_MEMORY_MB * 1024 * 1024


_BACKEND_ROOT = str(Path(__file__).resolve().parents[2])
# Tiến trình con chỉ import đúng module này - KHÔNG đi qua multiprocessing (spawn/forkserver đều
# chạy lại __main__ của tiến trình cha trong tiến trình con).
# stdout gốc chỉ dành cho kết quả: mọi thứ in ra lúc import / lúc chạy (print, log) bị đẩy sang
# stderr, không làm hỏng khung "ok"/"er" + pickle.
_CHILD_CODE = (
    "import sys; _out = sys.stdout.buffer; sys.stdout = sys.stderr; sys.path.insert(0, sys.argv[1]); "
    "from src.adapters.query_runner import _child_main; _child_main(_out)"
)


def _child_main(out=None) -> None:
    """Tiến trình con: đọc yêu cầu (pickle) từ stdin, đặt trần bộ nhớ, chạy, ghi kết quả ra `out`."""
    if out is None:
        out = sys.stdout.buffer
        sys.stdout = sys.stderr
    try:
        request = pickle.loads(sys.stdin.buffer.read())
        if request["memory_bytes"]:
            resource.setrlimit(resource.RLIMIT_AS, (request["memory_bytes"], request["memory_bytes"]))
        if request["engine"] == "sqlite":
            columns, raw = _sqlite_exec(request["path"], request["sql"], request["params"], request["cap"],
                                        request["timeout"], request["tables"])
        elif request["engine"] in ("postgres", "mysql"):
            from src.adapters.sql_server import server_exec  # noqa: PLC0415

            columns, raw = server_exec(request)
        else:
            columns, raw = _duckdb_exec(request["path"], request["sql"], request["params"], request["cap"],
                                        request["timeout"])
        payload = pickle.dumps((columns, raw), protocol=pickle.HIGHEST_PROTOCOL)
        if len(payload) > request["max_bytes"]:
            raise QueryFailedError(
                f"Kết quả quá lớn (khoảng {len(payload) // (1024 * 1024)} MiB, trần "
                f"{request['max_bytes'] // (1024 * 1024)} MiB) - chọn bớt cột / dòng."
            )
        out.write(b"ok" + payload)
    except (QueryTimeoutError, QueryFailedError, SourceAccessError) as error:
        out.write(b"er" + pickle.dumps((type(error).__name__, str(error))))
    except MemoryError:
        out.write(b"er" + pickle.dumps(("QueryFailedError", "Truy vấn dùng quá trần bộ nhớ cho phép.")))
    except BaseException as error:  # noqa: BLE001 - mọi lỗi khác: báo gọn, không lộ chi tiết driver
        out.write(b"er" + pickle.dumps(("QueryFailedError", f"Lỗi khi chạy truy vấn ({type(error).__name__}).")))
    out.flush()


_ERRORS = {"QueryTimeoutError": QueryTimeoutError, "QueryFailedError": QueryFailedError, "SourceAccessError": SourceAccessError}


def _run_isolated(engine: str, path: Path, sql_text: str, params: dict | None, cap: int, timeout: float,
                  tables: list[str] | None, max_bytes: int, memory_bytes: int | None = None) -> QueryResult:
    columns, raw = _spawn({
        "engine": engine, "path": str(path), "sql": sql_text, "params": params or {}, "cap": cap,
        "timeout": timeout, "tables": tables, "max_bytes": max_bytes,
        "memory_bytes": _limits() if memory_bytes is None else memory_bytes,
    }, timeout)
    return _result(columns, raw, cap)


def _spawn(fields: dict, timeout: float) -> tuple[list[str], list[tuple]]:
    """Chạy một yêu cầu trong tiến trình con cách ly; trả (cột, các dòng) hoặc ném lỗi đã phân loại."""
    request = pickle.dumps(fields)
    try:
        # Trần cứng: hạn của truy vấn + thời gian khởi động trình thông dịch; quá hạn thì bị kill.
        completed = subprocess.run(
            [sys.executable, "-c", _CHILD_CODE, _BACKEND_ROOT],
            input=request, capture_output=True, timeout=timeout + 15, check=False,
        )
    except subprocess.TimeoutExpired:
        raise QueryTimeoutError(f"Truy vấn chạy quá {timeout:g} giây và đã bị huỷ.") from None
    message = completed.stdout
    if message[:2] == b"er":
        kind, text = pickle.loads(message[2:])
        raise _ERRORS.get(kind, QueryFailedError)(text)
    if message[:2] != b"ok":
        # Tiến trình con chết không kịp báo (thường do vượt trần bộ nhớ).
        raise QueryFailedError("Truy vấn làm tiến trình chạy hỏng (thường do vượt trần bộ nhớ).")
    return pickle.loads(message[2:])


# ------------------------------------------------------------------------- PostgreSQL / MySQL

def _server_request(config: dict, op: str, timeout: float, **fields) -> dict:
    return {
        "engine": config["engine"], "op": op, "host": config["host"], "port": config["port"],
        "username": config["username"], "password": config.get("password"), "database": config["database"],
        "schema": config.get("schema") or "public", "timeout": timeout, "memory_bytes": _limits(),
        "cap": 0, "max_bytes": 8 * 1024 * 1024, "sql": None, "table": None, **fields,
    }


def run_server(config: dict, query: ValidatedQuery, params: dict | None, cap: int, timeout: float,
               max_bytes: int = 8 * 1024 * 1024) -> QueryResult:
    """
    Truy vấn đã kiểm trên PostgreSQL / MySQL. Tham số được gắn thành literal trong cây cú pháp
    (bind_params) rồi mới sinh câu SQL; driver không nhận args nên không nội suy chuỗi bằng `%`.
    """
    prepared = query.bind_params(params).qualify(config.get("schema") if config["engine"] == "postgres" else None)
    columns, raw = _spawn(_server_request(config, "query", timeout, sql=prepared.limited(cap + 1), cap=cap,
                                          max_bytes=max_bytes), timeout)
    return _result(columns, raw, cap)


def server_tables(config: dict, timeout: float) -> list[str]:
    _, rows = _spawn(_server_request(config, "tables", timeout), timeout)
    return [str(r[0]) for r in rows]


def server_columns(config: dict, table: str, timeout: float) -> list[dict]:
    _, rows = _spawn(_server_request(config, "columns", timeout, table=table), timeout)
    return [{"name": str(r[0]), "type": str(r[1] or ""), "nullable": str(r[2]).upper() == "YES"} for r in rows]


def run_sqlite(path: Path, query: ValidatedQuery, params: dict | None, cap: int, timeout: float,
               max_bytes: int = 8 * 1024 * 1024, memory_bytes: int | None = None) -> QueryResult:
    return _run_isolated("sqlite", path, query.limited(cap + 1), params, cap, timeout,
                         sorted(query.tables | query.ctes), max_bytes, memory_bytes)


def sqlite_tables(path: Path) -> list[str]:
    con = sqlite3.connect(f"file:{quote(str(path))}?mode=ro", uri=True, check_same_thread=False)
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


def sqlite_columns(path: Path, table: str) -> list[dict]:
    con = sqlite3.connect(f"file:{quote(str(path))}?mode=ro", uri=True, check_same_thread=False)
    try:
        escaped = table.replace('"', '""')
        # table_xinfo (không phải table_info): có cả cột GENERATED - `SELECT *` trả chúng nên metadata
        # cũng phải có. hidden: 0 thường, 2/3 generated; 1 là cột ẩn của bảng ảo, `SELECT *` không trả.
        rows = con.execute(f'PRAGMA table_xinfo("{escaped}")').fetchall()
        return [{"name": r[1], "type": r[2] or "", "nullable": not r[3]} for r in rows if r[6] != 1]
    finally:
        con.close()


# ------------------------------------------------------------------------- DuckDB

_DUCKDB_CONFIG = {
    "enable_external_access": False,
    "autoinstall_known_extensions": False,
    "autoload_known_extensions": False,
    "threads": 2,
    "memory_limit": "1GB",
    "lock_configuration": True,
}


def _duckdb_connect(path: Path):
    import duckdb  # noqa: PLC0415 - chỉ cần khi có nguồn DuckDB

    try:
        return duckdb.connect(str(path), read_only=True, config=dict(_DUCKDB_CONFIG))
    except duckdb.Error as error:
        raise SourceAccessError("Không mở được file DuckDB ở chế độ chỉ đọc.") from error


def _duckdb_exec(path: str, sql_text: str, params: dict | None, cap: int, timeout: float) -> tuple[list[str], list[tuple]]:
    import duckdb  # noqa: PLC0415

    con = _duckdb_connect(Path(path))
    timer = threading.Timer(timeout, con.interrupt)
    timer.start()
    try:
        cursor = con.execute(sql_text, params or None)
        columns = [d[0] for d in cursor.description or []]
        raw = cursor.fetchmany(cap + 1)
    except duckdb.InterruptException:
        raise QueryTimeoutError(f"Truy vấn chạy quá {timeout:g} giây và đã bị huỷ.") from None
    except duckdb.Error as error:
        raise QueryFailedError(f"DuckDB báo lỗi: {str(error).splitlines()[0]}") from None
    finally:
        timer.cancel()
        con.close()
    return columns, raw


def run_duckdb(path: Path, query: ValidatedQuery, params: dict | None, cap: int, timeout: float,
               max_bytes: int = 8 * 1024 * 1024, memory_bytes: int | None = None) -> QueryResult:
    return _run_isolated("duckdb", path, query.limited(cap + 1), params, cap, timeout,
                         sorted(query.tables), max_bytes, memory_bytes)


def duckdb_tables(path: Path) -> list[str]:
    con = _duckdb_connect(path)
    try:
        rows = con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


def duckdb_columns(path: Path, table: str) -> list[dict]:
    con = _duckdb_connect(path)
    try:
        rows = con.execute(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position",
            [table],
        ).fetchall()
        return [{"name": r[0], "type": r[1], "nullable": r[2] == "YES"} for r in rows]
    finally:
        con.close()


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


__all__ = [
    "QueryResult", "QueryTimeoutError", "QueryFailedError", "SourceAccessError", "UnsafeQueryError",
    "resolve_source_file", "json_safe", "run_sqlite", "run_duckdb", "sqlite_tables", "sqlite_columns",
    "duckdb_tables", "duckdb_columns", "quote_identifier",
]
