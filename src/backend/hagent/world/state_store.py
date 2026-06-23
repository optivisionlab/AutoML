import dataclasses
import inspect
from typing import Optional, Dict, Any

try:
    from pymongo import ReturnDocument
except ImportError:  # pragma: no cover — pymongo always present at runtime
    class ReturnDocument:  # type: ignore[no-redef]
        AFTER = True
        BEFORE = False

from .schema import WorldState, utc_now

_WORLD_STATE_FIELDS = {f.name for f in dataclasses.fields(WorldState)}


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


def _world_state_from_doc(doc: Dict[str, Any]) -> WorldState:
    clean_doc = {k: v for k, v in doc.items() if k in _WORLD_STATE_FIELDS}
    return WorldState(**clean_doc)

class WorldStateStore:
    def __init__(self, client: Any, db_name: str, collection_name: str, ttl_seconds: int):
        self.client = client
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.ttl_seconds = ttl_seconds

    async def ensure_indexes(self):
        await _maybe_await(self.collection.create_index("user_id", unique=True))
        if self.ttl_seconds > 0:
            await _maybe_await(self.collection.create_index(
                "updated_at", expireAfterSeconds=self.ttl_seconds
            ))

    async def ensure(self, user_id: str) -> None:
        """Đảm bảo một bản ghi world state tồn tại cho user."""
        now = utc_now()
        await _maybe_await(self.collection.update_one(
            {"user_id": user_id},
            {"$setOnInsert": {"created_at": now, "updated_at": now, "datasets": {}, "jobs": {}, "goals": []}},
            upsert=True
        ))

    async def get(self, user_id: str) -> Optional[WorldState]:
        """Lấy world state của một user."""
        doc = await _maybe_await(self.collection.find_one({"user_id": user_id}))
        if doc:
            return _world_state_from_doc(doc)
        return None

    async def upsert(self, user_id: str, patch: Dict[str, Any]) -> Optional[WorldState]:
        """Cập nhật hoặc chèn một phần của world state."""
        patch_with_timestamp = patch.copy()
        patch_with_timestamp["updated_at"] = utc_now()

        updated_doc = await _maybe_await(self.collection.find_one_and_update(
            {"user_id": user_id},
            {"$set": patch_with_timestamp},
            upsert=True,
            return_document=ReturnDocument.AFTER
        ))
        if updated_doc:
            return _world_state_from_doc(updated_doc)
        return None
