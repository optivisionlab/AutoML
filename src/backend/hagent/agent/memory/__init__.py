"""
DeerFlow-AutoML — Memory Storage (Phase 3).

Lưu trữ facts (kiến thức rút trích từ conversations).
Config-driven: backend type + TTL đọc từ YAML.

SOLID:
  S — Chỉ làm lưu trữ/truy xuất facts
  O — Thêm backend mới (Redis, MongoDB) qua kế thừa
  D — Backend inject qua factory, không hardcode
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Fact schema ──────────────────────────────────────────


@dataclass
class Fact:
    """Một fact rút trích từ conversation."""
    key: str                    # Unique identifier
    content: str                # Nội dung fact
    category: str = "general"   # general | dataset | model | preference | workflow
    confidence: float = 1.0     # 0.0 → 1.0
    source: str = ""            # Conversation/tool mà fact được rút trích từ
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0       # Số lần fact được truy cập

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Fact:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── Abstract Store ───────────────────────────────────────


class FactStore:
    """
    Abstract base cho fact storage.
    Cung cấp CRUD operations cho facts.
    """

    async def save(self, user_id: str, fact: Fact) -> None:
        raise NotImplementedError

    async def get(self, user_id: str, key: str) -> Fact | None:
        raise NotImplementedError

    async def search(
        self,
        user_id: str,
        *,
        category: str | None = None,
        query: str | None = None,
        limit: int = 20,
    ) -> list[Fact]:
        raise NotImplementedError

    async def get_all(self, user_id: str) -> list[Fact]:
        raise NotImplementedError

    async def delete(self, user_id: str, key: str) -> bool:
        raise NotImplementedError

    async def clear(self, user_id: str) -> int:
        raise NotImplementedError


# ── Local File Store ─────────────────────────────────────


class LocalFactStore(FactStore):
    """
    File-based fact store — lưu JSON trên disk.
    Phù hợp cho dev/test. Production dùng MongoDB store.
    """

    def __init__(self, storage_dir: str | Path):
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _user_file(self, user_id: str) -> Path:
        safe_id = user_id.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe_id}.json"

    def _load_facts(self, user_id: str) -> dict[str, dict]:
        fpath = self._user_file(user_id)
        if fpath.exists():
            try:
                return json.loads(fpath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_facts(self, user_id: str, facts: dict[str, dict]) -> None:
        fpath = self._user_file(user_id)
        fpath.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")

    async def save(self, user_id: str, fact: Fact) -> None:
        facts = self._load_facts(user_id)
        fact.updated_at = time.time()
        facts[fact.key] = fact.to_dict()
        self._save_facts(user_id, facts)
        logger.debug("Saved fact '%s' for user '%s'", fact.key, user_id)

    async def get(self, user_id: str, key: str) -> Fact | None:
        facts = self._load_facts(user_id)
        data = facts.get(key)
        if data:
            fact = Fact.from_dict(data)
            fact.access_count += 1
            facts[key] = fact.to_dict()
            self._save_facts(user_id, facts)
            return fact
        return None

    async def search(
        self,
        user_id: str,
        *,
        category: str | None = None,
        query: str | None = None,
        limit: int = 20,
    ) -> list[Fact]:
        facts = self._load_facts(user_id)
        results = []
        for data in facts.values():
            fact = Fact.from_dict(data)
            if category and fact.category != category:
                continue
            if query and query.lower() not in fact.content.lower():
                continue
            results.append(fact)

        # Sort by recency
        results.sort(key=lambda f: f.updated_at, reverse=True)
        return results[:limit]

    async def get_all(self, user_id: str) -> list[Fact]:
        facts = self._load_facts(user_id)
        result = [Fact.from_dict(d) for d in facts.values()]
        result.sort(key=lambda f: f.updated_at, reverse=True)
        return result

    async def delete(self, user_id: str, key: str) -> bool:
        facts = self._load_facts(user_id)
        if key in facts:
            del facts[key]
            self._save_facts(user_id, facts)
            return True
        return False

    async def clear(self, user_id: str) -> int:
        facts = self._load_facts(user_id)
        count = len(facts)
        self._save_facts(user_id, {})
        return count


# ── Factory ──────────────────────────────────────────────


def create_fact_store() -> FactStore:
    """
    Tạo FactStore từ YAML config.
    Config: memory.backend, memory.storage_dir
    """
    try:
        from hagent.bridge.config import load_config
        cfg = load_config()
        memory_cfg = cfg.get("memory", {}) or {}
    except Exception:
        memory_cfg = {}

    backend = memory_cfg.get("backend", "local")
    storage_dir = memory_cfg.get("storage_dir", "./data/memory")

    if backend == "local":
        return LocalFactStore(storage_dir)

    logger.warning("Unknown memory backend '%s', fallback to local.", backend)
    return LocalFactStore(storage_dir)
