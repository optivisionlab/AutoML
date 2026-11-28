"""Nguồn MongoDB chỉ-đọc (mongomock, dữ liệu Glass thật): metadata, find, aggregate, chặn toán tử nguy hiểm."""
# Third-party Libraries
import mongomock
import pytest

# Local Libraries
from src.adapters.mongodb import MongoSource
from src.adapters.query_policy import UnsafeQueryError
from src.adapters.query_runner import SourceAccessError
from tests.database_sources import glass_frame


@pytest.fixture
def source():
    client = mongomock.MongoClient()
    client["lab"]["glass"].insert_many(glass_frame().to_dict(orient="records"))
    return MongoSource(database="lab", client=client)


def test_system_databases_and_unknown_hosts_are_refused():
    with pytest.raises(SourceAccessError):
        MongoSource(database="admin", client=mongomock.MongoClient())
    with pytest.raises(SourceAccessError):
        MongoSource(database="lab", host="10.0.0.5", allowed_hosts={"localhost"})


def test_metadata_is_inferred_from_a_sample(source):
    assert source.list_tables() == ["glass"]
    info = source.describe("glass", 3)
    names = {c["name"] for c in info["columns"]}
    assert set(glass_frame().columns) <= names and "_id" in names
    assert info["schema_inferred"] is True and len(info["rows"]) == 3
    assert isinstance(info["rows"][0]["_id"], str)          # ObjectId -> chuỗi


def test_find_with_projection_sort_and_cap(source):
    result = source.execute({"kind": "find", "collection": "glass", "filter": {"Type": 1},
                             "projection": {"_id": 0, "RI": 1, "Type": 1}, "sort": {"RI": -1}}, cap=5)
    expected = glass_frame()[glass_frame()["Type"] == 1].sort_values("RI", ascending=False)["RI"].head(5).tolist()
    assert result.columns == ["RI", "Type"] and result.truncated is True
    assert [r["RI"] for r in result.rows] == pytest.approx(expected)


def test_aggregate_group_matches_pandas(source):
    result = source.execute({"kind": "aggregate", "collection": "glass", "pipeline": [
        {"$group": {"_id": "$Type", "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}]}, cap=20)
    expected = glass_frame()["Type"].value_counts().sort_index()
    assert [(r["_id"], r["n"]) for r in result.rows] == list(expected.items())
    assert result.truncated is False


@pytest.mark.parametrize("query", [
    {"kind": "aggregate", "collection": "glass", "pipeline": [{"$out": "stolen"}]},
    {"kind": "find", "collection": "glass", "filter": {"$where": "sleep(1000)"}},
])
def test_dangerous_operators_never_reach_the_server(source, query):
    with pytest.raises(UnsafeQueryError):
        source.execute(query, cap=5)
    assert source.list_tables() == ["glass"]


def test_result_budget_is_enforced_while_reading(source):
    # Codex E1: không nạp hết document rồi mới đo - dừng ngay khi vượt trần.
    from src.adapters.query_runner import QueryFailedError

    with pytest.raises(QueryFailedError, match="quá lớn"):
        source.execute({"kind": "find", "collection": "glass"}, cap=500, max_bytes=2_000)
    with pytest.raises(QueryFailedError, match="quá lớn"):
        source.describe("glass", 10, max_bytes=200)


def test_bson_int64_is_normalised_to_int():
    # Codex E4: PyMongo giải mã int64 thành bson.int64.Int64 (lớp con int) - mongomock thì không.
    import bson
    from bson.int64 import Int64
    from src.adapters.mongodb import normalize_document

    decoded = bson.decode(bson.encode({"big": Int64(9007199254740993), "small": Int64(3)}))
    assert type(decoded["big"]) is Int64
    normalized = normalize_document(decoded)
    assert type(normalized["big"]) is int and normalized["big"] == 9007199254740993


def test_rows_stay_sparse_and_field_explosions_are_refused():
    # Codex F1: document mỗi cái một trường riêng từng bị điền đủ mọi cột -> hàng triệu ô.
    from src.adapters.query_runner import QueryFailedError

    client = mongomock.MongoClient()
    client["lab"]["wide"].insert_many([{f"f{i}": i} for i in range(300)])
    source = MongoSource(database="lab", client=client)
    with pytest.raises(QueryFailedError, match="trường khác nhau"):
        source.execute({"kind": "find", "collection": "wide", "projection": {"_id": 0}}, cap=500)
    few = source.execute({"kind": "find", "collection": "wide", "projection": {"_id": 0}}, cap=3)
    assert few.columns == ["f0", "f1", "f2", "f3"] and few.rows[0] == {"f0": 0}
