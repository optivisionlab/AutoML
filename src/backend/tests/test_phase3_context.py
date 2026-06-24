"""
Tests cho Phase 3 — Context Engineering.

Test categories:
1. Fact & FactStore (memory storage)
2. Fact Extractor (extraction rules)
3. Memory Injection (formatting + injection)
4. ToolCache (TTL cache)
5. Middleware Stack (chain, pre/post)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def run_async(coro):
    """Helper: chạy async function trong test sync."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ══════════════════════════════════════════════════════════
# 1. Fact & FactStore
# ══════════════════════════════════════════════════════════


class TestFact:

    def test_create_fact(self):
        from hagent.agent.memory import Fact
        f = Fact(key="test", content="Hello", category="general")
        assert f.key == "test"
        assert f.confidence == 1.0

    def test_to_dict(self):
        from hagent.agent.memory import Fact
        f = Fact(key="k", content="c")
        d = f.to_dict()
        assert d["key"] == "k"
        assert "created_at" in d

    def test_from_dict(self):
        from hagent.agent.memory import Fact
        f = Fact.from_dict({"key": "k", "content": "c", "category": "model"})
        assert f.category == "model"


class TestLocalFactStore:

    def _make_store(self, tmp_path):
        from hagent.agent.memory import LocalFactStore
        return LocalFactStore(tmp_path)

    def test_save_and_get(self, tmp_path):
        from hagent.agent.memory import Fact
        store = self._make_store(tmp_path)
        f = Fact(key="ds1", content="Dataset iris", category="dataset")
        run_async(store.save("user1", f))
        result = run_async(store.get("user1", "ds1"))
        assert result is not None
        assert result.content == "Dataset iris"
        assert result.access_count == 1

    def test_search_by_category(self, tmp_path):
        from hagent.agent.memory import Fact
        store = self._make_store(tmp_path)
        run_async(store.save("u1", Fact(key="a", content="dataset A", category="dataset")))
        run_async(store.save("u1", Fact(key="b", content="model B", category="model")))
        results = run_async(store.search("u1", category="dataset"))
        assert len(results) == 1
        assert results[0].key == "a"

    def test_search_by_query(self, tmp_path):
        from hagent.agent.memory import Fact
        store = self._make_store(tmp_path)
        run_async(store.save("u1", Fact(key="a", content="iris dataset 150 rows")))
        run_async(store.save("u1", Fact(key="b", content="wine dataset 178 rows")))
        results = run_async(store.search("u1", query="iris"))
        assert len(results) == 1

    def test_get_all(self, tmp_path):
        from hagent.agent.memory import Fact
        store = self._make_store(tmp_path)
        for i in range(5):
            run_async(store.save("u1", Fact(key=f"k{i}", content=f"fact {i}")))
        all_facts = run_async(store.get_all("u1"))
        assert len(all_facts) == 5

    def test_delete(self, tmp_path):
        from hagent.agent.memory import Fact
        store = self._make_store(tmp_path)
        run_async(store.save("u1", Fact(key="x", content="temp")))
        assert run_async(store.delete("u1", "x"))
        assert run_async(store.get("u1", "x")) is None

    def test_clear(self, tmp_path):
        from hagent.agent.memory import Fact
        store = self._make_store(tmp_path)
        for i in range(3):
            run_async(store.save("u1", Fact(key=f"k{i}", content=f"f{i}")))
        count = run_async(store.clear("u1"))
        assert count == 3
        assert len(run_async(store.get_all("u1"))) == 0

    def test_user_isolation(self, tmp_path):
        from hagent.agent.memory import Fact
        store = self._make_store(tmp_path)
        run_async(store.save("alice", Fact(key="a", content="alice data")))
        run_async(store.save("bob", Fact(key="b", content="bob data")))
        assert run_async(store.get("alice", "b")) is None
        assert run_async(store.get("bob", "a")) is None


# ══════════════════════════════════════════════════════════
# 2. Fact Extractor
# ══════════════════════════════════════════════════════════


class TestFactExtractor:

    def test_extract_list_datasets(self):
        from hagent.agent.memory.extractor import extract_from_tool_output
        facts = extract_from_tool_output("list_datasets", {
            "datasets": [{"id": "d1", "name": "iris"}, {"id": "d2", "name": "wine"}]
        })
        assert len(facts) == 1
        assert "iris" in facts[0].content
        assert facts[0].category == "dataset"

    def test_extract_dataset_info(self):
        from hagent.agent.memory.extractor import extract_from_tool_output
        facts = extract_from_tool_output("get_dataset_info", {
            "id": "d1", "name": "iris.csv", "n_rows": 150, "n_cols": 5,
            "problem_type": "classification", "target": "species",
        })
        assert len(facts) == 1
        assert "150" in facts[0].content
        assert "classification" in facts[0].content

    def test_extract_start_training(self):
        from hagent.agent.memory.extractor import extract_from_tool_output
        facts = extract_from_tool_output("start_training", {
            "job_id": "j1", "dataset_id": "d1",
        })
        assert len(facts) == 1
        assert facts[0].category == "workflow"

    def test_extract_job_info(self):
        from hagent.agent.memory.extractor import extract_from_tool_output
        facts = extract_from_tool_output("get_job_info", {
            "id": "j1", "status": "completed", "best_model": "RF", "best_score": 0.95,
        })
        assert len(facts) == 1
        assert "RF" in facts[0].content
        assert facts[0].category == "model"

    def test_extract_available_models(self):
        from hagent.agent.memory.extractor import extract_from_tool_output
        facts = extract_from_tool_output("get_available_models", {
            "models": ["RandomForest", "XGBoost", "SVM"],
        })
        assert len(facts) == 1
        assert "RandomForest" in facts[0].content

    def test_extract_unknown_tool(self):
        from hagent.agent.memory.extractor import extract_from_tool_output
        facts = extract_from_tool_output("unknown_tool", {"data": 123})
        assert len(facts) == 0


# ══════════════════════════════════════════════════════════
# 3. Memory Injection
# ══════════════════════════════════════════════════════════


class TestMemoryInjection:

    def test_format_empty(self):
        from hagent.agent.memory.injection import _format_facts
        assert _format_facts([]) == ""

    def test_format_facts(self):
        from hagent.agent.memory import Fact
        from hagent.agent.memory.injection import _format_facts
        facts = [
            Fact(key="a", content="iris has 150 rows", category="dataset"),
            Fact(key="b", content="RF best model", category="model"),
        ]
        text = _format_facts(facts)
        assert "Trí nhớ dài hạn" in text
        assert "iris" in text
        assert "RF" in text
        assert "📊" in text  # Dataset emoji

    def test_load_memory_context(self, tmp_path):
        from hagent.agent.memory import Fact, LocalFactStore
        from hagent.agent.memory.injection import load_memory_context
        store = LocalFactStore(tmp_path)
        run_async(store.save("u1", Fact(key="a", content="test fact")))
        ctx = run_async(load_memory_context(store, "u1"))
        assert "test fact" in ctx

    def test_load_empty_user(self, tmp_path):
        from hagent.agent.memory import LocalFactStore
        from hagent.agent.memory.injection import load_memory_context
        store = LocalFactStore(tmp_path)
        ctx = run_async(load_memory_context(store, "nonexistent"))
        assert ctx == ""

    def test_inject_no_user(self):
        from hagent.agent.memory import LocalFactStore
        from hagent.agent.memory.injection import inject_memory_into_state
        store = LocalFactStore(tempfile.mkdtemp())
        state = {"messages": [], "user_id": None}
        result = run_async(inject_memory_into_state(store, state))
        assert "memory_context" not in result or result.get("memory_context") is None


# ══════════════════════════════════════════════════════════
# 4. ToolCache
# ══════════════════════════════════════════════════════════


class TestToolCache:

    def test_set_get(self):
        from hagent.agent.cache import ToolCache
        cache = ToolCache(ttl_seconds=60)
        cache.set("list_datasets", {}, {"datasets": [1, 2]})
        result = cache.get("list_datasets", {})
        assert result == {"datasets": [1, 2]}

    def test_miss(self):
        from hagent.agent.cache import ToolCache
        cache = ToolCache()
        assert cache.get("nonexistent", {}) is None

    def test_ttl_expiry(self):
        from hagent.agent.cache import ToolCache
        cache = ToolCache(ttl_seconds=0)  # Expire immediately
        cache.set("tool", {}, "value")
        time.sleep(0.01)
        assert cache.get("tool", {}) is None

    def test_invalidate(self):
        from hagent.agent.cache import ToolCache
        cache = ToolCache()
        cache.set("t", {"a": 1}, "v")
        assert cache.invalidate("t", {"a": 1})
        assert cache.get("t", {"a": 1}) is None

    def test_clear(self):
        from hagent.agent.cache import ToolCache
        cache = ToolCache()
        for i in range(5):
            cache.set(f"t{i}", {}, i)
        assert cache.clear() == 5
        assert cache.get("t0", {}) is None

    def test_stats(self):
        from hagent.agent.cache import ToolCache
        cache = ToolCache(ttl_seconds=60, max_entries=10)
        cache.set("a", {}, 1)
        cache.get("a", {})  # hit
        cache.get("b", {})  # miss
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1

    def test_eviction(self):
        from hagent.agent.cache import ToolCache
        cache = ToolCache(max_entries=3)
        for i in range(5):
            cache.set(f"t{i}", {}, i)
        assert len(cache._cache) <= 3

    def test_different_args(self):
        from hagent.agent.cache import ToolCache
        cache = ToolCache()
        cache.set("tool", {"id": "a"}, "val_a")
        cache.set("tool", {"id": "b"}, "val_b")
        assert cache.get("tool", {"id": "a"}) == "val_a"
        assert cache.get("tool", {"id": "b"}) == "val_b"


# ══════════════════════════════════════════════════════════
# 5. Middleware Stack
# ══════════════════════════════════════════════════════════


class TestMiddleware:

    def test_timing_middleware(self):
        from hagent.agent.middlewares import TimingMiddleware
        mw = TimingMiddleware()
        assert mw.name == "timing"
        state = run_async(mw.pre_process({}))
        assert "_start_time" in state
        result = run_async(mw.post_process(state, {}))
        assert "_elapsed_seconds" in result

    def test_input_sanitizer(self):
        from hagent.agent.middlewares import InputSanitizer
        mw = InputSanitizer()
        assert mw.name == "input_sanitizer"
        state = run_async(mw.pre_process({"messages": []}))
        assert "messages" in state

    def test_middleware_chain(self):
        from hagent.agent.middlewares import MiddlewareChain, TimingMiddleware, InputSanitizer
        chain = MiddlewareChain()
        chain.add(TimingMiddleware())
        chain.add(InputSanitizer())
        state = run_async(chain.run_pre({"messages": []}))
        assert "_start_time" in state
        result = run_async(chain.run_post(state, {}))
        assert "_elapsed_seconds" in result

    def test_chain_error_handling(self):
        from hagent.agent.middlewares import Middleware, MiddlewareChain

        class BrokenMiddleware(Middleware):
            @property
            def name(self): return "broken"
            async def pre_process(self, state):
                raise RuntimeError("boom")

        chain = MiddlewareChain([BrokenMiddleware()])
        # Should not raise — errors are logged
        state = run_async(chain.run_pre({"x": 1}))
        assert "x" in state

    def test_create_default_chain(self):
        from hagent.agent.middlewares import create_default_chain
        chain = create_default_chain()
        assert len(chain._middlewares) >= 3
        names = [mw.name for mw in chain._middlewares]
        assert "timing" in names
        assert "input_sanitizer" in names
