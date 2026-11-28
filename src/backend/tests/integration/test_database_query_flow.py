"""
Đầu-cuối, không LLM: tool của SQL Agent -> HTTP API backend thật (FastAPI in-process) -> adapter
-> SQLite / DuckDB / MongoDB chứa dữ liệu Glass THẬT -> dataset parquet.

Chỉ thay lưu trữ (Mongo metadata, MinIO) bằng bản trong bộ nhớ; còn lại là code chạy thật.
"""
# Standard Libraries
import io

# Third-party Libraries
import mongomock
import pandas as pd
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

# Local Libraries
# Image backend (deploy/Dockerfile) chỉ chép src/, assets/, tests/ - không có agent/. Khi đó bỏ qua
# file này; chạy trong repo (cả agent/) thì test chạy đủ.
tools = pytest.importorskip("agent.tools", reason="cần thư mục agent/ (chạy test trong repo)")
HAutoMLClient = pytest.importorskip("agent.api_client").HAutoMLClient

from src.config import settings  # noqa: E402
from src.core import dependencies  # noqa: E402
from src.main import app  # noqa: E402
from src.modules.database_connections import router as router_module  # noqa: E402
from src.modules.database_connections.service import ConnectionService  # noqa: E402
from src.modules.datasets.service import DatasetService  # noqa: E402
from tests.database_sources import FakeConnectionRepository, FakeDatasetRepository, glass_frame, make_duckdb, make_sqlite  # noqa: E402


USER = {"_id": "user-1", "username": "alice", "role": "user"}

FEATURES = ["RI", "Na", "Mg", "Al", "Si", "K", "Ca", "Ba", "Fe"]
# Bài toán thật: phân biệt kính cửa sổ loại 1 (float processed) với loại 2 (non-float processed).
SQL = (
    "SELECT RI, Na, Mg, Al, Si, K, Ca, Ba, Fe, CASE WHEN Type = 1 THEN 1 ELSE 0 END AS is_float_processed "
    "FROM glass WHERE Type IN (1, 2)"
)


@pytest.fixture
def world(tmp_path, monkeypatch):
    base = tmp_path / "sources"
    base.mkdir()
    make_sqlite(base)
    make_duckdb(base)
    monkeypatch.setattr(settings.DATABASE_SOURCES, "ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(settings.DATABASE_SOURCES, "FILES_DIR", base)
    monkeypatch.setattr(settings.DATABASE_SOURCES, "MONGO_ALLOWED_HOSTS", "localhost")
    uploads = {}

    async def upload_dataset(bucket, name, buffer):
        uploads[name] = buffer.getvalue()

    monkeypatch.setattr("src.modules.datasets.service.minio_service.upload_dataset", upload_dataset)
    mongo = mongomock.MongoClient()
    mongo["lab"]["glass"].insert_many(glass_frame().to_dict(orient="records"))
    monkeypatch.setattr(ConnectionService, "mongo_client_factory", staticmethod(lambda doc: mongo))
    datasets = FakeDatasetRepository()
    service = ConnectionService(FakeConnectionRepository(), DatasetService(datasets))
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER
    app.dependency_overrides[router_module.get_connection_service] = lambda: service

    http = TestClient(app, base_url="http://testserver/api/v1")
    api = HAutoMLClient()
    api._http = http                      # tool của agent đi qua HTTP thật tới app in-process
    api.access_token = "user-token"
    try:
        yield api, http, datasets, uploads
    finally:
        app.dependency_overrides.clear()


def _create(http, **body):
    response = http.post("/database-connections", json={"name": "lab", **body})
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _stored_frame(uploads) -> pd.DataFrame:
    return pd.read_parquet(io.BytesIO(list(uploads.values())[-1]))


@pytest.mark.parametrize("db_type,database", [("sqlite", "glass.sqlite"), ("duckdb", "glass.duckdb")])
def test_agent_tools_turn_a_sql_query_into_a_training_dataset(world, db_type, database):
    api, http, datasets, uploads = world
    connection_id = _create(http, db_type=db_type, database=database)

    connections = tools.list_database_connections(api)
    assert connections["ok"] and connections["connections"][0]["id"] == connection_id

    tables = tools.list_database_tables(api, connection_id)
    assert tables["tables"] == [{"name": "glass", "kind": "table"}]
    described = tools.describe_database_table(api, connection_id, "glass", sample_rows=3)
    assert [c["name"] for c in described["columns"]] == FEATURES + ["Type"] and len(described["sample_rows"]) == 3

    preview = tools.preview_sql_query(api, connection_id, SQL, row_limit=10)
    assert preview["ok"] and preview["truncated"] is True and preview["columns"] == FEATURES + ["is_float_processed"]

    imported = tools.import_database_query(api, connection_id, preview["preview_id"], "glass_float_vs_nonfloat")
    expected = glass_frame().query("Type in [1, 2]")
    assert imported["ok"] and imported["row_count"] == len(expected) and imported["truncated"] is False
    stored = _stored_frame(uploads)
    assert stored.columns.tolist() == FEATURES + ["is_float_processed"]
    assert int(stored["is_float_processed"].sum()) == int((expected["Type"] == 1).sum())
    pd.testing.assert_frame_equal(stored[FEATURES], expected[FEATURES].reset_index(drop=True), check_dtype=False)
    assert datasets.datasets[-1]["dataName"] == "glass_float_vs_nonfloat"

    again = tools.import_database_query(api, connection_id, preview["preview_id"], "glass_float_vs_nonfloat")
    assert again["already_imported"] is True and again["dataset_id"] == imported["dataset_id"]
    assert len(datasets.datasets) == 1


@pytest.mark.parametrize("sql", [
    "SELECT * FROM glass; DROP TABLE glass",
    "SELECT * FROM read_csv('/etc/passwd')",
    "WITH x AS (DELETE FROM glass RETURNING *) SELECT * FROM x",
    "SELECT * FROM users",
])
def test_agent_cannot_escape_read_only_access(world, sql):
    api, http, datasets, _ = world
    connection_id = _create(http, db_type="sqlite", database="glass.sqlite")
    result = tools.preview_sql_query(api, connection_id, sql)
    assert result["ok"] is False and result["status_code"] == 400
    assert tools.list_database_tables(api, connection_id)["tables"] == [{"name": "glass", "kind": "table"}]
    assert not datasets.datasets


def test_agent_tools_import_a_mongodb_aggregation(world):
    api, http, _, uploads = world
    connection_id = _create(http, db_type="mongodb", database="lab", host="localhost")
    preview = tools.preview_mongo_query(api, connection_id, {
        "kind": "aggregate", "collection": "glass", "row_limit": 5,
        "pipeline": [{"$match": {"Type": {"$in": [1, 2]}}},
                     {"$project": {"_id": 0, **{f: 1 for f in FEATURES}, "Type": 1}}]})
    assert preview["ok"] and preview["truncated"] is True
    imported = tools.import_database_query(api, connection_id, preview["preview_id"], "glass_from_mongo")
    assert imported["row_count"] == int(glass_frame()["Type"].isin([1, 2]).sum())
    assert _stored_frame(uploads).columns.tolist() == FEATURES + ["Type"]
