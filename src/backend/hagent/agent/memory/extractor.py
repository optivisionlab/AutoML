"""
DeerFlow-AutoML — Fact Extractor (Phase 3).

Rút trích facts từ tool outputs và AI responses.
Rule-based extraction — không cần LLM call thêm.

SOLID:
  S — Chỉ làm extraction, không lưu trữ
  O — Thêm extraction rule qua YAML config
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from hagent.agent.memory import Fact

logger = logging.getLogger(__name__)


# ── Extraction rules (config-driven categories) ─────────


def extract_from_tool_output(
    tool_name: str,
    payload: dict[str, Any],
    source: str = "",
) -> list[Fact]:
    """
    Rút trích facts từ tool output.

    Mỗi tool type → extraction logic riêng.
    Returns danh sách Facts.
    """
    facts: list[Fact] = []

    if tool_name == "list_datasets" and "datasets" in payload:
        ds_list = payload["datasets"]
        facts.append(Fact(
            key="known_datasets",
            content=f"User có {len(ds_list)} datasets: {', '.join(d.get('name', d.get('id', '?')) for d in ds_list[:10])}",
            category="dataset",
            source=source,
        ))

    elif tool_name == "get_dataset_info" and "id" in payload:
        ds_id = payload.get("id", "")
        ds_name = payload.get("name", ds_id)
        n_rows = payload.get("n_rows", "?")
        n_cols = payload.get("n_cols", "?")
        problem = payload.get("problem_type", "unknown")
        target = payload.get("target", "?")
        facts.append(Fact(
            key=f"dataset_{ds_id}",
            content=(
                f"Dataset '{ds_name}': {n_rows} rows × {n_cols} cols, "
                f"problem_type={problem}, target='{target}'"
            ),
            category="dataset",
            source=source,
        ))

    elif tool_name == "start_training" and "job_id" in payload:
        job_id = payload["job_id"]
        ds_id = payload.get("dataset_id", "?")
        facts.append(Fact(
            key=f"training_{job_id}",
            content=f"Started training job '{job_id}' on dataset '{ds_id}'",
            category="workflow",
            source=source,
        ))

    elif tool_name == "get_job_info":
        job_id = payload.get("id", payload.get("job_id", ""))
        status = payload.get("status", "unknown")
        best = payload.get("best_model")
        score = payload.get("best_score")
        content = f"Job '{job_id}': status={status}"
        if best:
            content += f", best_model={best}"
        if score:
            content += f", score={score}"
        facts.append(Fact(
            key=f"job_{job_id}",
            content=content,
            category="model" if best else "workflow",
            source=source,
        ))

    elif tool_name == "get_available_models" and "models" in payload:
        models = payload["models"]
        facts.append(Fact(
            key="available_models",
            content=f"Available ML models: {', '.join(str(m) for m in models[:20])}",
            category="model",
            source=source,
        ))

    return facts


def extract_from_response(
    response_text: str,
    source: str = "",
) -> list[Fact]:
    """
    Rút trích facts từ AI response text.
    Dùng pattern matching cho preferences và decisions.
    """
    facts: list[Fact] = []

    # Pattern: user preferences detected in response
    preference_patterns = [
        (r"(?:đề xuất|recommend|suggest)\s+(\w+)", "preference"),
        (r"model tốt nhất.*?(?:là|is)\s+(\w+)", "model"),
        (r"accuracy.*?(\d+\.?\d*%?)", "model"),
    ]

    for pattern, category in preference_patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            facts.append(Fact(
                key=f"response_{category}_{hash(match.group(0)) % 10000}",
                content=match.group(0),
                category=category,
                confidence=0.7,
                source=source,
            ))

    return facts


def extract_from_tool_message(msg: Any, source: str = "") -> list[Fact]:
    """Helper: extract facts từ LangChain ToolMessage."""
    if not hasattr(msg, "name") or not hasattr(msg, "content"):
        return []

    try:
        payload = (
            json.loads(msg.content)
            if isinstance(msg.content, str)
            else msg.content
        )
        if isinstance(payload, dict) and "error" not in payload:
            return extract_from_tool_output(msg.name, payload, source=source)
    except (json.JSONDecodeError, TypeError):
        pass

    return []
