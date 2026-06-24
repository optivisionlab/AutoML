"""
DeerFlow-AutoML — Coordinator (Lead Agent) — Phase 2, SOLID.

Coordinator quyết định routing hoặc trả lời trực tiếp.
Tất cả agent names đọc từ AgentRegistry (YAML config).
KHÔNG hardcode bất kỳ tên agent nào.

SOLID:
  S — Coordinator chỉ làm routing + trả lời
  O — Thêm agent mới chỉ cần YAML, không sửa coordinator
  D — Inject registry, không import sub-agents trực tiếp
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

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


def _get_valid_agents() -> set[str]:
    """Lấy danh sách agent names từ AgentRegistry (đọc YAML)."""
    from hagent.agent.registry import get_agent_registry
    return get_agent_registry().agent_names()


def keyword_route(message: str) -> str | None:
    """
    Quick keyword-based routing — đọc keywords từ hagent.yaml.
    Agent names cũng từ YAML, không hardcode.
    """
    from hagent.bridge.config import get_routing_config

    routing = get_routing_config()
    if not routing:
        return None

    valid_agents = _get_valid_agents()
    lower = message.lower()
    scores: dict[str, int] = {}

    for agent_name, agent_cfg in routing.items():
        # Chỉ route tới agents đã đăng ký trong registry
        if agent_name not in valid_agents:
            continue
        keywords = agent_cfg if isinstance(agent_cfg, list) else agent_cfg.get("keywords", [])
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[agent_name] = score

    if not scores:
        return None
    return max(scores, key=scores.get)


def parse_coordinator_response(response_text: str) -> tuple[str | None, str]:
    """
    Parse coordinator response to extract routing decision.
    Format: [ROUTE:agent_name] reason text
    Validates agent_name against registry.
    """
    match = re.match(r"\[ROUTE:(\w+)\]\s*(.*)", response_text, re.DOTALL)
    if match:
        agent_name = match.group(1).strip()
        reason = match.group(2).strip()
        valid_agents = _get_valid_agents()
        if agent_name in valid_agents:
            return agent_name, reason
    return None, response_text


# ── Dynamic routing instruction builder ──────────────────


def _build_routing_instruction() -> str:
    """
    Build routing instruction cho system prompt.
    Đọc agent names + descriptions từ YAML — KHÔNG hardcode.
    """
    from hagent.bridge.config import get_routing_config

    valid_agents = _get_valid_agents()
    routing = get_routing_config()

    lines = [
        "\n## Routing Protocol",
        "Bạn là Lead Agent (Coordinator). Dựa trên yêu cầu, quyết định route tới sub-agent phù hợp:\n",
    ]

    for agent_name in sorted(valid_agents):
        # Lấy keywords làm mô tả ngắn
        keywords = routing.get(agent_name, {})
        if isinstance(keywords, dict):
            keywords = keywords.get("keywords", [])
        kw_preview = ", ".join(keywords[:5]) if keywords else "N/A"
        lines.append(f"- **{agent_name}**: Khi yêu cầu liên quan tới: {kw_preview}")

    lines.extend([
        "\n### Cách route:",
        "- Nếu cần chuyển cho sub-agent: bắt đầu response bằng `[ROUTE:agent_name]` rồi giải thích ngắn.",
        "- Nếu trả lời trực tiếp (chào hỏi, câu hỏi chung): KHÔNG dùng [ROUTE:], trả lời bình thường.",
        "- Nếu cần dùng tools: gọi tools trực tiếp (không cần route).",
    ])

    return "\n".join(lines)


# ── System prompt loader ─────────────────────────────────


def _load_system_prompt(world_model: dict[str, Any] | None = None) -> str:
    """
    Load system prompt từ file (cấu hình trong hagent.yaml).
    Inject world model summary + routing instructions (dynamic).
    """
    from hagent.bridge.config import load_prompt_file

    try:
        template = load_prompt_file()
    except FileNotFoundError:
        logger.warning("Không tìm thấy prompt file, dùng fallback minimal.")
        template = (
            "Bạn là HAgent, trợ lý AI cho HAutoML. "
            "Trả lời bằng ngôn ngữ người dùng sử dụng.\n\n"
            "## World Model\n{world_model_summary}"
        )

    base_prompt = template.format(
        world_model_summary=_format_world_model_summary(world_model),
    )

    # Routing instruction build dynamic từ YAML
    routing_instruction = _build_routing_instruction()
    return base_prompt + "\n" + routing_instruction


# ── Coordinator node function ────────────────────────────


async def coordinator_node(state: AutoMLState) -> dict:
    """
    LangGraph node: Coordinator quyết định routing hoặc trả lời trực tiếp.

    Routing strategy (2 tầng):
    1. Quick keyword route từ YAML config
    2. LLM-based routing: LLM response chứa [ROUTE:X]
    """
    from hagent.agent.llm_config import create_chat_model
    from hagent.agent.tools.automl_tools import ALL_TOOLS

    messages = state["messages"]
    world_model = state.get("world_model")

    # ── Bước 1: Quick keyword route ──────────────────────
    last_user_msg = ""
    for msg in reversed(messages):
        if hasattr(msg, "content") and getattr(msg, "type", "") == "human":
            last_user_msg = msg.content or ""
            break

    quick_route = keyword_route(last_user_msg)
    valid_agents = _get_valid_agents()

    if quick_route and quick_route in valid_agents:
        logger.info("Quick route → %s (keyword match)", quick_route)
        route_msg = AIMessage(
            content=f"[ROUTE:{quick_route}] Chuyển yêu cầu tới {quick_route}."
        )
        return {
            "messages": [route_msg],
            "next_agent": quick_route,
        }

    # ── Bước 2: LLM-based routing ────────────────────────
    system_prompt = _load_system_prompt(world_model)

    llm = create_chat_model()
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    prompt_parts = [system_prompt]
    memory_ctx = state.get("memory_context")
    if memory_ctx:
        prompt_parts.append(f"\n## Trí nhớ dài hạn\n{memory_ctx}")

    full_system = "\n".join(prompt_parts)
    full_messages = [SystemMessage(content=full_system)] + list(messages)

    response = await llm_with_tools.ainvoke(full_messages)

    # ── Bước 3: Parse routing decision ───────────────────
    state_update: dict[str, Any] = {"messages": [response]}

    if response.content and not (hasattr(response, "tool_calls") and response.tool_calls):
        route_target, _ = parse_coordinator_response(response.content)
        if route_target:
            state_update["next_agent"] = route_target
            logger.info("LLM route → %s", route_target)
        else:
            state_update["next_agent"] = None

    return state_update
