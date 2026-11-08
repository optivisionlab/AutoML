"""
Kiểm tra truy vấn CHỈ ĐỌC trước khi chạy trên nguồn dữ liệu ngoài.

Truy vấn có thể do LLM sinh ra, nên không tin vào tiền tố "SELECT": `WITH x AS (DELETE ...) SELECT`
hay `SELECT ... INTO` đều mở đầu bằng SELECT. Ở đây phân tích cú pháp toàn bộ (sqlglot) rồi duyệt
cả cây: đúng một câu SELECT/UNION, không có thao tác ghi, không đọc file/mạng/extension, chỉ đọc
các bảng thật của kết nối (hoặc CTE khai trong chính câu đó).

Bộ kiểm cú pháp KHÔNG thay quyền của database: bộ chạy (query_runner) còn mở kết nối chỉ-đọc.
"""
# Standard Libraries
from dataclasses import dataclass, field
from typing import Any

# Third-party Libraries
import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError
from sqlglot.optimizer.scope import build_scope


MAX_SQL_LENGTH = 20_000
MAX_MONGO_DEPTH = 12
MAX_MONGO_NODES = 2_000
MAX_PIPELINE_STAGES = 20

SQL_DIALECTS = {"sqlite": "sqlite", "duckdb": "duckdb", "postgres": "postgres", "mysql": "mysql"}
# Database dạng server: tham số được gắn thẳng thành literal (bind_params), có danh sách hàm riêng.
SERVER_DIALECTS = {"postgres", "mysql"}


class UnsafeQueryError(ValueError):
    """Truy vấn bị từ chối: không an toàn, không hợp lệ hoặc đọc ngoài phạm vi kết nối."""


# Thao tác ghi / quản trị / đọc file: có ở BẤT KỲ đâu trong cây (kể cả trong CTE) là từ chối.
_DENIED_NODES = tuple(
    getattr(exp, name) for name in (
        "Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter", "Command", "Pragma",
        "Attach", "Detach", "Copy", "Into", "Lock", "Set", "Use", "Transaction", "Commit",
        "Rollback", "Grant", "LoadData", "Describe", "Show", "Install", "Export", "Summarize",
        "Kill", "Analyze", "Cache", "Uncache", "Refresh", "TruncateTable", "ReadCSV", "ReadParquet",
        # Optimizer hint /*+ ... */: MySQL MAX_EXECUTION_TIME / SET_VAR(sql_mode=...) ghi đè được
        # timeout và chế độ chuỗi mà bộ chạy đã ép cho phiên.
        "Hint",
    ) if hasattr(exp, name)
)

# Hàm cấm theo tên (đọc/ghi file, extension, biến môi trường), dù sqlglot có nhận dạng hay không.
_DENIED_FUNCTIONS = {
    "load_extension", "readfile", "writefile", "edit", "fts3_tokenizer",
    "read_csv", "read_csv_auto", "read_parquet", "parquet_scan", "read_json", "read_json_auto",
    "read_json_objects", "read_ndjson", "read_text", "read_blob", "glob", "getenv",
    "current_setting", "sniff_csv", "query", "query_table",
}

# Hàm cấm thêm theo dialect của database dạng server. Phần lớn đã bị chặn vì sqlglot không nhận
# dạng (danh sách cho phép bên dưới); liệt kê tên ở đây để luôn bị chặn và báo đúng lý do.
# repeat / lpad / rpad / space: một lời gọi bắt server cấp phát tới 1 GB - DoS database của người dùng.
_DENIED_FUNCTIONS_BY_DIALECT = {
    "postgres": {
        "pg_sleep", "pg_sleep_for", "pg_sleep_until", "pg_read_file", "pg_read_binary_file", "pg_ls_dir",
        "pg_stat_file", "pg_ls_logdir", "pg_ls_waldir", "pg_ls_tmpdir", "pg_ls_archive_statusdir",
        "lo_import", "lo_export", "lo_get", "lo_put", "lo_open", "lo_create", "lo_unlink", "lo_from_bytea",
        "dblink", "dblink_exec", "dblink_connect", "dblink_send_query", "query_to_xml", "query_to_xmlschema",
        "query_to_xml_and_xmlschema", "cursor_to_xml", "table_to_xml", "table_to_xmlschema", "schema_to_xml",
        "database_to_xml", "set_config", "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf",
        "pg_rotate_logfile", "pg_notify", "pg_advisory_lock", "pg_advisory_xact_lock", "pg_try_advisory_lock",
        "pg_advisory_lock_shared", "txid_current", "pg_current_xact_id", "nextval", "setval", "currval",
        "lastval", "inet_server_addr", "inet_server_port", "pg_postmaster_start_time", "pg_conf_load_time",
        "repeat", "pad", "lpad", "rpad",
        # generate_series trong subquery + string_agg / array_agg dựng một giá trị khổng lồ: server
        # hết bộ nhớ trước khi statement_timeout kịp cắt (đã tái hiện: ~2 GB rồi "out of memory").
        "generate_series", "generateseries", "exploding_generate_series", "explodinggenerateseries",
    },
    "mysql": {
        "load_file", "sleep", "benchmark", "get_lock", "release_lock", "release_all_locks", "is_free_lock",
        "is_used_lock", "master_pos_wait", "source_pos_wait", "sys_eval", "sys_exec", "user", "system_user",
        "repeat", "pad", "lpad", "rpad", "space",
    },
}
# Thông tin server / tài khoản (phiên bản giúp dò lỗ hổng): chặn ở cả hai dialect server. So khớp cả
# tên lớp sqlglot vì sql_name() của hàm đã nhận dạng có thể khác tên người dùng viết (version -> CURRENT_VERSION).
_SERVER_INFO_FUNCTIONS = {
    "version", "current_version", "currentversion", "current_user", "currentuser", "session_user",
    "sessionuser", "system_user", "user", "current_role",
}
# Postgres: từ khoá chuẩn SQL viết KHÔNG ngoặc (`SELECT user`) là hàm tài khoản, nhưng sqlglot đọc
# thành một cột - phải chặn ở dạng cột trần, không nháy, không tiền tố bảng ("user" có nháy / g.user
# vẫn là cột thật).
_POSTGRES_NILADIC_IDENTITY = {"user", "current_user", "session_user", "current_role"}

# Hàm sqlglot KHÔNG nhận dạng (exp.Anonymous) chỉ được dùng nếu nằm trong danh sách này.
_ALLOWED_ANONYMOUS = {
    "julianday", "instr", "date", "time", "datetime", "strftime", "unixepoch",
    "total", "typeof", "hex", "quote", "char", "unicode", "median", "mode", "quantile",
    "quantile_cont", "quantile_disc", "date_part", "date_trunc", "epoch", "regexp_matches",
    "list_value", "round_even",
}
# Hàm thuần (tính toán / ngày giờ / chuỗi) sqlglot chưa nhận dạng ở từng dialect server.
_ALLOWED_ANONYMOUS_BY_DIALECT = {
    "postgres": {"age", "cardinality", "clock_timestamp", "every", "isfinite", "make_date", "octet_length",
                 "regexp_match", "statement_timestamp", "to_json", "jsonb_extract_path_text", "timeofday"},
    "mysql": {"bin", "conv", "crc32", "field", "find_in_set", "json_length", "json_unquote", "makedate", "now",
              "oct", "period_diff", "sysdate", "unix_timestamp", "weekday"},
}


@dataclass
class ValidatedQuery:
    """Câu SQL đã kiểm: `sql` là bản chuẩn hoá do sqlglot sinh lại (không phải chuỗi gốc)."""
    sql: str
    dialect: str
    tables: set[str] = field(default_factory=set)
    expression: Any = None
    # Tên CTE khai trong câu (SQLite báo đọc CTE như đọc một bảng tên đó).
    ctes: set[str] = field(default_factory=set)
    # Danh sách bảng thật của kết nối (None = không kiểm) - qualify() dùng để chuẩn hoá tên.
    allowed: list[str] | None = None

    def limited(self, limit: int) -> str:
        """Bọc câu đã kiểm trong SELECT * FROM (...) LIMIT n - chặn đọc quá giới hạn ngay ở database."""
        wrapped = exp.select("*").from_(exp.Subquery(this=self.expression.copy(), alias=exp.TableAlias(
            this=exp.to_identifier("hautoml_q")))).limit(int(limit))
        # comments=False: MySQL CHẠY nội dung comment dạng /*! ... */ - không bao giờ gửi comment đi.
        return wrapped.sql(dialect=self.dialect, comments=False)

    def bind_params(self, params: dict | None) -> "ValidatedQuery":
        """
        Gắn tham số `:ten` thành literal ngay trong cây cú pháp (cho Postgres / MySQL): driver không
        phải nội suy chuỗi bằng `%` (dấu % trong LIKE 'a%' không còn gây lỗi), và literal do sqlglot
        sinh theo đúng dialect - bộ chạy ép chế độ chuỗi của server khớp (standard_conforming_strings
        bật / không NO_BACKSLASH_ESCAPES). Chỉ nhận giá trị đơn: chuỗi, số, bool, NULL.
        """
        params = params or {}
        expression = self.expression.copy()
        for node in list(expression.find_all(exp.Placeholder)):
            name = node.name
            if not name or name == "?":
                raise UnsafeQueryError("Dùng tham số có tên (:ten) kèm params, không dùng ? hay %s.")
            if name not in params:
                raise UnsafeQueryError(f"Thiếu giá trị cho tham số :{name} trong params.")
            node.replace(_literal(params[name], name))
        return ValidatedQuery(sql=expression.sql(dialect=self.dialect, comments=False), dialect=self.dialect,
                              tables=set(self.tables), expression=expression, ctes=set(self.ctes), allowed=self.allowed)

    def qualify(self, schema: str | None = None) -> "ValidatedQuery":
        """
        Cho Postgres / MySQL: viết lại mọi bảng thật thành đúng tên trong metadata (có nháy), giữ tên
        cũ làm alias để cột `glass.x` vẫn đúng, và (Postgres) gắn schema của kết nối. Không còn tên
        trần để server phân giải: Postgres luôn tìm pg_catalog TRƯỚC search_path, và so hoa/thường
        của bộ kiểm khác quy tắc của server (Postgres gấp tên không nháy về chữ thường).
        Chỉ dùng cho câu sắp chạy - câu lưu lại (`sql`) vẫn là bản chưa qualify để kiểm lại được.
        """
        if self.allowed is None:
            return self
        exact = set(self.allowed)
        lower = {t.lower(): t for t in self.allowed}
        expression = self.expression.copy()
        try:
            root_scope = build_scope(expression)
            scopes = list(root_scope.traverse()) if root_scope else []
        except Exception as error:  # noqa: BLE001
            raise UnsafeQueryError(f"Không phân tích được phạm vi bảng của câu SQL ({type(error).__name__}).") from None
        seen: set[int] = set()
        for scope in scopes:
            for source in scope.sources.values():
                if not isinstance(source, exp.Table) or id(source) in seen:
                    continue
                seen.add(id(source))
                identifier = source.this
                name = identifier.name
                effective = name.lower() if self.dialect == "postgres" and not identifier.args.get("quoted") else name
                canonical = effective if effective in exact else lower.get(name.lower())
                if canonical is None:
                    raise UnsafeQueryError(f"Bảng '{name}' không tồn tại trong kết nối này.")
                if not source.alias:
                    source.set("alias", exp.TableAlias(this=identifier.copy()))
                source.set("this", exp.to_identifier(canonical, quoted=True))
                if schema:
                    source.set("db", exp.to_identifier(schema, quoted=True))
        return ValidatedQuery(sql=expression.sql(dialect=self.dialect, comments=False), dialect=self.dialect,
                              tables=set(self.tables), expression=expression, ctes=set(self.ctes), allowed=self.allowed)


def _literal(value: Any, name: str) -> exp.Expression:
    if value is None or isinstance(value, bool):
        return exp.convert(value)
    if isinstance(value, int):
        return exp.convert(value)
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise UnsafeQueryError(f"Tham số :{name} phải là số hữu hạn.")
        return exp.convert(value)
    if isinstance(value, str):
        if len(value) > 10_000 or "\x00" in value:
            raise UnsafeQueryError(f"Tham số :{name} quá dài hoặc chứa ký tự NUL.")
        return exp.convert(value)
    raise UnsafeQueryError(f"Tham số :{name} chỉ nhận chuỗi, số, true/false hoặc null.")


def _function_name(node: exp.Func) -> str:
    if isinstance(node, exp.Anonymous):
        return str(node.name or "").lower()
    try:
        return node.sql_name().lower()
    except Exception:  # noqa: BLE001 - hàm lạ: coi như không nhận dạng
        return type(node).__name__.lower()


def _function_names(node: exp.Func) -> set[str]:
    """Mọi tên để so với danh sách cấm: tên SQL sqlglot sinh và tên lớp AST."""
    return {_function_name(node), type(node).__name__.lower()}


def validate_sql(sql: str, dialect: str, allowed_tables: list[str] | None = None) -> ValidatedQuery:
    """
    Chỉ chấp nhận đúng MỘT câu SELECT (có thể UNION / CTE không đệ quy), chỉ đọc các bảng của
    kết nối. allowed_tables=None thì không kiểm tên bảng (vd lúc chưa đọc được metadata).

    Raises:
        UnsafeQueryError: kèm lý do người dùng / agent đọc hiểu được.
    """
    read = SQL_DIALECTS.get(dialect)
    if read is None:
        raise UnsafeQueryError(f"Chưa hỗ trợ truy vấn cho loại database '{dialect}'.")
    if not isinstance(sql, str) or not sql.strip():
        raise UnsafeQueryError("Câu SQL rỗng.")
    if len(sql) > MAX_SQL_LENGTH:
        raise UnsafeQueryError(f"Câu SQL quá dài (tối đa {MAX_SQL_LENGTH} ký tự).")
    try:
        statements = [s for s in sqlglot.parse(sql, read=read) if s is not None]
    except ParseError as error:
        raise UnsafeQueryError(f"Không phân tích được câu SQL: {str(error).splitlines()[0]}") from None
    if len(statements) != 1:
        raise UnsafeQueryError("Chỉ được chạy đúng MỘT câu SQL (không nối nhiều câu bằng dấu ;).")
    root = statements[0]
    if not isinstance(root, (exp.Select, exp.SetOperation)):
        raise UnsafeQueryError(f"Chỉ cho phép truy vấn đọc (SELECT); đây là câu {type(root).__name__.upper()}.")

    server = read in SERVER_DIALECTS
    denied_functions = _DENIED_FUNCTIONS | _DENIED_FUNCTIONS_BY_DIALECT.get(read, set())
    if server:
        denied_functions = denied_functions | _SERVER_INFO_FUNCTIONS
    allowed_anonymous = _ALLOWED_ANONYMOUS | _ALLOWED_ANONYMOUS_BY_DIALECT.get(read, set())
    cte_names: set[str] = set()
    for node in root.walk():
        if isinstance(node, _DENIED_NODES):
            raise UnsafeQueryError(f"Truy vấn chứa thao tác không được phép: {type(node).__name__.upper()}.")
        # MySQL @@biến_hệ_thống / @biến (đọc cấu hình server, gán biến phiên); Postgres $1 (tham số vị trí).
        if server and isinstance(node, (exp.SessionParameter, exp.Parameter)):
            raise UnsafeQueryError("Không dùng biến hệ thống / biến phiên (@, @@) hay tham số vị trí ($1); "
                                   "dùng :ten kèm params.")
        if (read == "postgres" and isinstance(node, exp.Column) and not node.table
                and isinstance(node.this, exp.Identifier) and not node.this.args.get("quoted")
                and node.name.lower() in _POSTGRES_NILADIC_IDENTITY):
            raise UnsafeQueryError(f"'{node.name}' là thông tin tài khoản database - không được dùng; cột thật tên "
                                   f"này phải viết trong nháy kép (\"{node.name}\").")
        # MySQL _latin1'...' / _binary'...': đổi bảng mã của literal - một nguồn lệch cách hiểu chuỗi.
        if server and isinstance(node, exp.Introducer):
            raise UnsafeQueryError("Không dùng tiền tố bảng mã cho chuỗi (_latin1'...', _binary'...').")
        if isinstance(node, exp.With) and node.args.get("recursive"):
            raise UnsafeQueryError("Không cho phép CTE đệ quy (WITH RECURSIVE).")
        if isinstance(node, exp.Select) and node.args.get("locks"):
            raise UnsafeQueryError("Không cho phép khoá dòng (FOR UPDATE / FOR SHARE).")
        if isinstance(node, exp.CTE) and node.alias:
            cte_names.add(node.alias.lower())
        if isinstance(node, exp.Func):
            name = _function_name(node)
            if _function_names(node) & denied_functions:
                raise UnsafeQueryError(f"Hàm '{name}' không được phép (đọc/ghi file, mạng, khoá, cấu hình hoặc "
                                       "cấp phát quá lớn).")
            if isinstance(node, exp.Anonymous) and name not in allowed_anonymous:
                raise UnsafeQueryError(f"Hàm '{name}' chưa được hỗ trợ trong truy vấn an toàn.")

    known = {t.lower(): t for t in (allowed_tables or [])}
    for table in root.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            raise UnsafeQueryError("Không cho phép hàm bảng trong FROM (vd read_csv, glob).")
        if table.args.get("db") or table.args.get("catalog"):
            raise UnsafeQueryError(f"Không được chỉ định schema/database khác cho bảng '{table.name}'.")

    # Bảng thật = nguồn mà scope của sqlglot phân giải thành Table (không phải CTE). Gom tên CTE
    # toàn cục là sai: CTE "sqlite_master" khai trong một subquery không che bảng sqlite_master thật
    # ở câu ngoài.
    try:
        root_scope = build_scope(root)
        scopes = list(root_scope.traverse()) if root_scope else []
    except Exception as error:  # noqa: BLE001 - không phân giải được scope thì không chạy
        raise UnsafeQueryError(f"Không phân tích được phạm vi bảng của câu SQL ({type(error).__name__}).") from None
    tables: set[str] = set()
    for scope in scopes:
        for source in scope.sources.values():
            if not isinstance(source, exp.Table):
                continue
            name = source.name
            if allowed_tables is not None and name.lower() not in known:
                raise UnsafeQueryError(f"Bảng '{name}' không tồn tại trong kết nối này.")
            tables.add(known.get(name.lower(), name))

    return ValidatedQuery(sql=root.sql(dialect=read, comments=False), dialect=read, tables=tables, expression=root,
                          ctes=cte_names, allowed=list(allowed_tables) if allowed_tables is not None else None)


# ------------------------------------------------------------------------- MongoDB

ALLOWED_PIPELINE_STAGES = {"$match", "$project", "$sort", "$limit", "$skip", "$group", "$unwind", "$count"}

# Toán tử chạy code, ghi dữ liệu hoặc đọc collection khác: cấm ở mọi độ sâu.
DENIED_MONGO_OPERATORS = {
    "$where", "$function", "$accumulator", "$out", "$merge", "$lookup", "$unionWith",
    "$graphLookup", "$eval", "$currentOp", "$listSessions", "$planCacheStats", "$collStats",
    "$indexStats", "$documents", "$changeStream",
}


def _check_mongo_value(value: Any, depth: int, counter: list[int]) -> None:
    counter[0] += 1
    if counter[0] > MAX_MONGO_NODES:
        raise UnsafeQueryError("Truy vấn MongoDB quá lớn.")
    if depth > MAX_MONGO_DEPTH:
        raise UnsafeQueryError(f"Truy vấn MongoDB lồng quá sâu (tối đa {MAX_MONGO_DEPTH} mức).")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise UnsafeQueryError("Khoá trong truy vấn MongoDB phải là chuỗi.")
            if key in DENIED_MONGO_OPERATORS:
                raise UnsafeQueryError(f"Toán tử MongoDB '{key}' không được phép.")
            _check_mongo_value(item, depth + 1, counter)
    elif isinstance(value, list):
        for item in value:
            _check_mongo_value(item, depth + 1, counter)
    elif isinstance(value, str) and value.startswith("$$") and value[2:].split(".")[0].upper() in {"CLUSTER_TIME", "USER_ROLES"}:
        raise UnsafeQueryError("Biến hệ thống MongoDB này không được phép.")


def _check_collection(name: Any) -> str:
    if not isinstance(name, str) or not name or "$" in name or "\x00" in name or name.startswith("system."):
        raise UnsafeQueryError("Tên collection không hợp lệ.")
    return name


def validate_mongo_query(query: dict) -> dict:
    """
    Kiểm truy vấn MongoDB chỉ-đọc: {"kind": "find", collection, filter?, projection?, sort?} hoặc
    {"kind": "aggregate", collection, pipeline}. Trả bản đã chuẩn hoá.
    """
    if not isinstance(query, dict):
        raise UnsafeQueryError("Truy vấn MongoDB phải là object JSON.")
    kind = query.get("kind")
    collection = _check_collection(query.get("collection"))
    counter = [0]
    if kind == "find":
        allowed = {"kind", "collection", "filter", "projection", "sort", "row_limit"}
        if set(query) - allowed:
            raise UnsafeQueryError(f"Trường không hỗ trợ trong find: {sorted(set(query) - allowed)}.")
        spec = {"kind": "find", "collection": collection}
        for part in ("filter", "projection", "sort"):
            value = query.get(part) or {}
            if not isinstance(value, dict):
                raise UnsafeQueryError(f"'{part}' phải là object.")
            _check_mongo_value(value, 1, counter)
            spec[part] = value
        if any(v not in (1, -1) for v in spec["sort"].values()):
            raise UnsafeQueryError("sort chỉ nhận 1 (tăng) hoặc -1 (giảm).")
        return spec
    if kind == "aggregate":
        allowed = {"kind", "collection", "pipeline", "row_limit"}
        if set(query) - allowed:
            raise UnsafeQueryError(f"Trường không hỗ trợ trong aggregate: {sorted(set(query) - allowed)}.")
        pipeline = query.get("pipeline")
        if not isinstance(pipeline, list) or not pipeline:
            raise UnsafeQueryError("pipeline phải là danh sách stage, không rỗng.")
        if len(pipeline) > MAX_PIPELINE_STAGES:
            raise UnsafeQueryError(f"pipeline quá dài (tối đa {MAX_PIPELINE_STAGES} stage).")
        for stage in pipeline:
            if not isinstance(stage, dict) or len(stage) != 1:
                raise UnsafeQueryError("Mỗi stage phải là object có đúng một khoá.")
            (name, body), = stage.items()
            if name not in ALLOWED_PIPELINE_STAGES:
                raise UnsafeQueryError(
                    f"Stage '{name}' không được phép; chỉ dùng: {', '.join(sorted(ALLOWED_PIPELINE_STAGES))}."
                )
            _check_mongo_value(body, 1, counter)
        return {"kind": "aggregate", "collection": collection, "pipeline": pipeline}
    raise UnsafeQueryError("kind phải là 'find' hoặc 'aggregate'.")
