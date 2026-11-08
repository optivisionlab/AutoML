"""
Kết nối database đã lưu + luồng preview -> import (dữ liệu Glass thật trong SQLite / DuckDB / MongoDB giả).

Kiểm: mật khẩu chỉ lưu dạng mã hoá và không bao giờ trả ra; kết nối của người khác coi như không có;
truy vấn không an toàn bị chặn; import tạo đúng một dataset có đủ dữ liệu, gửi lại không tạo trùng;
kết quả vượt trần phải được chấp nhận rõ ràng; preview cũ (kết nối đã đổi) bị từ chối.
"""
# Standard Libraries
import io
from types import SimpleNamespace
import json

# Third-party Libraries
import mongomock
import pandas as pd
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

# Local Libraries
from src.config import settings
from src.core import dependencies
from src.core.exceptions import CustomException
from src.main import app
from src.modules.database_connections import router as router_module
from src.modules.database_connections.schemas import ConnectionCreate, ConnectionUpdate, DescribeRequest, ImportRequest
from src.modules.database_connections.service import ConnectionService
from src.modules.datasets.service import DatasetService
from tests.database_sources import FakeConnectionRepository, FakeDatasetRepository, glass_frame, make_duckdb, make_sqlite


USER = {"_id": "user-1", "username": "alice", "role": "user"}
OTHER = {"_id": "user-2", "username": "bob", "role": "user"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    base = tmp_path / "sources"
    base.mkdir()
    make_sqlite(base)
    make_duckdb(base)
    monkeypatch.setattr(settings.DATABASE_SOURCES, "ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(settings.DATABASE_SOURCES, "FILES_DIR", base)
    monkeypatch.setattr(settings.DATABASE_SOURCES, "MONGO_ALLOWED_HOSTS", "localhost,mongodb")
    uploads = {}

    async def upload_dataset(bucket, name, buffer):
        uploads[name] = buffer.getvalue()

    monkeypatch.setattr("src.modules.datasets.service.minio_service.upload_dataset", upload_dataset)
    mongo = mongomock.MongoClient()
    mongo["lab"]["glass"].insert_many(glass_frame().to_dict(orient="records"))
    monkeypatch.setattr(ConnectionService, "mongo_client_factory", staticmethod(lambda doc: mongo))
    dataset_repo = FakeDatasetRepository()
    service = ConnectionService(FakeConnectionRepository(), DatasetService(dataset_repo))
    return service, dataset_repo, uploads


async def _create(service, **fields):
    payload = {"name": "lab", "db_type": "sqlite", "database": "glass.sqlite", **fields}
    return await service.create_connection(USER, ConnectionCreate(**payload))


async def test_secrets_are_encrypted_and_never_returned(env):
    service, _, _ = env
    public = await _create(service, db_type="mongodb", database="lab", host="localhost", username="reader", password="s3cret!")
    stored = service.repo.connections[public.id]
    assert stored["password_ciphertext"] and "s3cret!" not in json.dumps(stored, default=str)
    dumped = public.model_dump_json()
    for leaked in ("s3cret!", "reader", "localhost", "ciphertext"):
        assert leaked not in dumped


async def test_feature_is_disabled_without_an_encryption_key(env, monkeypatch):
    service, _, _ = env
    monkeypatch.setattr(settings.DATABASE_SOURCES, "ENCRYPTION_KEY", "")
    with pytest.raises(CustomException) as error:
        await _create(service)
    assert error.value.status_code == 503


@pytest.mark.parametrize("fields", [
    {"database": "../etc/passwd"},
    {"database": "/etc/hosts"},
    {"database": "missing.sqlite"},
    {"host": "db.example.com"},
    {"db_type": "mongodb", "database": "lab", "host": "169.254.169.254"},
    {"db_type": "mongodb", "database": "admin", "host": "localhost"},
])
async def test_dangerous_connection_targets_are_refused(env, fields):
    service, _, _ = env
    with pytest.raises(CustomException) as error:
        await _create(service, **fields)
    assert error.value.status_code == 400


async def test_other_users_cannot_see_or_use_a_connection(env):
    service, _, _ = env
    public = await _create(service)
    for call in (service.get_connection(OTHER, public.id), service.list_tables(OTHER, public.id),
                 service.preview_query(OTHER, public.id, {"kind": "sql", "sql": "SELECT * FROM glass"})):
        with pytest.raises(CustomException) as error:
            await call
        assert error.value.status_code == 404


@pytest.mark.parametrize("db_type,database", [("sqlite", "glass.sqlite"), ("duckdb", "glass.duckdb")])
async def test_metadata_preview_and_import_round_trip(env, db_type, database):
    service, dataset_repo, uploads = env
    public = await _create(service, db_type=db_type, database=database)
    assert (await service.list_tables(USER, public.id)) == {"tables": [{"name": "glass", "kind": "table"}]}
    described = await service.describe_table(USER, public.id, DescribeRequest(table="glass", sample_rows=3))
    assert [c["name"] for c in described["columns"]] == list(glass_frame().columns) and len(described["rows"]) == 3

    sql = "SELECT RI, Na, Mg, Type FROM glass WHERE Ba = 0"
    preview = await service.preview_query(USER, public.id, {"kind": "sql", "sql": sql, "row_limit": 5})
    expected = glass_frame().query("Ba == 0")[["RI", "Na", "Mg", "Type"]].reset_index(drop=True)
    assert preview.row_count == 5 and preview.truncated is True and preview.columns == ["RI", "Na", "Mg", "Type"]

    imported = await service.import_preview(USER, public.id, ImportRequest(preview_id=preview.preview_id, data_name="glass_no_ba"))
    assert imported.row_count == len(expected) and imported.truncated is False
    stored = pd.read_parquet(io.BytesIO(next(iter(uploads.values()))))
    pd.testing.assert_frame_equal(stored, expected, check_dtype=False)
    assert dataset_repo.datasets[0]["source"]["kind"] == "database_query" and dataset_repo.datasets[0]["public"] is False

    again = await service.import_preview(USER, public.id, ImportRequest(preview_id=preview.preview_id, data_name="glass_no_ba"))
    assert again.already_imported is True and again.dataset_id == imported.dataset_id and len(dataset_repo.datasets) == 1


async def test_unsafe_sql_is_rejected_before_execution(env):
    service, _, _ = env
    public = await _create(service)
    for sql in ("SELECT 1; DROP TABLE glass", "SELECT * FROM read_csv('/etc/passwd')", "SELECT * FROM users"):
        with pytest.raises(CustomException) as error:
            await service.preview_query(USER, public.id, {"kind": "sql", "sql": sql})
        assert error.value.status_code == 400 and error.value.error_code == "UNSAFE_QUERY"


async def test_import_over_the_cap_needs_explicit_consent(env, monkeypatch):
    service, dataset_repo, _ = env
    monkeypatch.setattr(settings.DATABASE_SOURCES, "IMPORT_MAX_ROWS", 50)
    public = await _create(service)
    preview = await service.preview_query(USER, public.id, {"kind": "sql", "sql": "SELECT * FROM glass"})
    with pytest.raises(CustomException) as error:
        await service.import_preview(USER, public.id, ImportRequest(preview_id=preview.preview_id, data_name="g"))
    assert error.value.status_code == 409 and error.value.error_code == "RESULT_TRUNCATED" and not dataset_repo.datasets
    imported = await service.import_preview(
        USER, public.id, ImportRequest(preview_id=preview.preview_id, data_name="g", allow_truncated=True))
    assert imported.row_count == 50 and imported.truncated is True


async def test_preview_becomes_stale_when_the_connection_changes(env):
    service, _, _ = env
    public = await _create(service)
    preview = await service.preview_query(USER, public.id, {"kind": "sql", "sql": "SELECT * FROM glass"})
    await service.update_connection(USER, public.id, ConnectionUpdate(name="renamed"))
    with pytest.raises(CustomException) as error:
        await service.import_preview(USER, public.id, ImportRequest(preview_id=preview.preview_id, data_name="g"))
    assert error.value.status_code == 409 and error.value.error_code == "PREVIEW_STALE"


async def test_mongodb_aggregate_preview_and_import(env):
    service, dataset_repo, uploads = env
    public = await _create(service, db_type="mongodb", database="lab", host="localhost")
    query = {"kind": "aggregate", "collection": "glass",
             "pipeline": [{"$match": {"Type": {"$in": [1, 2]}}}, {"$project": {"_id": 0, "RI": 1, "Na": 1, "Type": 1}}]}
    preview = await service.preview_query(USER, public.id, {**query, "row_limit": 10})
    assert preview.columns == ["RI", "Na", "Type"] and preview.truncated is True
    imported = await service.import_preview(USER, public.id, ImportRequest(preview_id=preview.preview_id, data_name="glass_12"))
    assert imported.row_count == int(glass_frame()["Type"].isin([1, 2]).sum())
    stored = pd.read_parquet(io.BytesIO(next(iter(uploads.values()))))
    assert list(stored.columns) == ["RI", "Na", "Type"]


async def test_nested_mongo_values_must_be_projected_before_import(env):
    service, _, _ = env
    public = await _create(service, db_type="mongodb", database="lab", host="localhost")
    preview = await service.preview_query(USER, public.id, {
        "kind": "aggregate", "collection": "glass",
        "pipeline": [{"$group": {"_id": "$Type", "values": {"$push": "$RI"}}}]})
    with pytest.raises(CustomException) as error:
        await service.import_preview(USER, public.id, ImportRequest(preview_id=preview.preview_id, data_name="nested"))
    assert error.value.status_code == 400


def test_http_api_round_trip_without_leaking_secrets(env):
    service, _, _ = env
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER
    app.dependency_overrides[router_module.get_connection_service] = lambda: service
    try:
        client = TestClient(app)
        created = client.post("/api/v1/database-connections",
                              json={"name": "lab", "db_type": "sqlite", "database": "glass.sqlite"})
        assert created.status_code == 201, created.text
        connection_id = created.json()["data"]["id"]
        listed = client.get("/api/v1/database-connections").json()
        assert listed["meta"]["total_items"] == 1 and listed["data"][0]["database_label"] == "glass.sqlite"
        tables = client.get(f"/api/v1/database-connections/{connection_id}/tables").json()["data"]
        assert tables == {"tables": [{"name": "glass", "kind": "table"}]}
        preview = client.post(f"/api/v1/database-connections/{connection_id}/preview",
                              json={"query": {"kind": "sql", "sql": "SELECT Type, COUNT(*) AS n FROM glass GROUP BY Type"}})
        assert preview.status_code == 200, preview.text
        body = preview.json()["data"]
        imported = client.post(f"/api/v1/database-connections/{connection_id}/import",
                               json={"preview_id": body["preview_id"], "data_name": "glass_counts"})
        assert imported.status_code == 200 and imported.json()["data"]["row_count"] == glass_frame()["Type"].nunique()
        bad = client.post(f"/api/v1/database-connections/{connection_id}/preview",
                          json={"query": {"kind": "sql", "sql": "DELETE FROM glass"}})
        assert bad.status_code == 400
        extra = client.post("/api/v1/database-connections",
                            json={"name": "x", "db_type": "sqlite", "database": "glass.sqlite", "url": "sqlite:////etc/x"})
        assert extra.status_code == 422                       # không nhận URI / trường lạ
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("database", ["AutoML", "automl"])
async def test_the_application_database_is_never_a_source(env, database):
    # Codex D1: Mongo của chính HAutoML (thường không bật xác thực) chứa tbl_User của mọi người.
    service, _, _ = env
    with pytest.raises(CustomException) as error:
        await _create(service, db_type="mongodb", database=database, host="localhost")
    assert error.value.status_code == 400


async def test_mongodb_is_off_until_hosts_are_configured(env, monkeypatch):
    service, _, _ = env
    monkeypatch.setattr(settings.DATABASE_SOURCES, "MONGO_ALLOWED_HOSTS", "")
    with pytest.raises(CustomException) as error:
        await _create(service, db_type="mongodb", database="lab", host="localhost")
    assert "đang tắt" in error.value.detail


def test_import_keeps_exact_integers_and_reports_type_problems():
    # Codex D4: cột số nguyên có NULL từng thành float64 làm sai số lớn.
    import decimal
    from src.modules.database_connections.service import frame_for_import

    frame, notes = frame_for_import(["id", "price"], [{"id": 9007199254740993, "price": decimal.Decimal("1.10")},
                                                      {"id": None, "price": decimal.Decimal("2.25")}])
    assert str(frame["id"].dtype) == "Int64" and int(frame["id"][0]) == 9007199254740993
    assert frame["price"].tolist() == [1.10, 2.25] and any("DECIMAL" in n for n in notes)
    for rows in ([{"x": 1}, {"x": "a"}], [{"x": b"\x00"}], [{"x": {"a": 1}}]):
        with pytest.raises(CustomException) as error:
            frame_for_import(["x"], rows)
        assert error.value.status_code == 400


async def test_lost_insert_acknowledgement_keeps_the_file(env):
    # Codex D6: Mongo đã ghi nhưng mất phản hồi -> không được xoá parquet của dataset đã tồn tại.
    service, dataset_repo, uploads = env
    original = dataset_repo.create_dataset

    async def create_then_fail(doc):
        await original(doc)
        raise ConnectionError("mất phản hồi sau khi ghi")

    dataset_repo.create_dataset = create_then_fail
    public = await _create(service)
    preview = await service.preview_query(USER, public.id, {"kind": "sql", "sql": "SELECT * FROM glass"})
    imported = await service.import_preview(USER, public.id, ImportRequest(preview_id=preview.preview_id, data_name="g"))
    assert imported.row_count == len(glass_frame()) and len(dataset_repo.datasets) == 1 and len(uploads) == 1


async def test_crashed_import_is_recovered_without_a_duplicate(env):
    # Codex D7: tiến trình chết sau khi tạo dataset, trước khi ghi kết quả preview.
    service, dataset_repo, _ = env
    public = await _create(service)
    preview = await service.preview_query(USER, public.id, {"kind": "sql", "sql": "SELECT * FROM glass"})
    first = await service.import_preview(USER, public.id, ImportRequest(preview_id=preview.preview_id, data_name="g"))
    record = service.repo.previews[preview.preview_id]
    record.update(import_state="running", claimed_at=0, import_result=None)          # như lúc chết giữa chừng
    again = await service.import_preview(USER, public.id, ImportRequest(preview_id=preview.preview_id, data_name="g"))
    assert again.already_imported and again.dataset_id == first.dataset_id and len(dataset_repo.datasets) == 1


async def test_stuck_import_claim_expires(env):
    service, dataset_repo, _ = env
    public = await _create(service)
    preview = await service.preview_query(USER, public.id, {"kind": "sql", "sql": "SELECT * FROM glass"})
    service.repo.previews[preview.preview_id].update(import_state="running", claimed_at=0)
    imported = await service.import_preview(USER, public.id, ImportRequest(preview_id=preview.preview_id, data_name="g"))
    assert imported.row_count == len(glass_frame()) and len(dataset_repo.datasets) == 1


def test_bson_int64_values_import_as_exact_integers():
    from bson.int64 import Int64
    from src.modules.database_connections.service import frame_for_import

    frame, _ = frame_for_import(["n"], [{"n": Int64(9007199254740993)}, {"n": None}])
    assert str(frame["n"].dtype) == "Int64" and int(frame["n"][0]) == 9007199254740993


async def test_overlapping_attempts_keep_one_dataset_and_no_orphan_file(env, monkeypatch):
    # Codex E2: lượt cũ quá hạn và lượt mới cùng ghi -> mỗi lượt một file, lượt thua xoá file của mình;
    # lượt cũ không ghi đè được trạng thái của lượt mới.
    service, dataset_repo, uploads = env
    removed = []

    async def remove_object(bucket, name):
        removed.append(name)
        uploads.pop(name, None)

    monkeypatch.setattr("src.modules.datasets.service.minio_service.remove_object", remove_object)
    frame = glass_frame()
    dataset_id = "6aee00000000000000000001"
    first = await service.datasets.import_dataframe(USER, frame, "g", None, None, dataset_id=dataset_id)
    second = await service.datasets.import_dataframe(USER, frame, "g", None, None, dataset_id=dataset_id)
    assert first.id == second.id == dataset_id and len(dataset_repo.datasets) == 1
    linked = dataset_repo.datasets[0]["data_link"]["object_name"]
    assert list(uploads) == [linked] and len(removed) == 1 and removed[0] != linked

    public = await _create(service)
    preview = await service.preview_query(USER, public.id, {"kind": "sql", "sql": "SELECT * FROM glass"})
    repo = service.repo
    assert await repo.claim_preview_import(preview.preview_id, USER["_id"], 0, 600, "old")
    assert await repo.claim_preview_import(preview.preview_id, USER["_id"], 10_000, 600, "new")   # lượt cũ quá hạn
    await repo.finish_preview_import(preview.preview_id, USER["_id"], None, "old")                 # lượt cũ báo lỗi muộn
    assert repo.previews[preview.preview_id]["import_state"] == "running"                          # không xoá chỗ của lượt mới


async def test_overlapping_import_reports_the_dataset_actually_stored(env, monkeypatch):
    # Codex F3: lượt thua từng trả số liệu của chính nó thay cho dataset thật (của lượt thắng).
    service, dataset_repo, _ = env
    public = await _create(service)
    preview = await service.preview_query(USER, public.id, {"kind": "sql", "sql": "SELECT * FROM glass"})
    dataset_id = service.repo.previews[preview.preview_id]["dataset_id"]
    original = service.datasets.import_dataframe

    async def other_attempt_wins_first(user, df, name, description, provenance, dataset_id=None):
        from bson import ObjectId
        await dataset_repo.create_dataset({"_id": ObjectId(dataset_id), "dataName": "g", "dataType": "table",
                                           "createDate": 0, "latestUpdate": 0, "userId": USER["_id"], "activate": 1,
                                           "data_link": {"object_name": "other.parquet"},
                                           "source": {"row_count": 1, "columns": ["RI"], "truncated": False, "notes": []}})
        return await original(user, df, name, description, provenance, dataset_id=dataset_id)

    monkeypatch.setattr(service.datasets, "import_dataframe", other_attempt_wins_first)
    imported = await service.import_preview(USER, public.id, ImportRequest(preview_id=preview.preview_id, data_name="g"))
    assert imported.dataset_id == dataset_id and imported.row_count == 1 and imported.columns == ["RI"]


async def test_overlong_column_names_are_refused_or_left_out(env):
    # Codex G1: tên cột / trường dài (vd 1.000.000 ký tự) đi nguyên ra API và context agent.
    import sqlite3

    service, _, _ = env
    long_name = "f" * 300
    con = sqlite3.connect(settings.DATABASE_SOURCES.FILES_DIR / "odd.sqlite")
    con.execute(f'CREATE TABLE odd ("{long_name}" INTEGER, ok INTEGER)')
    con.execute("INSERT INTO odd VALUES (1, 2)")
    con.execute("CREATE TABLE many (" + ", ".join(f"c{i} INTEGER" for i in range(250)) + ")")
    con.execute("INSERT INTO many VALUES (" + ", ".join(["7"] * 250) + ")")
    con.commit()
    con.close()
    public = await _create(service, database="odd.sqlite")

    with pytest.raises(CustomException) as error:
        await service.preview_query(USER, public.id, {"kind": "sql", "sql": f'SELECT ok AS "{long_name}" FROM odd'})
    assert error.value.status_code == 400 and error.value.error_code == "QUERY_INVALID"
    assert long_name not in error.value.detail
    # Mô tả bảng vẫn dùng được: bỏ cột tên quá dài / quá 200 cột, báo số cột bị bỏ.
    odd = await service.describe_table(USER, public.id, DescribeRequest(table="odd"))
    assert [c["name"] for c in odd["columns"]] == ["ok"] and odd["rows"] == [{"ok": 2}] and odd["omitted_columns"] == 1
    many = await service.describe_table(USER, public.id, DescribeRequest(table="many"))
    assert len(many["columns"]) == 200 and len(many["rows"][0]) == 200 and many["omitted_columns"] == 50

    mongo = ConnectionService.mongo_client_factory(None)
    mongo["lab"]["odd"].insert_one({"g" * 1000: 1, "ok": 2})
    public = await _create(service, db_type="mongodb", database="lab", host="localhost")
    with pytest.raises(CustomException) as error:
        await service.preview_query(USER, public.id, {"kind": "find", "collection": "odd", "projection": {"_id": 0}})
    assert error.value.error_code == "QUERY_INVALID" and "g" * 1000 not in error.value.detail
    described = await service.describe_table(USER, public.id, DescribeRequest(table="odd"))
    assert "g" * 1000 not in json.dumps(described) and described["omitted_columns"] == 1


async def test_describing_a_very_wide_table_stays_within_the_sql_limit(env):
    # Codex H3: 200 cột tên 128 ký tự + 1 cột bị bỏ -> câu SELECT liệt kê ~26.000 ký tự, vượt trần 20.000.
    import sqlite3

    service, _, _ = env
    names = [f"c{i:03d}" + "w" * 124 for i in range(200)] + ["x" * 300]
    con = sqlite3.connect(settings.DATABASE_SOURCES.FILES_DIR / "wide.sqlite")
    con.execute("CREATE TABLE wide (" + ", ".join(f'"{n}" INTEGER' for n in names) + ")")
    con.execute("INSERT INTO wide VALUES (" + ", ".join(["1"] * len(names)) + ")")
    con.commit()
    con.close()
    public = await _create(service, database="wide.sqlite")
    described = await service.describe_table(USER, public.id, DescribeRequest(table="wide"))
    shown = [c["name"] for c in described["columns"]]
    assert 100 < len(shown) < 200 and shown == names[:len(shown)]
    assert list(described["rows"][0]) == shown                      # dòng mẫu khớp đúng các cột hiển thị
    assert described["omitted_columns"] == len(names) - len(shown)


def test_import_notes_are_grouped_by_kind():
    # Codex H2: một ghi chú cho mỗi cột -> 200 cột DECIMAL thành 200+ ghi chú trong response.
    import decimal
    from src.modules.database_connections.service import frame_for_import

    columns = [f"price_{i}" for i in range(30)]
    _, notes = frame_for_import(columns, [{c: decimal.Decimal("1.5") for c in columns}])
    assert len(notes) == 1 and "30 cột" in notes[0] and "và 20 cột khác" in notes[0]


async def test_generated_columns_are_described_like_select_star_returns_them(env):
    # Codex I1: PRAGMA table_info bỏ cột GENERATED nhưng SELECT * vẫn trả chúng.
    import sqlite3

    service, _, _ = env
    con = sqlite3.connect(settings.DATABASE_SOURCES.FILES_DIR / "gen.sqlite")
    con.execute(f'CREATE TABLE gen (a INTEGER, twice INTEGER GENERATED ALWAYS AS (a * 2), '
                f'"{"g" * 129}" INTEGER GENERATED ALWAYS AS (a + 1))')
    con.execute("INSERT INTO gen (a) VALUES (3)")
    con.commit()
    con.close()
    public = await _create(service, database="gen.sqlite")
    described = await service.describe_table(USER, public.id, DescribeRequest(table="gen"))
    assert [c["name"] for c in described["columns"]] == ["a", "twice"]
    assert described["rows"] == [{"a": 3, "twice": 6}] and described["omitted_columns"] == 1


def test_missing_values_and_out_of_range_integers_import_cleanly():
    # Codex I3: NaN trong cột số nguyên (MongoDB) gây ValueError/500; UBIGINT 2^63 không vừa Int64.
    import math
    from src.modules.database_connections.service import frame_for_import

    frame, _ = frame_for_import(["x"], [{"x": 1}, {"x": math.nan}, {"x": None}])
    assert str(frame["x"].dtype) == "Int64" and frame["x"].tolist()[0] == 1 and frame["x"].isna().sum() == 2
    frame, notes = frame_for_import(["id"], [{"id": 2 ** 63}, {"id": 5}])
    assert str(frame["id"].dtype) == "float64" and frame["id"].tolist() == [float(2 ** 63), 5.0]
    assert any("2^53" in n for n in notes)


async def test_column_names_are_stripped_consistently_and_clashes_are_reported(env):
    # Codex I4: import bỏ khoảng trắng tên cột -> `x` và " x " trùng nhau, tên báo về lệch tên đã lưu.
    service, dataset_repo, uploads = env
    public = await _create(service)
    clash = await service.preview_query(USER, public.id, {"kind": "sql", "sql": 'SELECT 1 AS x, 2 AS " x " FROM glass'})
    with pytest.raises(CustomException) as error:
        await service.import_preview(USER, public.id, ImportRequest(preview_id=clash.preview_id, data_name="clash"))
    assert error.value.status_code == 400 and error.value.error_code == "QUERY_INVALID" and not dataset_repo.datasets

    spaced = await service.preview_query(USER, public.id, {"kind": "sql", "sql": 'SELECT RI AS " ri " FROM glass'})
    imported = await service.import_preview(USER, public.id, ImportRequest(preview_id=spaced.preview_id, data_name="ri"))
    stored = pd.read_parquet(io.BytesIO(next(iter(uploads.values()))))
    assert imported.columns == ["ri"] == list(stored.columns) == dataset_repo.datasets[0]["source"]["columns"]


@pytest.mark.parametrize("fields,code", [
    ({"db_type": "postgres", "host": "db.internal"}, "SOURCE_ACCESS"),                      # tắt: chưa khai allowlist
])
async def test_server_sql_sources_are_off_until_hosts_are_configured(env, monkeypatch, fields, code):
    service, _, _ = env
    monkeypatch.setattr(settings.DATABASE_SOURCES, "SQL_ALLOWED_HOSTS", "")
    with pytest.raises(CustomException) as error:
        await _create(service, database="lab", username="ro", password="x", **fields)
    assert error.value.error_code == code and "đang tắt" in error.value.detail


@pytest.mark.parametrize("fields", [
    {"db_type": "postgres", "host": "evil.example"},                         # host ngoài allowlist
    {"db_type": "postgres", "host": "db.internal", "port": 6379},           # host đúng, port khác (vd Redis)
    {"db_type": "postgres", "host": "db.internal,evil.example"},            # nhiều host kiểu libpq
    {"db_type": "postgres", "host": "/var/run/postgresql"},                 # unix socket
    {"db_type": "mysql", "host": "db.internal", "port": 5432},              # sai port cho MySQL
    {"db_type": "mysql", "host": "mysql.internal", "database": "mysql"},     # database hệ thống
    {"db_type": "mysql", "host": "mysql.internal", "database": "information_schema"},
    {"db_type": "mysql", "host": "mysql.internal", "schema_name": "lab"},    # MySQL không có schema_name
    {"db_type": "postgres", "host": "db.internal", "schema_name": "pg_catalog"},
    {"db_type": "postgres", "host": "db.internal", "schema_name": "information_schema"},
    {"db_type": "postgres", "host": "db.internal", "database": "template1"},
    {"db_type": "postgres", "host": "db.internal", "username": None},       # thiếu tài khoản
    {"db_type": "sqlite", "database": "glass.sqlite", "schema_name": "lab"},
])
async def test_dangerous_server_sql_targets_are_refused(env, monkeypatch, fields):
    service, _, _ = env
    monkeypatch.setattr(settings.DATABASE_SOURCES, "SQL_ALLOWED_HOSTS", "db.internal, mysql.internal:3306")
    payload = {"database": "lab", "username": "ro", "password": "x", **fields}
    if fields["db_type"] == "sqlite":
        payload = {k: v for k, v in payload.items() if k in ("db_type", "database", "schema_name")}
    with pytest.raises(CustomException) as error:
        await _create(service, **payload)
    assert error.value.status_code == 400


async def test_server_sql_connection_hides_host_and_secret(env, monkeypatch):
    service, _, _ = env
    monkeypatch.setattr(settings.DATABASE_SOURCES, "SQL_ALLOWED_HOSTS", "db.internal,[::1]:6543")
    public = await _create(service, db_type="postgres", database="lab", host="db.internal", username="ro",
                           password="pg-secret", schema_name="sales")
    dumped = public.model_dump_json()
    assert "pg-secret" not in dumped and "db.internal" not in dumped and public.database_label == "lab.sales"
    ipv6 = await _create(service, db_type="postgres", database="lab", host="::1", port=6543, username="ro")
    assert ipv6.db_type == "postgres"
    # Allowlist đổi sau khi tạo: kết nối cũ không dùng được nữa.
    monkeypatch.setattr(settings.DATABASE_SOURCES, "SQL_ALLOWED_HOSTS", "other.internal")
    with pytest.raises(CustomException) as error:
        await service.list_tables(USER, public.id)
    assert error.value.error_code == "SOURCE_ACCESS"


# ---------------------------------------------------------------- review 2026-11-08: dọn bản xem trước


async def test_old_previews_are_pruned_per_user(env, monkeypatch):
    # Codex (P2): mỗi preview thêm một document, chỉ hết hạn khi import -> kho phình vô hạn.
    from src.modules.database_connections import service as service_module

    service, _, _ = env
    monkeypatch.setattr(service_module, "MAX_PREVIEWS_PER_USER", 3)
    public = await _create(service)
    query = {"kind": "sql", "sql": "SELECT * FROM glass", "params": {}, "row_limit": 5}
    other_user = {**USER, "_id": "other-user"}
    other = await service.create_connection(other_user, ConnectionCreate(name="x", db_type="sqlite", database="glass.sqlite"))
    await service.preview_query(other_user, other.id, query)
    ids = [(await service.preview_query(USER, public.id, query)).preview_id for _ in range(5)]
    mine = [d for d in service.repo.previews.values() if d["userId"] == USER["_id"]]
    assert sorted(str(d["_id"]) for d in mine) == sorted(ids[-3:])        # chỉ giữ 3 bản mới nhất
    assert any(d["userId"] == "other-user" for d in service.repo.previews.values())  # không đụng người khác
    # Bản hết hạn quá một ngày bị xoá; bản đang nhập thì không.
    running = service.repo.previews[ids[-1]]
    running.update(import_state="running", expires_at=0)
    service.repo.previews[ids[-2]]["expires_at"] = 0
    await service.preview_query(USER, public.id, query)
    assert ids[-1] in service.repo.previews and ids[-2] not in service.repo.previews


class _AsyncCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def skip(self, count):
        self._cursor = self._cursor.skip(count)
        return self

    def __aiter__(self):
        self._items = iter(self._cursor)
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration


class _AsyncCollection:
    def __init__(self, collection):
        self._collection = collection

    async def insert_one(self, doc):
        return self._collection.insert_one(doc)

    async def delete_many(self, query):
        return self._collection.delete_many(query)

    def find(self, *args, **kwargs):
        return _AsyncCursor(self._collection.find(*args, **kwargs))


async def test_repository_prune_query_against_mongo_semantics():
    # Kiểm đúng câu truy vấn Mongo của repository thật (mongomock bọc async).
    from src.modules.database_connections.repository import ConnectionRepository

    database = mongomock.MongoClient().db
    repo = ConnectionRepository(SimpleNamespace(
        tbl_DatabaseConnection=_AsyncCollection(database.tbl_DatabaseConnection),
        tbl_DatabasePreview=_AsyncCollection(database.tbl_DatabasePreview),
    ))
    previews = database.tbl_DatabasePreview
    for i in range(6):
        previews.insert_one({"userId": "u1", "created_at": float(i), "expires_at": 100.0 + i, "import_state": None})
    previews.insert_one({"userId": "u1", "created_at": -1.0, "expires_at": 0.0, "import_state": "running"})
    previews.insert_one({"userId": "u2", "created_at": 0.0, "expires_at": 0.0, "import_state": None})
    await repo.prune_previews("u1", expired_before=101.5, keep=2)
    left = sorted((d["userId"], d["created_at"]) for d in previews.find())
    assert left == [("u1", -1.0), ("u1", 4.0), ("u1", 5.0), ("u2", 0.0)]


async def test_prune_does_not_delete_a_preview_claimed_for_import_in_between():
    # Codex vòng 2 (P2): prune tìm bản rảnh -> import chuyển bản đó sang running -> prune xoá theo _id.
    from src.modules.database_connections.repository import ConnectionRepository

    database = mongomock.MongoClient().db
    previews = database.tbl_DatabasePreview

    class RacingCollection(_AsyncCollection):
        def find(self, *args, **kwargs):
            cursor = super().find(*args, **kwargs)
            previews.update_many({"created_at": 0.0}, {"$set": {"import_state": "running"}})  # import nhận chỗ
            return cursor

    repo = ConnectionRepository(SimpleNamespace(
        tbl_DatabaseConnection=_AsyncCollection(database.tbl_DatabaseConnection),
        tbl_DatabasePreview=RacingCollection(previews),
    ))
    for i in range(3):
        previews.insert_one({"userId": "u1", "created_at": float(i), "expires_at": 1e12, "import_state": None})
    await repo.prune_previews("u1", expired_before=0.0, keep=1)
    left = sorted(d["created_at"] for d in previews.find())
    assert 0.0 in left and 2.0 in left and 1.0 not in left
