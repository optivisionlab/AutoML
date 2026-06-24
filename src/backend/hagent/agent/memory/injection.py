"""
DeerFlow-AutoML — Memory Injection (Phase 3).

Load relevant facts và format thành context string
để inject vào system prompt.

SOLID:
  S — Chỉ làm injection/formatting
  D — FactStore inject qua parameter
"""

from __future__ import annotations

import logging
from typing import Any

from hagent.agent.memory import Fact, FactStore

logger = logging.getLogger(__name__)


async def load_memory_context(
    store: FactStore,
    user_id: str,
    *,
    query: str | None = None,
    categories: list[str] | None = None,
    max_facts: int = 15,
) -> str:
    """
    Load và format memory context cho system prompt injection.

    Args:
        store: FactStore instance
        user_id: User identifier
        query: Optional relevance query
        categories: Optional category filter
        max_facts: Maximum facts to include

    Returns:
        Formatted markdown string cho prompt injection.
    """
    if not user_id:
        return ""

    all_facts: list[Fact] = []

    if categories:
        for cat in categories:
            facts = await store.search(user_id, category=cat, limit=max_facts)
            all_facts.extend(facts)
    elif query:
        all_facts = await store.search(user_id, query=query, limit=max_facts)
    else:
        all_facts = await store.get_all(user_id)

    if not all_facts:
        return ""

    # Deduplicate by key
    seen = set()
    unique_facts = []
    for f in all_facts:
        if f.key not in seen:
            seen.add(f.key)
            unique_facts.append(f)

    # Limit
    unique_facts = unique_facts[:max_facts]

    # Format
    return _format_facts(unique_facts)


def _format_facts(facts: list[Fact]) -> str:
    """Format facts thành markdown cho prompt injection."""
    if not facts:
        return ""

    # Group by category
    by_category: dict[str, list[Fact]] = {}
    for f in facts:
        by_category.setdefault(f.category, []).append(f)

    lines = ["## Trí nhớ dài hạn (Long-term Memory)"]
    lines.append(f"*{len(facts)} facts đã ghi nhận:*\n")

    category_labels = {
        "dataset": "📊 Datasets",
        "model": "🤖 Models",
        "workflow": "🔄 Workflow",
        "preference": "⚙️ Preferences",
        "general": "📝 General",
    }

    for category, cat_facts in by_category.items():
        label = category_labels.get(category, f"📌 {category.title()}")
        lines.append(f"### {label}")
        for f in cat_facts[:5]:
            conf_marker = "" if f.confidence >= 0.8 else " *(low confidence)*"
            lines.append(f"- {f.content}{conf_marker}")
        lines.append("")

    return "\n".join(lines)


async def inject_memory_into_state(
    store: FactStore,
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Middleware helper: load memory và inject vào state.

    Đọc user_id từ state, load facts, set memory_context.
    """
    user_id = state.get("user_id")
    if not user_id:
        return state

    # Extract query hint từ last message
    query = None
    messages = state.get("messages", [])
    if messages:
        last_msg = messages[-1]
        if hasattr(last_msg, "content") and last_msg.content:
            query = last_msg.content[:200]

    memory_text = await load_memory_context(
        store, user_id, query=query,
    )

    if memory_text:
        state["memory_context"] = memory_text
        logger.debug("Injected %d chars of memory for user '%s'", len(memory_text), user_id)

    return state
