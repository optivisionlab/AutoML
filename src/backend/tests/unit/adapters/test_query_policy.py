"""Bộ kiểm truy vấn chỉ-đọc: tập tấn công thật sự gặp (LLM sinh SQL) và truy vấn hợp lệ."""
# Third-party Libraries
import pytest

# Local Libraries
from src.adapters.query_policy import UnsafeQueryError, validate_mongo_query, validate_sql


TABLES = ["glass", "concrete"]

ATTACKS = [
    "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT * FROM read_parquet('s3://bucket/x.parquet')",
    "SELECT * FROM glob('/home/*')",
    "SELECT load_extension('/tmp/evil.so')",
    "SELECT readfile('/etc/shadow')",
    "WITH x AS (DELETE FROM glass RETURNING *) SELECT * FROM x",
    "SELECT 1; DROP TABLE glass",
    "SELECT * FROM glass; DELETE FROM glass",
    "ATTACH 'other.db' AS other",
    "SELECT * INTO copy_of_glass FROM glass",
    "PRAGMA table_info(glass)",
    "COPY glass TO 'out.csv'",
    "INSTALL httpfs",
    "DELETE FROM glass",
    "UPDATE glass SET Type = 1",
    "INSERT INTO glass VALUES (1)",
    "CREATE TABLE t AS SELECT * FROM glass",
    "SELECT * FROM main.glass",
    "SELECT * FROM other_db.glass",
    "SELECT * FROM secret_table",
    "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT * FROM r",
    "SELECT * FROM glass FOR UPDATE",
    "SELECT getenv('HOME')",
    "SELECT my_udf(RI) FROM glass",
    "",
    "   ",
]


@pytest.mark.parametrize("dialect", ["sqlite", "duckdb", "postgres", "mysql"])
@pytest.mark.parametrize("sql", ATTACKS)
def test_unsafe_or_out_of_scope_sql_is_rejected(sql, dialect):
    with pytest.raises(UnsafeQueryError):
        validate_sql(sql, dialect, TABLES)


VALID = [
    "SELECT RI, Na, Type FROM glass WHERE Mg > 3",
    "SELECT Type, COUNT(*) AS n, AVG(RI) AS ri FROM glass GROUP BY Type ORDER BY Type",
    "WITH g AS (SELECT * FROM glass WHERE Ba = 0) SELECT COUNT(*) FROM g",
    "SELECT * FROM glass UNION ALL SELECT * FROM glass",
    "SELECT ROUND(Na / Si, 4) AS ratio, CASE WHEN Fe > 0 THEN 1 ELSE 0 END AS has_fe FROM glass LIMIT 5",
    "SELECT a.RI FROM glass AS a JOIN concrete AS c ON a.Type = c.age",
]


@pytest.mark.parametrize("dialect", ["sqlite", "duckdb", "postgres", "mysql"])
@pytest.mark.parametrize("sql", VALID)
def test_read_only_sql_is_accepted_and_rewritten(sql, dialect):
    validated = validate_sql(sql, dialect, TABLES)
    assert validated.tables <= set(TABLES)
    wrapped = validated.limited(21)
    assert wrapped.upper().startswith("SELECT * FROM (") and wrapped.rstrip().endswith("LIMIT 21")


def test_table_names_are_matched_case_insensitively_and_canonicalised():
    assert validate_sql("SELECT * FROM GLASS", "sqlite", TABLES).tables == {"glass"}


def test_unsupported_dialect_is_refused():
    with pytest.raises(UnsafeQueryError, match="Chưa hỗ trợ"):
        validate_sql("SELECT 1", "oracle", TABLES)


@pytest.mark.parametrize("query", [
    {"kind": "aggregate", "collection": "glass", "pipeline": [{"$out": "copy"}]},
    {"kind": "aggregate", "collection": "glass", "pipeline": [{"$merge": {"into": "x"}}]},
    {"kind": "aggregate", "collection": "glass", "pipeline": [{"$lookup": {"from": "users"}}]},
    {"kind": "aggregate", "collection": "glass", "pipeline": [{"$match": {"$expr": {"$function": {"body": "x"}}}}]},
    {"kind": "find", "collection": "glass", "filter": {"$where": "this.RI > 1"}},
    {"kind": "find", "collection": "system.users"},
    {"kind": "find", "collection": "glass", "sort": {"RI": 2}},
    {"kind": "find", "collection": "glass", "hint": "x"},
    {"kind": "aggregate", "collection": "glass", "pipeline": []},
    {"kind": "aggregate", "collection": "glass", "pipeline": [{"$match": {}, "$project": {}}]},
    {"kind": "update", "collection": "glass"},
])
def test_unsafe_mongo_queries_are_rejected(query):
    with pytest.raises(UnsafeQueryError):
        validate_mongo_query(query)


def test_deeply_nested_mongo_filter_is_rejected():
    nested = {"RI": 1}
    for _ in range(20):
        nested = {"$and": [nested]}
    with pytest.raises(UnsafeQueryError, match="sâu"):
        validate_mongo_query({"kind": "find", "collection": "glass", "filter": nested})


def test_safe_mongo_queries_are_normalised():
    spec = validate_mongo_query({
        "kind": "aggregate", "collection": "glass",
        "pipeline": [{"$match": {"Ba": 0}}, {"$group": {"_id": "$Type", "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}],
        "row_limit": 20,
    })
    assert spec == {"kind": "aggregate", "collection": "glass",
                    "pipeline": [{"$match": {"Ba": 0}}, {"$group": {"_id": "$Type", "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}]}


def test_cte_in_a_subquery_does_not_hide_a_real_table_outside_it():
    # Codex D5: tên CTE gom toàn cục từng cho bảng thật sqlite_master ở câu ngoài lọt qua.
    sql = ("SELECT name FROM sqlite_master WHERE EXISTS "
           "(WITH sqlite_master AS (SELECT 1) SELECT 1 FROM sqlite_master)")
    with pytest.raises(UnsafeQueryError, match="sqlite_master"):
        validate_sql(sql, "sqlite", TABLES)


def test_string_padding_functions_are_not_whitelisted():
    with pytest.raises(UnsafeQueryError):
        validate_sql("SELECT printf('%1000000000s', 'x')", "sqlite", TABLES)


# --------------------------------------------------------------------- PostgreSQL / MySQL

POSTGRES_ATTACKS = [
    "SELECT pg_read_file('/etc/passwd')",
    "SELECT pg_read_binary_file('/etc/passwd')",
    "SELECT pg_ls_dir('.')",
    "SELECT pg_sleep(30)",
    "SELECT * FROM glass, LATERAL (SELECT pg_sleep(1)) AS s",
    "SELECT lo_import('/etc/passwd')",
    "SELECT dblink('host=evil', 'select 1')",
    "SELECT * FROM query_to_xml('select * from secret_table', true, true, '')",
    "SELECT set_config('search_path', 'other', false)",
    "SELECT current_setting('data_directory')",
    "SELECT txid_current()",
    "SELECT nextval('seq')",
    "SELECT pg_advisory_lock(1)",
    "SELECT pg_terminate_backend(1)",
    "SELECT repeat('x', 1000000000)",
    "SELECT lpad('x', 1000000000, 'y')",
    "SELECT inet_server_addr()",
    "SELECT * FROM pg_shadow",
    "SELECT * FROM pg_catalog.pg_authid",
    "SELECT * FROM information_schema.tables",
    "SELECT * FROM public.glass",
    "SELECT RI FROM glass WHERE Type = $1",
    "COPY glass TO PROGRAM 'id'",
    "SELECT * FROM glass FOR SHARE",
    "DO $$ BEGIN PERFORM 1; END $$",
    "CALL some_procedure()",
    "LISTEN chan",
    "NOTIFY chan",
    # Review R1: từ khoá tài khoản viết không ngoặc (sqlglot đọc thành cột).
    "SELECT user AS who FROM glass",
    "SELECT current_role",
    "SELECT type FROM glass WHERE user = 'hautoml_ro'",
    # Review R2: generate_series + string_agg -> server hết bộ nhớ trước timeout.
    "SELECT length(string_agg('xxxxxxxxxx', '')) AS n FROM (SELECT generate_series(1, 200000000)) AS s",
    "SELECT count(*) FROM (SELECT generate_series(1, 2000000000)) AS s",
]

MYSQL_ATTACKS = [
    "SELECT LOAD_FILE('/etc/passwd')",
    "SELECT SLEEP(30)",
    "SELECT BENCHMARK(1000000000, MD5('x'))",
    "SELECT GET_LOCK('a', 10)",
    "SELECT @@datadir",
    "SELECT @@session.sql_mode",
    "SELECT @a := 1",
    "SELECT * INTO @v FROM glass",
    "SELECT * FROM glass INTO OUTFILE '/tmp/x'",
    "SELECT * FROM glass LOCK IN SHARE MODE",
    "SELECT * FROM mysql.user",
    "SELECT * FROM information_schema.tables",
    "SELECT REPEAT('x', 1000000000)",
    "SELECT SPACE(1000000000)",
    "SELECT USER()",
    "HANDLER glass OPEN",
    "LOAD DATA LOCAL INFILE '/etc/passwd' INTO TABLE glass",
    "SELECT 1 FROM DUAL",
    "VALUES ROW(1)",
]


@pytest.mark.parametrize("sql", POSTGRES_ATTACKS)
def test_postgres_specific_attacks_are_rejected(sql):
    with pytest.raises(UnsafeQueryError):
        validate_sql(sql, "postgres", TABLES)


@pytest.mark.parametrize("sql", MYSQL_ATTACKS)
def test_mysql_specific_attacks_are_rejected(sql):
    with pytest.raises(UnsafeQueryError):
        validate_sql(sql, "mysql", TABLES)


@pytest.mark.parametrize("dialect,sql", [
    ("postgres", "SELECT date_trunc('month', now()) AS m, age(now()) AS a, RI::text AS r FROM glass"),
    ("postgres", "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY RI) FROM glass"),
    ("postgres", "SELECT RI FROM glass WHERE Na ILIKE '1%'"),
    ("mysql", "SELECT `RI`, DATE_FORMAT(NOW(), '%Y') AS y, IFNULL(Fe, 0) AS fe FROM `glass`"),
    ("mysql", "SELECT Type, GROUP_CONCAT(RI) AS ris FROM glass GROUP BY Type"),
])
def test_everyday_server_sql_is_accepted(dialect, sql):
    assert validate_sql(sql, dialect, TABLES).tables == {"glass"}


@pytest.mark.parametrize("dialect", ["postgres", "mysql"])
def test_comments_never_reach_the_server(dialect):
    # MySQL CHẠY nội dung /*! ... */ - câu gửi đi không được còn comment nào.
    validated = validate_sql("SELECT RI /*! , SLEEP(5) */ FROM glass -- trailing", dialect, TABLES)
    assert "/*" not in validated.sql and "--" not in validated.sql
    assert "/*" not in validated.limited(5) and "SLEEP" not in validated.limited(5).upper()


@pytest.mark.parametrize("dialect", ["postgres", "mysql"])
@pytest.mark.parametrize("value", ["a'b", "abc\\", "x\\' OR 1=1 -- ", "100%", "%(t)s", "line\nbreak", "ổn định"])
def test_params_are_inlined_as_round_trippable_literals(dialect, value):
    import sqlglot
    from sqlglot import exp

    bound = validate_sql("SELECT RI FROM glass WHERE Na = :v AND Type = :t", dialect, TABLES).bind_params(
        {"v": value, "t": 2})
    where = sqlglot.parse_one(bound.limited(5), read=dialect).find(exp.Where)
    literals = [lit for lit in where.find_all(exp.Literal)]
    assert value in [lit.this for lit in literals if lit.is_string] and ":v" not in bound.sql


@pytest.mark.parametrize("params,message", [
    ({}, "Thiếu giá trị"),
    ({"v": {"$gt": 1}}, "chỉ nhận"),
    ({"v": float("nan")}, "hữu hạn"),
    ({"v": "a\x00b"}, "NUL"),
])
def test_bad_params_are_refused(params, message):
    validated = validate_sql("SELECT RI FROM glass WHERE Na = :v", "postgres", TABLES)
    with pytest.raises(UnsafeQueryError, match=message):
        validated.bind_params(params)


@pytest.mark.parametrize("dialect", ["postgres", "mysql"])
def test_positional_placeholders_are_refused_when_binding(dialect):
    validated = validate_sql("SELECT RI FROM glass WHERE Type = ?", dialect, TABLES)
    with pytest.raises(UnsafeQueryError, match="tham số có tên"):
        validated.bind_params({"t": 1})


def test_quoted_or_qualified_user_column_is_still_a_real_column():
    for sql in ('SELECT "user" FROM glass', "SELECT g.user FROM glass AS g"):
        assert validate_sql(sql, "postgres", TABLES).tables == {"glass"}
    assert validate_sql("SELECT user FROM glass", "mysql", TABLES).tables == {"glass"}   # MySQL: cột thường
