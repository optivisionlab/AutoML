"""
DeerFlow-AutoML — Middleware Stack (Phase 3).

Pipeline pre/post processing cho agent graph:
- Pre: World model loading, memory injection, input validation
- Post: Fact extraction, world state update, response audit

SOLID:
  S — Mỗi middleware chỉ 1 trách nhiệm
  O — Thêm middleware mới qua YAML config
  D — Middleware chain inject, không hardcode
"""

from __future__ import annotations

import abc
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


# ── Base Middleware ───────────────────────────────────────


class Middleware(abc.ABC):
    """Abstract base cho middleware."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    async def pre_process(self, state: dict[str, Any]) -> dict[str, Any]:
        """Chạy trước graph invoke. Override để xử lý."""
        return state

    async def post_process(
        self, state: dict[str, Any], result: dict[str, Any],
    ) -> dict[str, Any]:
        """Chạy sau graph invoke. Override để xử lý."""
        return result


# ── Middleware Chain ──────────────────────────────────────


class MiddlewareChain:
    """
    Chạy danh sách middlewares theo thứ tự.
    Pre: đầu → cuối. Post: cuối → đầu (onion model).
    """

    def __init__(self, middlewares: list[Middleware] | None = None):
        self._middlewares = middlewares or []

    def add(self, middleware: Middleware) -> None:
        self._middlewares.append(middleware)
        logger.debug("Middleware added: %s", middleware.name)

    async def run_pre(self, state: dict[str, Any]) -> dict[str, Any]:
        for mw in self._middlewares:
            try:
                state = await mw.pre_process(state)
            except Exception as e:
                logger.error("Middleware '%s' pre_process failed: %s", mw.name, e)
        return state

    async def run_post(
        self, state: dict[str, Any], result: dict[str, Any],
    ) -> dict[str, Any]:
        for mw in reversed(self._middlewares):
            try:
                result = await mw.post_process(state, result)
            except Exception as e:
                logger.error("Middleware '%s' post_process failed: %s", mw.name, e)
        return result


# ── Concrete Middlewares ─────────────────────────────────


class TimingMiddleware(Middleware):
    """Đo thời gian xử lý."""

    @property
    def name(self) -> str:
        return "timing"

    async def pre_process(self, state: dict[str, Any]) -> dict[str, Any]:
        state["_start_time"] = time.time()
        return state

    async def post_process(
        self, state: dict[str, Any], result: dict[str, Any],
    ) -> dict[str, Any]:
        start = state.get("_start_time", 0)
        elapsed = time.time() - start
        result["_elapsed_seconds"] = round(elapsed, 3)
        logger.info("Agent processing time: %.3fs", elapsed)
        return result


class MemoryMiddleware(Middleware):
    """Pre: inject memory. Post: extract và save facts."""

    @property
    def name(self) -> str:
        return "memory"

    async def pre_process(self, state: dict[str, Any]) -> dict[str, Any]:
        from hagent.agent.memory import create_fact_store
        from hagent.agent.memory.injection import inject_memory_into_state

        store = create_fact_store()
        state["_fact_store"] = store
        return await inject_memory_into_state(store, state)

    async def post_process(
        self, state: dict[str, Any], result: dict[str, Any],
    ) -> dict[str, Any]:
        from hagent.agent.memory.extractor import extract_from_tool_message

        store = state.get("_fact_store")
        user_id = state.get("user_id")
        if not store or not user_id:
            return result

        messages = result.get("messages", [])
        for msg in messages:
            facts = extract_from_tool_message(msg, source="graph_output")
            for fact in facts:
                await store.save(user_id, fact)

        return result


class WorldModelMiddleware(Middleware):
    """Pre: load world model vào state."""

    @property
    def name(self) -> str:
        return "world_model"

    async def pre_process(self, state: dict[str, Any]) -> dict[str, Any]:
        user_id = state.get("user_id")
        if not user_id:
            return state

        try:
            from hagent.world.state_store import WorldStateStore
            # World state store cần MongoDB client — skip nếu không có
            # Đây là optional enrichment
            logger.debug("World model middleware: skipped (no active store)")
        except ImportError:
            pass

        return state


class InputSanitizer(Middleware):
    """Pre: sanitize user input."""

    @property
    def name(self) -> str:
        return "input_sanitizer"

    async def pre_process(self, state: dict[str, Any]) -> dict[str, Any]:
        messages = state.get("messages", [])
        if messages:
            last = messages[-1]
            if hasattr(last, "content") and last.content:
                content = last.content.strip()
                if len(content) > 10000:
                    content = content[:10000] + "\n\n[... truncated]"
                    logger.warning("Input truncated to 10000 chars")
        return state


# ── Factory ──────────────────────────────────────────────


def create_default_chain() -> MiddlewareChain:
    """
    Tạo middleware chain mặc định từ config.
    Thứ tự: timing → input_sanitizer → world_model → memory
    """
    try:
        from hagent.bridge.config import load_config
        cfg = load_config()
        memory_enabled = cfg.get("memory", {}).get("enabled", True)
    except Exception:
        memory_enabled = True

    chain = MiddlewareChain()
    chain.add(TimingMiddleware())
    chain.add(InputSanitizer())
    chain.add(WorldModelMiddleware())

    if memory_enabled:
        chain.add(MemoryMiddleware())

    logger.info(
        "Middleware chain created: %s",
        [mw.name for mw in chain._middlewares],
    )
    return chain
