"""
Dữ liệu và đồ giả dùng chung cho test nguồn dữ liệu ngoài (SQL agent / kết nối đã lưu).

Dữ liệu THẬT: bộ Glass Identification (UCI, 214 dòng), bản sao byte-đúng của
docs/data_automl/user/glass.csv (sha256 2149f02a...70680c7) đặt trong tests/fixtures/ để test chạy
được cả khi build Docker (build context chỉ có src/backend). Nạp vào SQLite / DuckDB / MongoDB giả -
không sinh số liệu.
"""
# Standard Libraries
import sqlite3
from pathlib import Path

# Third-party Libraries
import pandas as pd
from bson import ObjectId


GLASS_CSV = Path(__file__).resolve().parent / "fixtures" / "glass.csv"


def glass_frame() -> pd.DataFrame:
    return pd.read_csv(GLASS_CSV)


def make_sqlite(directory: Path, name: str = "glass.sqlite") -> Path:
    path = directory / name
    con = sqlite3.connect(path)
    glass_frame().to_sql("glass", con, index=False)
    con.close()
    return path


def make_duckdb(directory: Path, name: str = "glass.duckdb") -> Path:
    import duckdb

    path = directory / name
    con = duckdb.connect(str(path))
    frame = glass_frame()
    con.register("frame", frame)
    con.execute("CREATE TABLE glass AS SELECT * FROM frame")
    con.close()
    return path


class FakeConnectionRepository:
    """ConnectionRepository trong bộ nhớ, cùng hợp đồng (lọc theo _id + userId)."""

    def __init__(self):
        self.connections: dict[str, dict] = {}
        self.previews: dict[str, dict] = {}

    async def create(self, doc):
        doc = dict(doc)
        doc["_id"] = ObjectId()
        self.connections[str(doc["_id"])] = doc
        return dict(doc)

    async def list_by_user(self, user_id, skip, limit):
        docs = [d for d in self.connections.values() if d["userId"] == user_id]
        return [dict(d) for d in docs[skip:skip + limit]], len(docs)

    async def get(self, connection_id, user_id):
        doc = self.connections.get(connection_id)
        return dict(doc) if doc and doc["userId"] == user_id else None

    async def update(self, connection_id, user_id, fields, now):
        doc = self.connections.get(connection_id)
        if not doc or doc["userId"] != user_id:
            return None
        doc.update(fields)
        doc["updated_at"] = now
        doc["version"] = doc.get("version", 1) + 1
        return dict(doc)

    async def delete(self, connection_id, user_id):
        doc = self.connections.get(connection_id)
        if not doc or doc["userId"] != user_id:
            return False
        del self.connections[connection_id]
        return True

    async def create_preview(self, doc):
        doc = dict(doc)
        doc["_id"] = ObjectId()
        self.previews[str(doc["_id"])] = doc
        return dict(doc)

    async def prune_previews(self, user_id, expired_before, keep):
        mine = [d for d in self.previews.values() if d["userId"] == user_id and d.get("import_state") != "running"]
        for doc in mine:
            if doc["expires_at"] < expired_before:
                self.previews.pop(str(doc["_id"]), None)
        alive = sorted((d for d in mine if str(d["_id"]) in self.previews), key=lambda d: d["created_at"], reverse=True)
        for doc in alive[keep:]:
            self.previews.pop(str(doc["_id"]), None)

    async def get_preview(self, preview_id, user_id):
        doc = self.previews.get(preview_id)
        return dict(doc) if doc and doc["userId"] == user_id else None

    async def claim_preview_import(self, preview_id, user_id, now, lease_seconds, token):
        doc = self.previews.get(preview_id)
        if not doc or doc["userId"] != user_id:
            return None
        stale = doc.get("import_state") == "running" and doc.get("claimed_at", 0) < now - lease_seconds
        if doc.get("import_state") is not None and not stale:
            return None
        doc.update(import_state="running", claimed_at=now, claim_token=token)
        return dict(doc)

    async def finish_preview_import(self, preview_id, user_id, result, token=None):
        doc = self.previews[preview_id]
        if token is not None and doc.get("claim_token") != token:
            return
        if result:
            doc.update(import_state="done", import_result=result)
        else:
            doc["import_state"] = None


class FakeDatasetRepository:
    def __init__(self):
        self.datasets: list[dict] = []

    async def create_dataset(self, doc):
        doc = dict(doc)
        doc.setdefault("_id", ObjectId())
        if any(str(d["_id"]) == str(doc["_id"]) for d in self.datasets):
            raise ValueError("duplicate key _id")           # như unique _id của MongoDB
        self.datasets.append(doc)
        return dict(doc)

    async def get_dataset_by_id(self, dataset_id, include_data_link=False):
        return next((dict(d) for d in self.datasets if str(d["_id"]) == str(dataset_id)), None)
