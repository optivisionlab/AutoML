"""
AutoML Agent State — Tham chiếu từ DeerFlow's ThreadState.

Defines the state schema for the LangGraph StateGraph, carrying
messages, AutoML-specific context, World Model snapshot, and memory.

Reference: deerflow/agents/thread_state.py
"""

from __future__ import annotations

from typing import Annotated, Any, NotRequired, TypedDict

from langgraph.graph.message import add_messages


# ── Sub-state fragments (kiểu DeerFlow) ─────────────────


class DatasetContext(TypedDict, total=False):
    """Ngữ cảnh dataset đang được thao tác."""
    id: str
    name: str
    n_rows: int
    n_cols: int
    features: list[str]
    target: str | None
    problem_type: str | None  # classification | regression


class JobContext(TypedDict, total=False):
    """Ngữ cảnh training job."""
    id: str
    dataset_id: str
    status: str  # pending | running | completed | failed
    models: list[str]
    best_model: str | None
    best_score: float | None
    metrics: dict[str, float]


class EvaluationResult(TypedDict, total=False):
    """Kết quả đánh giá và so sánh models."""
    job_ids: list[str]
    comparison_table: list[dict[str, Any]]
    best_job_id: str | None
    recommendation: str | None


# ── Main state ───────────────────────────────────────────


class AutoMLState(TypedDict):
    """
    State cho LangGraph StateGraph — Tham chiếu DeerFlow's ThreadState.

    messages: LangGraph message list with auto-merge reducer.
    Các trường còn lại là AutoML-specific context được cập nhật
    bởi các sub-agent nodes.
    """

    # ── Core LangGraph messages ──────────────────────────
    messages: Annotated[list, add_messages]

    # ── Routing / orchestration ──────────────────────────
    next_agent: NotRequired[str | None]
    """Agent node tiếp theo do coordinator quyết định."""

    current_phase: NotRequired[str | None]
    """Phase hiện tại: analyze | select | train | evaluate | respond."""

    # ── AutoML-specific context ──────────────────────────
    dataset_context: NotRequired[DatasetContext | None]
    """Dataset đang được thao tác."""

    job_context: NotRequired[JobContext | None]
    """Training job đang chạy hoặc vừa hoàn thành."""

    active_jobs: NotRequired[list[JobContext] | None]
    """Nhiều jobs chạy song song (khi so sánh models)."""

    evaluation: NotRequired[EvaluationResult | None]
    """Kết quả đánh giá cuối cùng."""

    # ── World Model snapshot ─────────────────────────────
    world_model: NotRequired[dict | None]
    """Snapshot từ WorldStateStore — tất cả datasets + jobs đã biết."""

    # ── Memory context (DeerFlow memory module) ──────────
    memory_context: NotRequired[str | None]
    """Long-term memory đã inject vào prompt."""

    # ── User context ─────────────────────────────────────
    user_id: NotRequired[str | None]
    user_token: NotRequired[str | None]
