"""
DeerFlow-AutoML — Tool Result Cache (Phase 3).

TTL-based in-memory cache cho tool results.
Config đọc từ YAML agent.cache section.

SOLID:
  S — Chỉ làm caching
  D — Config inject từ YAML
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class ToolCache:
    """
    In-memory TTL cache cho tool results.

    Giảm API calls lặp lại trong cùng conversation.
    Config: agent.cache.ttl_seconds, agent.cache.max_entries
    """

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 100):
        self._cache: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl_seconds
        self._max = max_entries
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(tool_name: str, args: dict) -> str:
        """Tạo cache key từ tool name + args."""
        raw = f"{tool_name}:{json.dumps(args, sort_keys=True, default=str)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, tool_name: str, args: dict) -> Any | None:
        """Lấy cached result. None nếu miss hoặc expired."""
        key = self._make_key(tool_name, args)
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None

        ts, value = entry
        if time.time() - ts > self._ttl:
            del self._cache[key]
            self._misses += 1
            return None

        self._hits += 1
        return value

    def set(self, tool_name: str, args: dict, value: Any) -> None:
        """Lưu result vào cache."""
        if len(self._cache) >= self._max:
            self._evict_oldest()

        key = self._make_key(tool_name, args)
        self._cache[key] = (time.time(), value)

    def invalidate(self, tool_name: str, args: dict) -> bool:
        """Xóa một entry."""
        key = self._make_key(tool_name, args)
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> int:
        """Xóa toàn bộ cache."""
        count = len(self._cache)
        self._cache.clear()
        return count

    def stats(self) -> dict[str, Any]:
        """Trả về cache statistics."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_entries": self._max,
            "ttl_seconds": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
        }

    def _evict_oldest(self) -> None:
        """Xóa entry cũ nhất khi cache đầy."""
        if not self._cache:
            return
        oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
        del self._cache[oldest_key]


# ── Singleton ────────────────────────────────────────────

_cache: ToolCache | None = None


def get_tool_cache() -> ToolCache:
    """Singleton ToolCache — config từ YAML."""
    global _cache
    if _cache is None:
        try:
            from hagent.bridge.config import get_cache_config
            cfg = get_cache_config()
            if not cfg.get("enabled", True):
                _cache = ToolCache(ttl_seconds=0, max_entries=0)
            else:
                _cache = ToolCache(
                    ttl_seconds=cfg.get("ttl_seconds", 300),
                    max_entries=cfg.get("max_entries", 100),
                )
        except Exception:
            _cache = ToolCache()
    return _cache


def reset_cache() -> None:
    """Reset cache singleton."""
    global _cache
    _cache = None
