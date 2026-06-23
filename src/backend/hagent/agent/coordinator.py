"""
DeerFlow-AutoML — Coordinator (Lead Agent).

The coordinator is the central decision-making node. It receives the user's
message, decides which sub-agent (or itself) should handle the request,
and synthesizes final responses.

Reference: deerflow/agents/lead_agent/agent.py
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import SystemMessage

from hagent.agent.state import AutoMLState

logger = logging.getLogger(__name__)


# ── World Model formatting ───────────────────────────────


def _format_world_model_summary(world_model: dict[str, Any] | None) -> str:
    """Format world model snapshot cho system prompt."""
    if not world_model:
        return "Chưa có dữ liệu World Model."

    datasets = world_model.get("datasets", {})
    jobs = world_model.get("jobs", {})

    lines = []
    if datasets:
        ds_names = [f"- {did}: {d.get('name', '?')}" for did, d in datasets.items()]
        lines.append(f"**Datasets ({len(datasets)}):**\n" + "\n".join(ds_names[:10]))
    else:
        lines.append("**Datasets:** Chưa có")

    if jobs:
        job_summaries = [f"- {jid}: status={j.get('status', '?')}" for jid, j in jobs.items()]
        lines.append(f"**Jobs ({len(jobs)}):**\n" + "\n".join(job_summaries[:10]))
    else:
        lines.append("**Jobs:** Chưa có")

    return "\n".join(lines)


# ── Routing logic (config-driven) ────────────────────────


def keyword_route(message: str) -> str | None:
    """
    Quick keyword-based routing — đọc keywords từ hagent.yaml.

    Returns:
        Tên sub-agent phù hợp nhất, hoặc None nếu không match.
    """
    from hagent.bridge.config import get_routing_config

    routing = get_routing_config()
    if not routing:
        return None

    lower = message.lower()
    scores: dict[str, int] = {}
    for agent_name, keywords in routing.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[agent_name] = score

    if not scores:
        return None
    return max(scores, key=scores.get)


def parse_coordinator_response(response_text: str) -> tuple[str | None, str]:
    """
    Parse coordinator response to extract routing decision.

    Returns:
        (route_target, clean_text)
        route_target is None if coordinator responds directly.
    """
    if response_text.startswith("[ROUTE:"):
        end = response_text.index("]")
        agent_name = response_text[7:end].strip()
        reason = response_text[end + 1:].strip()
        return agent_name, reason
    return None, response_text


# ── System prompt loader ─────────────────────────────────


def _load_system_prompt(world_model: dict[str, Any] | None = None) -> str:
    """
    Load system prompt từ file (cấu hình trong hagent.yaml).
    Inject world model summary vào placeholder {world_model_summary}.
    """
    from hagent.bridge.config import load_prompt_file

    try:
        template = load_prompt_file()  # Đọc từ agent.system_prompt_path
    except FileNotFoundError:
        logger.warning("Không tìm thấy prompt file, dùng fallback minimal.")
        template = (
            "Bạn là HAgent, trợ lý AI cho HAutoML. "
            "Trả lời bằng ngôn ngữ người dùng sử dụng.\n\n"
            "## World Model\n{world_model_summary}"
        )

    return template.format(
        world_model_summary=_format_world_model_summary(world_model),
    )


# ── Coordinator node function ────────────────────────────


async def coordinator_node(state: AutoMLState) -> dict:
    """
    LangGraph node: Coordinator quyết định routing hoặc trả lời trực tiếp.

    Phase 1: Coordinator dùng tools trực tiếp (single-agent mode).
    Phase 2: Thêm LLM-based routing tới sub-agents.
    """
    from hagent.agent.llm_config import create_chat_model
    from hagent.agent.tools.automl_tools import ALL_TOOLS

    messages = state["messages"]
    world_model = state.get("world_model")

    # Load system prompt từ file config
    system_prompt = _load_system_prompt(world_model)

    # Tạo LLM từ config (provider/model đọc từ hagent.yaml)
    llm = create_chat_model()
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    # Inject system prompt + memory context (nếu có)
    prompt_parts = [system_prompt]
    memory_ctx = state.get("memory_context")
    if memory_ctx:
        prompt_parts.append(f"\n## Trí nhớ dài hạn\n{memory_ctx}")

    full_system = "\n".join(prompt_parts)
    full_messages = [SystemMessage(content=full_system)] + list(messages)

    # Gọi LLM
    response = await llm_with_tools.ainvoke(full_messages)

    return {"messages": [response]}
