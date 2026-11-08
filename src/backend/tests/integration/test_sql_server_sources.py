"""
PostgreSQL / MySQL THẬT (docker) cho SQL agent: metadata, preview, import, và các lớp bảo vệ ở
phía server (transaction chỉ-đọc, timeout, quyền, chế độ chuỗi). Dữ liệu: bộ Glass (UCI) thật.

Chạy:
    docker compose -f src/backend/tests/sql_sources/docker-compose.yml up -d --wait
    docker run --rm --network host -v $PWD:/repo -w /repo/src/backend/tests hautoml-backend-test:local \\
        python -m pytest integration/test_sql_server_sources.py
Không có server thì bỏ qua (vd lúc build Docker); đặt HAUTOML_REQUIRE_SQL_SERVERS=1 để thành lỗi.
Server trong compose cố ý để chế độ chuỗi BẤT LỢI (standard_conforming_strings=off; ANSI_QUOTES +
NO_BACKSLASH_ESCAPES) - test chứng minh bộ chạy tự ép lại chế độ an toàn.
"""
# Standard Libraries
import io
import os
import socket

# Third-party Libraries
import pandas as pd
import pytest
from cryptography.fernet import Fernet

# Local Libraries
from src.adapters.query_runner import QueryFailedError, QueryTimeoutError, SourceAccessError, _server_request, _spawn
from src.config import settings
from src.core.exceptions import CustomException
from src.modules.database_connections.schemas import ConnectionCreate, DescribeRequest, ImportRequest
from src.modules.database_connections.service import ConnectionService
from src.modules.datasets.service import DatasetService
from tests.database_sources import FakeConnectionRepository, FakeDatasetRepository, glass_frame


USER = {"_id": "user-1", "username": "alice", "role": "user"}
HOST = os.getenv("HAUTOML_TEST_SQL_HOST", "127.0.0.1")
SERVERS = {
    "postgres": {"port": int(os.getenv("HAUTOML_TEST_PG_PORT", "55432")), "glass_columns": ["ri", "na", "type"]},
    "mysql": {"port": int(os.getenv("HAUTOML_TEST_MYSQL_PORT", "53306")), "glass_columns": ["RI", "Na", "Type"]},
}


def _reachable(port: int) -> bool:
    try:
        with socket.create_connection((HOST, port), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.fixture(params=list(SERVERS))
def engine(request):
    name = request.param
    if not _reachable(SERVERS[name]["port"]):
        if os.getenv("HAUTOML_REQUIRE_SQL_SERVERS") == "1":
            pytest.fail(f"{name} test server không chạy ở {HOST}:{SERVERS[name]['port']}")
        pytest.skip(f"{name} test server không chạy (xem tests/sql_sources/docker-compose.yml)")
    return name


def _config(engine: str, username: str = "hautoml_ro", password: str = "ro-test-password") -> dict:
    return {"engine": engine, "host": HOST, "port": SERVERS[engine]["port"], "username": username,
            "password": password, "database": "lab", "schema": "public" if engine == "postgres" else None}


def _raw(engine: str, sql: str, timeout: float = 5, **config):
    """Gửi câu SQL THẲNG vào bộ chạy, bỏ qua bộ kiểm - để thử riêng lớp bảo vệ của server."""
    return _spawn(_server_request(_config(engine, **config), "query", timeout, sql=sql, cap=10), timeout)


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(settings.DATABASE_SOURCES, "ENCRYPTION_KEY", Fernet.generate_key().decode())
    allowed = ",".join(f"{HOST}:{s['port']}" for s in SERVERS.values())
    monkeypatch.setattr(settings.DATABASE_SOURCES, "SQL_ALLOWED_HOSTS", allowed)
    uploads = {}

    async def upload_dataset(bucket, name, buffer):
        uploads[name] = buffer.getvalue()

    monkeypatch.setattr("src.modules.datasets.service.minio_service.upload_dataset", upload_dataset)
    dataset_repo = FakeDatasetRepository()
    return ConnectionService(FakeConnectionRepository(), DatasetService(dataset_repo)), dataset_repo, uploads


async def _connect(service, engine: str, **fields):
    payload = {"name": f"lab-{engine}", "db_type": engine, "database": "lab", "host": HOST,
               "port": SERVERS[engine]["port"], "username": "hautoml_ro", "password": "ro-test-password", **fields}
    return await service.create_connection(USER, ConnectionCreate(**payload))


async def test_metadata_preview_and_import_round_trip(engine, service):
    service, dataset_repo, uploads = service
    public = await _connect(service, engine)
    assert "ro-test-password" not in public.model_dump_json() and HOST not in public.model_dump_json()
    # Chỉ thấy bảng được cấp quyền: bảng canary secret_salaries không xuất hiện.
    assert await service.list_tables(USER, public.id) == {"tables": [{"name": "glass", "kind": "table"}]}
    described = await service.describe_table(USER, public.id, DescribeRequest(table="glass", sample_rows=3))
    assert len(described["columns"]) == 10 and len(described["rows"]) == 3

    ri, na, type_ = SERVERS[engine]["glass_columns"]
    sql = f"SELECT {ri}, {na}, {type_} FROM glass WHERE {type_} IN (:a, :b) ORDER BY {ri}, {na}"
    preview = await service.preview_query(USER, public.id, {"kind": "sql", "sql": sql, "params": {"a": 1, "b": 2},
                                                            "row_limit": 5})
    assert preview.row_count == 5 and preview.truncated is True and preview.columns == [ri, na, type_]
    imported = await service.import_preview(USER, public.id, ImportRequest(preview_id=preview.preview_id, data_name="g12"))
    frame = glass_frame()
    expected = frame[frame["Type"].isin([1, 2])][["RI", "Na", "Type"]]
    stored = pd.read_parquet(io.BytesIO(next(iter(uploads.values()))))
    assert imported.row_count == len(expected) == len(stored) == 146
    assert sorted(stored[type_].tolist()) == sorted(expected["Type"].tolist())
    assert abs(stored[ri].astype(float).sum() - expected["RI"].sum()) < 1e-6
    if engine == "mysql":  # cột DECIMAL -> số thực, có ghi chú
        assert any("DECIMAL" in n for n in imported.notes)


async def test_canary_table_is_unreachable(engine, service):
    service, _, _ = service
    public = await _connect(service, engine)
    with pytest.raises(CustomException) as error:
        await service.preview_query(USER, public.id, {"kind": "sql", "sql": "SELECT * FROM secret_salaries"})
    assert error.value.error_code == "UNSAFE_QUERY"
    # Kể cả khi bộ kiểm bị vượt qua, quyền của database vẫn chặn.
    with pytest.raises(QueryFailedError) as raw_error:
        _raw(engine, "SELECT * FROM secret_salaries")
    assert "canary" not in str(raw_error.value) and "127.0.0.1" not in str(raw_error.value)


def _glass_count(engine: str) -> int:
    _, rows = _raw(engine, "SELECT COUNT(*) FROM glass")
    return rows[0][0]


def test_writes_fail_even_for_an_account_that_may_write(engine):
    before = _glass_count(engine)
    for sql in ("INSERT INTO glass (ri) VALUES (1.0)", "DELETE FROM glass"):
        with pytest.raises(QueryFailedError):
            _raw(engine, sql, username="hautoml_rw", password="rw-test-password")
    assert _glass_count(engine) == before == 214


def test_server_side_timeout_stops_heavy_queries(engine):
    ri, na, _ = SERVERS[engine]["glass_columns"]
    heavy = f"SELECT COUNT(*) FROM glass a, glass b, glass c, glass d WHERE a.{ri} * b.{na} > c.{ri} + d.{na}"
    with pytest.raises(QueryTimeoutError):
        _raw(engine, heavy, timeout=1.5)


async def test_injection_through_params_under_hostile_server_string_modes(engine, service):
    service, _, _ = service
    public = await _connect(service, engine)
    _, _, type_ = SERVERS[engine]["glass_columns"]
    cast = "CHAR(20)" if engine == "mysql" else "TEXT"
    sql = f"SELECT COUNT(*) AS n FROM glass WHERE CAST({type_} AS {cast}) = :v"
    counts = {}
    for value in ["1", "x\\' OR 1=1 -- ", "x' OR '1'='1", "1\\", "1' UNION SELECT note FROM secret_salaries -- "]:
        preview = await service.preview_query(USER, public.id, {"kind": "sql", "sql": sql, "params": {"v": value}})
        counts[value] = preview.rows[0]["n"]
    assert counts == {"1": 70, "x\\' OR 1=1 -- ": 0, "x' OR '1'='1": 0, "1\\": 0,
                      "1' UNION SELECT note FROM secret_salaries -- ": 0}


async def test_unsafe_server_sql_is_rejected_before_running(engine, service):
    service, _, _ = service
    public = await _connect(service, engine)
    attacks = {
        "postgres": ["SELECT pg_read_file('/etc/passwd')", "SELECT pg_sleep(30)", "SELECT version()",
                     "SELECT * FROM pg_catalog.pg_authid", "SELECT /*+ SeqScan(glass) */ * FROM glass FOR UPDATE"],
        "mysql": ["SELECT LOAD_FILE('/etc/passwd')", "SELECT SLEEP(30)", "SELECT @@datadir",
                  "SELECT /*+ MAX_EXECUTION_TIME(999999) */ * FROM glass", "SELECT * FROM mysql.user"],
    }[engine]
    for sql in attacks:
        with pytest.raises(CustomException) as error:
            await service.preview_query(USER, public.id, {"kind": "sql", "sql": sql})
        assert error.value.status_code == 400, sql


def test_bad_credentials_do_not_leak_host_or_user(engine):
    with pytest.raises(SourceAccessError) as error:
        _raw(engine, "SELECT 1", password="definitely-wrong")
    assert "127.0.0.1" not in str(error.value) and "hautoml_ro" not in str(error.value)


def test_result_byte_budget_is_enforced(engine):
    with pytest.raises(QueryFailedError, match="quá lớn"):
        _spawn(_server_request(_config(engine), "query", 5, sql="SELECT * FROM glass", cap=500, max_bytes=2_000), 5)


async def test_postgres_schema_name_scopes_tables(service):
    if not _reachable(SERVERS["postgres"]["port"]):
        pytest.skip("postgres test server không chạy")
    service, _, _ = service
    public = await _connect(service, "postgres", schema_name="lab")
    assert public.database_label == "lab.lab"
    assert await service.list_tables(USER, public.id) == {"tables": [{"name": "glass_types", "kind": "table"}]}
    preview = await service.preview_query(USER, public.id, {"kind": "sql", "sql": "SELECT type, n FROM glass_types ORDER BY type"})
    assert [r["n"] for r in preview.rows] == [70, 76, 17, 13, 9, 29]
    # Bảng của schema khác (public.glass) không đọc được từ kết nối này.
    with pytest.raises(CustomException):
        await service.preview_query(USER, public.id, {"kind": "sql", "sql": "SELECT * FROM glass"})
