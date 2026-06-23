import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from hagent.world.state_store import WorldStateStore


class FakeCollection:
    def __init__(self):
        self.doc = None
        self.indexes = []

    async def create_index(self, *args, **kwargs):
        self.indexes.append((args, kwargs))
        return "idx"

    async def update_one(self, query, update, upsert=False):
        if self.doc is None and upsert:
            self.doc = {"_id": "mongo-internal", **query, **update.get("$setOnInsert", {})}

    async def find_one(self, query):
        if self.doc and self.doc.get("user_id") == query.get("user_id"):
            return dict(self.doc)
        return None

    async def find_one_and_update(self, query, update, upsert=False, return_document=False):
        if self.doc is None and upsert:
            self.doc = {"_id": "mongo-internal", **query}
        if self.doc and self.doc.get("user_id") == query.get("user_id"):
            self.doc.update(update.get("$set", {}))
            return dict(self.doc)
        return None


class FakeDb:
    def __init__(self, collection):
        self.collection = collection

    def __getitem__(self, name):
        return self.collection


class FakeClient:
    def __init__(self, collection):
        self.collection = collection

    def __getitem__(self, name):
        return FakeDb(self.collection)


class TestWorldStateStore(unittest.IsolatedAsyncioTestCase):
    async def test_async_store_round_trip_ignores_mongo_id(self):
        collection = FakeCollection()
        store = WorldStateStore(FakeClient(collection), "db", "world_states", 60)

        await store.ensure_indexes()
        await store.ensure("user-1")
        state = await store.get("user-1")

        self.assertEqual(state.user_id, "user-1")
        self.assertNotIn("_id", state.to_dict())
        self.assertEqual(len(collection.indexes), 2)

        updated = await store.upsert(
            "user-1",
            {"datasets": {"ds1": {"id": "ds1", "name": "Dataset"}}},
        )

        self.assertEqual(updated.datasets["ds1"]["name"], "Dataset")
        self.assertNotIn("_id", updated.to_dict())

    async def test_extra_fields_in_mongo_doc_are_ignored(self):
        """Verify documents with extra fields don't crash _world_state_from_doc."""
        collection = FakeCollection()
        store = WorldStateStore(FakeClient(collection), "db", "world_states", 60)

        # Simulate a MongoDB document with extra unexpected fields
        collection.doc = {
            "_id": "mongo-internal",
            "user_id": "user-extra",
            "datasets": {},
            "jobs": {},
            "goals": [],
            "updated_at": "2026-01-01T00:00:00+00:00",
            "created_at": "2026-01-01T00:00:00+00:00",
            "some_migration_field": "should_be_ignored",
            "__v": 0,
        }

        state = await store.get("user-extra")
        self.assertIsNotNone(state)
        self.assertEqual(state.user_id, "user-extra")
        # Extra fields should NOT appear in the WorldState object
        self.assertFalse(hasattr(state, "some_migration_field"))
        self.assertFalse(hasattr(state, "__v"))


if __name__ == "__main__":
    unittest.main()
