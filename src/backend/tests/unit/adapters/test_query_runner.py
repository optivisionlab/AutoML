"""Bộ chạy chỉ-đọc trên dữ liệu thật (Glass) trong SQLite / DuckDB: kết quả đúng, giới hạn, lớp bảo vệ thứ hai."""
# Standard Libraries
import os

# Third-party Libraries
import pytest
import sqlglot

# Local Libraries
from src.adapters.query_policy import ValidatedQuery, validate_sql
from src.adapters.query_runner import (
    QueryFailedError, QueryTimeoutError, SourceAccessError, duckdb_columns, duckdb_tables,
    resolve_source_file, run_duckdb, run_sqlite, sqlite_columns, sqlite_tables,
)
from tests.database_sources import glass_frame, make_duckdb, make_sqlite


@pytest.fixture
def sources(tmp_path):
    base = tmp_path / "sources"
    base.mkdir()
    return base, make_sqlite(base), make_duckdb(base)


def _raw(sql: str, dialect: str) -> ValidatedQuery:
    """Bỏ qua bộ kiểm cú pháp - để chứng minh database tự chặn (lớp bảo vệ thứ hai)."""
    expression = sqlglot.parse_one(sql, read=dialect)
    return ValidatedQuery(sql=sql, dialect=dialect, expression=expression)


def test_files_outside_the_source_directory_are_refused(sources, tmp_path):
    base, sqlite_path, _ = sources
    assert resolve_source_file("glass.sqlite", base) == sqlite_path.resolve()
    outside = tmp_path / "secret.sqlite"
    outside.write_bytes(sqlite_path.read_bytes())
    for name in ("../secret.sqlite", str(outside), "missing.sqlite", "", "a\x00b"):
        with pytest.raises(SourceAccessError):
            resolve_source_file(name, base)
    os.symlink(outside, base / "link.sqlite")
    with pytest.raises(SourceAccessError):
        resolve_source_file("link.sqlite", base)
    # Thư mục "anh em" trùng tiền tố tên (sources2 vs sources): so tiền tố phải kèm dấu phân cách.
    sibling = tmp_path / "sources2"
    sibling.mkdir()
    (sibling / "secret.sqlite").write_bytes(sqlite_path.read_bytes())
    with pytest.raises(SourceAccessError):
        resolve_source_file("../sources2/secret.sqlite", base)
    assert resolve_source_file("./sub/../glass.sqlite", base) == sqlite_path.resolve()


@pytest.mark.parametrize("engine", ["sqlite", "duckdb"])
def test_aggregate_matches_pandas_on_the_real_data(sources, engine):
    base, sqlite_path, duckdb_path = sources
    path, runner = (sqlite_path, run_sqlite) if engine == "sqlite" else (duckdb_path, run_duckdb)
    tables = sqlite_tables(path) if engine == "sqlite" else duckdb_tables(path)
    assert tables == ["glass"]
    query = validate_sql("SELECT Type, COUNT(*) AS n, AVG(RI) AS ri FROM glass GROUP BY Type ORDER BY Type", engine, tables)
    result = runner(path, query, {}, cap=20, timeout=5)
    expected = glass_frame().groupby("Type").agg(n=("RI", "size"), ri=("RI", "mean")).reset_index()
    assert result.columns == ["Type", "n", "ri"] and not result.truncated
    assert [r["Type"] for r in result.rows] == expected["Type"].tolist()
    assert [r["n"] for r in result.rows] == expected["n"].tolist()
    assert [r["ri"] for r in result.rows] == pytest.approx(expected["ri"].tolist())


@pytest.mark.parametrize("engine", ["sqlite", "duckdb"])
def test_row_cap_sets_truncated_without_reading_everything(sources, engine):
    base, sqlite_path, duckdb_path = sources
    path, runner = (sqlite_path, run_sqlite) if engine == "sqlite" else (duckdb_path, run_duckdb)
    query = validate_sql("SELECT * FROM glass", engine, ["glass"])
    capped = runner(path, query, {}, cap=10, timeout=5)
    assert capped.row_count == 10 and capped.truncated is True
    full = runner(path, query, {}, cap=len(glass_frame()), timeout=5)
    assert full.row_count == len(glass_frame()) and full.truncated is False


def test_sqlite_parameters_are_bound_not_concatenated(sources):
    _, sqlite_path, _ = sources
    query = validate_sql("SELECT COUNT(*) AS n FROM glass WHERE Type = :t", "sqlite", ["glass"])
    result = run_sqlite(sqlite_path, query, {"t": 1}, cap=5, timeout=5)
    assert result.rows[0]["n"] == int((glass_frame()["Type"] == 1).sum())


@pytest.mark.parametrize("sql", [
    "SELECT load_extension('/tmp/x.so')",
    "SELECT * FROM glass WHERE 0 = (SELECT COUNT(*) FROM pragma_table_info('glass'))",
])
def test_sqlite_refuses_dangerous_operations_even_without_the_validator(sources, sql):
    _, sqlite_path, _ = sources
    with pytest.raises(QueryFailedError):
        run_sqlite(sqlite_path, _raw(sql, "sqlite"), {}, cap=5, timeout=5)


def test_sqlite_file_is_opened_read_only(sources):
    # Bộ chạy luôn bọc câu trong SELECT ... LIMIT nên lệnh ghi không có đường vào; lớp cuối là
    # chính file được mở với mode=ro: ghi qua đúng URI đó thì SQLite từ chối.
    import sqlite3
    from urllib.parse import quote

    _, sqlite_path, _ = sources
    before = sqlite_path.read_bytes()
    con = sqlite3.connect(f"file:{quote(str(sqlite_path))}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        con.execute("DELETE FROM glass")
    con.close()
    run_sqlite(sqlite_path, validate_sql("SELECT * FROM glass", "sqlite", ["glass"]), {}, cap=5, timeout=5)
    assert sqlite_path.read_bytes() == before


def test_duckdb_blocks_file_access_even_without_the_validator(sources):
    _, _, duckdb_path = sources
    with pytest.raises(QueryFailedError):
        run_duckdb(duckdb_path, _raw("SELECT * FROM read_csv('/etc/passwd')", "duckdb"), {}, cap=5, timeout=5)


@pytest.mark.parametrize("engine", ["sqlite", "duckdb"])
def test_long_running_query_is_cancelled(sources, engine):
    base, sqlite_path, duckdb_path = sources
    path, runner = (sqlite_path, run_sqlite) if engine == "sqlite" else (duckdb_path, run_duckdb)
    heavy = validate_sql(
        "SELECT COUNT(*) AS n FROM glass a, glass b, glass c, glass d WHERE a.RI + b.RI + c.RI > d.RI",
        engine, ["glass"],
    )
    with pytest.raises(QueryTimeoutError):
        runner(path, heavy, {}, cap=5, timeout=0.2)


def test_column_metadata(sources):
    _, sqlite_path, duckdb_path = sources
    names = list(glass_frame().columns)
    assert [c["name"] for c in sqlite_columns(sqlite_path, "glass")] == names
    assert [c["name"] for c in duckdb_columns(duckdb_path, "glass")] == names


def test_sqlite_authorizer_only_reads_tables_the_validator_approved(sources):
    _, sqlite_path, _ = sources
    with pytest.raises(QueryFailedError):
        run_sqlite(sqlite_path, _raw("SELECT name FROM sqlite_master", "sqlite"), {}, cap=5, timeout=5)


def test_memory_bombs_are_contained_by_the_worker_limit(sources):
    # Codex D3: repeat()/printf cấp phát GB trong MỘT dòng; memory_limit của DuckDB không chặn được.
    _, _, duckdb_path = sources
    with pytest.raises(QueryFailedError):
        run_duckdb(duckdb_path, _raw("SELECT length(repeat('x', 2000000000)) AS n", "duckdb"), {}, cap=1, timeout=20,
                   memory_bytes=1024 * 1024 * 1024)


def test_oversized_results_are_refused_not_silently_cut(sources):
    _, sqlite_path, _ = sources
    with pytest.raises(QueryFailedError, match="quá lớn"):
        run_sqlite(sqlite_path, validate_sql("SELECT * FROM glass", "sqlite", ["glass"]), {}, cap=500, timeout=5,
                   max_bytes=1000)


def test_legacy_endpoint_cannot_read_files_through_a_duckdb_view(tmp_path, monkeypatch):
    # Codex D2: endpoint cũ /datasets/database/* đọc view bằng SQLAlchemy -> view read_csv('/ngoài')
    # đọc được file ngoài thư mục nguồn. Giờ đi qua bộ chạy tắt truy cập file ngoài.
    import duckdb
    from src.adapters.base import DatabaseConfig, QueryExecutionError
    from src.adapters.duckdb import DuckDBAdapter
    from src.config import settings

    base = tmp_path / "sources"
    base.mkdir()
    secret = tmp_path / "secret.csv"
    secret.write_text("password\nhunter2\n")
    con = duckdb.connect(str(base / "evil.duckdb"))
    con.execute(f"CREATE VIEW leak AS SELECT * FROM read_csv('{secret}')")
    con.close()
    monkeypatch.setattr(settings.DATABASE_SOURCES, "FILES_DIR", base)
    adapter = DuckDBAdapter(DatabaseConfig(db_type="duckdb", database="evil.duckdb"))
    assert "leak" in adapter.get_tables()
    with pytest.raises(QueryExecutionError):
        adapter.fetch_table_to_dataframe("leak")


def test_legacy_endpoint_still_imports_a_real_table(sources, monkeypatch):
    from src.adapters.base import DatabaseConfig
    from src.adapters.sqlite import SQLiteAdapter
    from src.config import settings

    base, _, _ = sources
    monkeypatch.setattr(settings.DATABASE_SOURCES, "FILES_DIR", base)
    frame = SQLiteAdapter(DatabaseConfig(db_type="sqlite", database="glass.sqlite")).fetch_table_to_dataframe("glass")
    assert frame.shape == glass_frame().shape


def test_views_and_ctes_still_run_under_the_authorizer(tmp_path):
    # Codex E3: authorizer từng chặn view (đọc bảng gốc) và CTE (SQLite báo đọc CTE như bảng).
    import sqlite3

    base = tmp_path / "sources"
    base.mkdir()
    path = make_sqlite(base)
    con = sqlite3.connect(path)
    con.execute("CREATE VIEW float_glass AS SELECT RI, Type FROM glass WHERE Type = 1")
    con.commit()
    con.close()
    tables = sqlite_tables(path)
    assert tables == ["float_glass", "glass"]
    view = run_sqlite(path, validate_sql("SELECT COUNT(*) AS n FROM float_glass", "sqlite", tables), {}, cap=5, timeout=5)
    assert view.rows[0]["n"] == int((glass_frame()["Type"] == 1).sum())
    cte = run_sqlite(path, validate_sql("WITH a AS (SELECT RI FROM glass) SELECT COUNT(*) AS n FROM a", "sqlite", tables),
                     {}, cap=5, timeout=5)
    assert cte.rows[0]["n"] == len(glass_frame())


def test_nested_views_run_under_the_authorizer(tmp_path):
    # Codex F4: v2 -> v1 -> glass; SQLite báo view trong cùng (v1) khi đọc bảng gốc.
    import sqlite3

    base = tmp_path / "sources"
    base.mkdir()
    path = make_sqlite(base)
    con = sqlite3.connect(path)
    con.execute("CREATE VIEW v1 AS SELECT RI, Type FROM glass")
    con.execute("CREATE VIEW v2 AS SELECT * FROM v1 WHERE Type = 2")
    con.commit()
    con.close()
    tables = sqlite_tables(path)
    result = run_sqlite(path, validate_sql("SELECT COUNT(*) AS n FROM v2", "sqlite", tables), {}, cap=5, timeout=5)
    assert result.rows[0]["n"] == int((glass_frame()["Type"] == 2).sum())
    with pytest.raises(QueryFailedError):          # catalog vẫn bị chặn kể cả khi bỏ qua bộ kiểm
        run_sqlite(path, _raw("SELECT name FROM sqlite_master", "sqlite"), {}, cap=5, timeout=5)
