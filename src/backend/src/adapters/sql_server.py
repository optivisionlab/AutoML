"""
Nguồn PostgreSQL / MySQL cho SQL agent: chạy CHỈ ĐỌC trong tiến trình con cách ly của query_runner
(trần bộ nhớ RLIMIT_AS, bị kill khi quá hạn, mật khẩu đi qua stdin chứ không qua tham số dòng lệnh).

Các lớp bảo vệ ở phía database (độc lập với bộ kiểm cú pháp query_policy):
- Transaction CHỈ ĐỌC: Postgres `default_transaction_read_only` + `set_session(readonly=True)`;
  MySQL `SET SESSION TRANSACTION READ ONLY` + `START TRANSACTION READ ONLY`.
- Hạn thời gian ở server (`statement_timeout` / `max_execution_time`) để server tự dừng việc khi
  tiến trình con bị kill, kèm `lock_timeout` (Postgres).
- Chế độ chuỗi của server được ép khớp với cách sqlglot sinh literal: Postgres
  `standard_conforming_strings = on`; MySQL bỏ ANSI_QUOTES / NO_BACKSLASH_ESCAPES / PIPES_AS_CONCAT.
  Lệch chế độ là lệch cách hiểu chuỗi giữa bộ kiểm và server - cửa cho injection.
- MySQL: không bật nhiều câu một lần (CLIENT.MULTI_STATEMENTS), tắt LOAD DATA LOCAL (`local_infile`):
  server lạ không đọc được file của backend.
- Đọc theo lô (cursor phía server / SSCursor), cộng dung lượng, vượt trần thì dừng và báo.
Bộ kiểm và các lớp trên KHÔNG thay quyền của database: tài khoản khai cho HAutoML phải chỉ có SELECT.
"""
# Standard Libraries
import datetime as dt
import decimal
import re
import time
from typing import Any

# Local Libraries
from src.adapters.query_runner import QueryFailedError, QueryTimeoutError, SourceAccessError


SERVER_ENGINES = ("postgres", "mysql")
DEFAULT_PORTS = {"postgres": 5432, "mysql": 3306}
MAX_TABLES = 5_000
_FETCH_BATCH = 500
_MYSQL_UNSAFE_MODES = {"ANSI", "ANSI_QUOTES", "NO_BACKSLASH_ESCAPES", "PIPES_AS_CONCAT"}
_MYSQL_TIMEOUT_CODES = {3024, 1969, 1317}  # MySQL max_execution_time, MariaDB max_statement_time, bị ngắt

_PG_TABLES = (
    "SELECT table_name FROM information_schema.tables WHERE table_schema = %s "
    "AND table_type IN ('BASE TABLE', 'VIEW') ORDER BY table_name LIMIT %s"
)
_PG_COLUMNS = (
    "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
    "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position"
)
_MYSQL_TABLES = (
    "SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE() "
    "AND table_type IN ('BASE TABLE', 'VIEW') ORDER BY table_name LIMIT %s"
)
_MYSQL_COLUMNS = (
    "SELECT column_name, column_type, is_nullable FROM information_schema.columns "
    "WHERE table_schema = DATABASE() AND table_name = %s ORDER BY ordinal_position"
)


def _plain(value: Any) -> Any:
    """Giá trị driver -> kiểu đơn giản, pickle / JSON được (đi tiếp qua json_safe, frame_for_import)."""
    if value is None or isinstance(value, (bool, int, float, str, bytes, decimal.Decimal, dt.datetime, dt.date)):
        return value
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (set, frozenset)):  # cột SET của MySQL
        return ",".join(sorted(str(v) for v in value))
    if isinstance(value, dt.time):
        return value.isoformat()
    return str(value)  # timedelta (TIME của MySQL / interval), UUID, Range, địa chỉ IP...


def _approx_size(row: tuple) -> int:
    total = 16
    for value in row:
        if isinstance(value, (str, bytes)):
            total += len(value) + 8
        elif isinstance(value, (dict, list)):
            total += len(repr(value))
        else:
            total += 16
    return total


def _fetch(cursor, cap: int, max_bytes: int, deadline: float, timeout: float) -> list[tuple]:
    rows: list[tuple] = []
    used = 0
    while len(rows) <= cap:
        # Hạn TỔNG: statement_timeout của Postgres tính riêng từng lệnh FETCH, không phải cả vòng đọc.
        if time.monotonic() > deadline:
            raise QueryTimeoutError(f"Truy vấn chạy quá {timeout:g} giây và đã bị huỷ.")
        batch = cursor.fetchmany(min(_FETCH_BATCH, cap + 1 - len(rows)))
        if not batch:
            break
        for row in batch:
            used += _approx_size(row)
            if used > max_bytes:
                raise QueryFailedError(
                    f"Kết quả quá lớn (vượt {max_bytes // (1024 * 1024)} MiB) - chọn bớt cột / dòng."
                )
            rows.append(tuple(_plain(v) for v in row))
    return rows


_IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def _first_line(text: Any, request: dict | None = None, limit: int = 300) -> str:
    """Dòng đầu của thông báo lỗi server, bỏ host / địa chỉ IP (API không bao giờ lộ host của kết nối)."""
    line = (str(text or "").strip().splitlines() or [""])[0]
    if request and request.get("host"):
        line = line.replace(str(request["host"]), "***")
    return _IPV4.sub("***", line)[:limit]


def server_exec(request: dict) -> tuple[list[str], list[tuple]]:
    """Chạy trong tiến trình con: op = "query" | "tables" | "columns"."""
    if request["engine"] == "postgres":
        return _postgres(request)
    if request["engine"] == "mysql":
        return _mysql(request)
    raise SourceAccessError(f"Loại database không hỗ trợ: {request['engine']}.")


# ------------------------------------------------------------------------- PostgreSQL

def _pg_connect_error(error: Exception) -> SourceAccessError:
    # Không trả nguyên thông báo libpq: nó chứa host, IP, tên tài khoản.
    text = str(error).lower()
    if "password authentication failed" in text or "no password supplied" in text or "authentication" in text:
        return SourceAccessError("PostgreSQL từ chối đăng nhập: sai tài khoản hoặc mật khẩu.")
    if "does not exist" in text and "database" in text:
        return SourceAccessError("Database không tồn tại trên server PostgreSQL.")
    if "timeout" in text:
        return SourceAccessError("Hết thời gian chờ kết nối PostgreSQL (kiểm tra host, port, mạng).")
    return SourceAccessError("Không kết nối được PostgreSQL (kiểm tra host, port, mạng, tài khoản).")


def _postgres(request: dict) -> tuple[list[str], list[tuple]]:
    import psycopg2  # noqa: PLC0415 - chỉ nạp trong tiến trình con
    from psycopg2 import errors as pg_errors  # noqa: PLC0415
    from psycopg2 import sql as pg_sql  # noqa: PLC0415

    timeout_ms = max(1, int(request["timeout"] * 1000))
    deadline = time.monotonic() + request["timeout"]
    try:
        con = psycopg2.connect(
            host=request["host"], port=request["port"], dbname=request["database"], user=request["username"],
            password=request.get("password") or None, connect_timeout=5, application_name="hautoml-sql-agent",
            options="-c default_transaction_read_only=on", client_encoding="UTF8",
        )
    except psycopg2.Error as error:
        raise _pg_connect_error(error) from None
    try:
        con.set_session(readonly=True, autocommit=False)
        with con.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = %s", (timeout_ms,))
            cur.execute("SET LOCAL lock_timeout = %s", (min(timeout_ms, 2000),))
            cur.execute("SET LOCAL idle_in_transaction_session_timeout = %s", (timeout_ms + 5000,))
            cur.execute("SET LOCAL standard_conforming_strings = on")
            cur.execute(pg_sql.SQL("SET LOCAL search_path TO {}").format(pg_sql.Identifier(request["schema"])))
            # Xác nhận chế độ đã có hiệu lực (không tin vào việc SET không báo lỗi).
            cur.execute("SELECT current_setting('standard_conforming_strings'), current_setting('transaction_read_only')")
            if tuple(cur.fetchone()) != ("on", "on"):
                raise SourceAccessError("Không đặt được phiên chỉ-đọc an toàn trên PostgreSQL.")
            if request["op"] == "tables":
                cur.execute(_PG_TABLES, (request["schema"], MAX_TABLES))
                return ["name"], [tuple(r) for r in cur.fetchall()]
            if request["op"] == "columns":
                cur.execute(_PG_COLUMNS, (request["schema"], request["table"]))
                return ["name", "type", "nullable"], [tuple(r) for r in cur.fetchall()]
        # Cursor phía server: đọc từng lô, không nạp hết kết quả vào bộ nhớ trước khi kịp đo.
        # Không dùng `with`: đóng cursor trong transaction đã lỗi có thể ném lỗi khác che mất lỗi thật;
        # đóng kết nối ở finally là đủ.
        cur = con.cursor(name="hautoml_cursor")
        cur.itersize = _FETCH_BATCH
        cur.execute(request["sql"])
        rows = _fetch(cur, request["cap"], request["max_bytes"], deadline, request["timeout"])
        columns = [d[0] for d in cur.description or []]
        return columns, rows
    except pg_errors.QueryCanceled:
        raise QueryTimeoutError(f"Truy vấn chạy quá {request['timeout']:g} giây và đã bị huỷ.") from None
    except psycopg2.Error as error:
        message = getattr(getattr(error, "diag", None), "message_primary", None) or error
        raise QueryFailedError(f"PostgreSQL báo lỗi: {_first_line(message, request)}") from None
    finally:
        try:
            con.close()  # đóng kết nối = huỷ transaction (không có gì để commit)
        except Exception:  # noqa: BLE001
            pass


# ------------------------------------------------------------------------- MySQL

def _mysql_connect_error(error: Exception) -> SourceAccessError:
    code = error.args[0] if getattr(error, "args", None) else None
    if code in (1045, 1044, 1698):
        return SourceAccessError("MySQL từ chối đăng nhập: sai tài khoản / mật khẩu hoặc không có quyền vào database.")
    if code == 1049:
        return SourceAccessError("Database không tồn tại trên server MySQL.")
    return SourceAccessError("Không kết nối được MySQL (kiểm tra host, port, mạng, tài khoản).")


def _mysql(request: dict) -> tuple[list[str], list[tuple]]:
    import pymysql  # noqa: PLC0415 - chỉ nạp trong tiến trình con
    import pymysql.cursors  # noqa: PLC0415

    timeout_ms = max(1, int(request["timeout"] * 1000))
    deadline = time.monotonic() + request["timeout"]
    try:
        con = pymysql.connect(
            host=request["host"], port=request["port"], user=request["username"],
            password=request.get("password") or "", database=request["database"],
            connect_timeout=5, read_timeout=int(request["timeout"]) + 5, write_timeout=10,
            charset="utf8mb4", local_infile=False, autocommit=False, client_flag=0,
        )
    except pymysql.err.MySQLError as error:
        raise _mysql_connect_error(error) from None
    try:
        with con.cursor() as cur:
            cur.execute("SELECT @@SESSION.sql_mode")
            modes = [m for m in str(cur.fetchone()[0] or "").split(",") if m and m.upper() not in _MYSQL_UNSAFE_MODES]
            cur.execute("SET SESSION sql_mode = %s", (",".join(modes),))
            try:
                cur.execute("SET SESSION max_execution_time = %s", (timeout_ms,))
            except pymysql.err.MySQLError:  # MariaDB: biến khác tên, đơn vị giây
                cur.execute("SET SESSION max_statement_time = %s", (float(request["timeout"]),))
            cur.execute("SELECT @@SESSION.sql_mode, @@SESSION.character_set_client")
            mode, charset = cur.fetchone()
            if set(str(mode or "").upper().split(",")) & _MYSQL_UNSAFE_MODES or str(charset).lower() != "utf8mb4":
                raise SourceAccessError("Không đặt được chế độ phiên an toàn trên MySQL.")
            cur.execute("SET SESSION TRANSACTION READ ONLY")
            cur.execute("START TRANSACTION READ ONLY")
            if request["op"] == "tables":
                cur.execute(_MYSQL_TABLES, (MAX_TABLES,))
                return ["name"], [tuple(r) for r in cur.fetchall()]
            if request["op"] == "columns":
                cur.execute(_MYSQL_COLUMNS, (request["table"],))
                return ["name", "type", "nullable"], [tuple(r) for r in cur.fetchall()]
        cur = con.cursor(pymysql.cursors.SSCursor)  # không đệm: đọc từng lô
        cur.execute(request["sql"])  # không truyền args: pymysql không nội suy % trong câu
        columns = [d[0] for d in cur.description or []]
        rows = _fetch(cur, request["cap"], request["max_bytes"], deadline, request["timeout"])
        return columns, rows
    except pymysql.err.MySQLError as error:
        code = error.args[0] if error.args else None
        if code in _MYSQL_TIMEOUT_CODES or (code == 2013 and "timed out" in str(error).lower()):
            raise QueryTimeoutError(f"Truy vấn chạy quá {request['timeout']:g} giây và đã bị huỷ.") from None
        if code in (1142, 1143, 1044, 1227):
            # Thông báo gốc kèm 'user'@'địa-chỉ-backend': chỉ nói thiếu quyền.
            raise QueryFailedError("MySQL báo lỗi: tài khoản không có quyền với bảng / cột này.") from None
        message = error.args[1] if len(error.args) > 1 else error
        raise QueryFailedError(f"MySQL báo lỗi: {_first_line(message, request)}") from None
    finally:
        try:
            con.close()  # đóng kết nối = huỷ transaction; không đọc nốt kết quả còn lại
        except Exception:  # noqa: BLE001
            pass
