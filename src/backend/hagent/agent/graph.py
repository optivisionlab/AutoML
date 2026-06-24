"""
DeerFlow-AutoML — LangGraph StateGraph Definition (Phase 2, SOLID).

Dynamic multi-agent graph — đọc YAML config qua AgentRegistry.
KHÔNG hardcode bất kỳ tên agent, module path, hay tool name nào.

Thêm agent mới: chỉ cần thêm entry trong hagent.yaml → graph tự build.

SOLID:
  S — Graph chỉ làm 1 việc: build topology từ registry
  O — Mở rộng qua YAML config, không sửa Python
  D — Inject registry, không import sub-agents trực tiếp
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from hagent.agent.coordinator import coordinator_node
from hagent.agent.registry import get_agent_registry
from hagent.agent.state import AutoMLState

logger = logging.getLogger(__name__)


# ── Routing functions ────────────────────────────────────


def coordinator_route(state: AutoMLState) -> str:
    """
    Coordinator quyết định route tới đâu.

    Ưu tiên:
    1. Nếu coordinator trả về tool_calls → "coordinator_tools"
    2. Nếu state có next_agent hợp lệ → route tới sub-agent đó
    3. Nếu không → END
    """
    messages = state["messages"]
    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "coordinator_tools"

    next_agent = state.get("next_agent")
    registry = get_agent_registry()
    if next_agent and registry.is_valid_agent(next_agent):
        logger.info("Coordinator routing → %s", next_agent)
        return next_agent

    return "end"


def subagent_route(state: AutoMLState) -> str:
    """
    Sau khi sub-agent chạy:
    - Nếu cần tools → "sub_tools"
    - Nếu không → "synthesize"
    """
    messages = state["messages"]
    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "sub_tools"

    return "synthesize"


def after_sub_tools(state: AutoMLState) -> str:
    """Sau khi tool chạy xong, quay lại sub-agent hiện tại."""
    next_agent = state.get("next_agent")
    registry = get_agent_registry()
    if next_agent and registry.is_valid_agent(next_agent):
        return next_agent
    return "synthesize"


# ── Synthesizer node ─────────────────────────────────────


async def synthesizer_node(state: AutoMLState) -> dict:
    """Tổng hợp kết quả từ sub-agent. Reset next_agent."""
    return {
        "next_agent": None,
        "current_phase": state.get("current_phase", "respond"),
    }


# ── Dynamic graph builder ───────────────────────────────


def build_automl_graph() -> StateGraph:
    """
    Xây dựng LangGraph StateGraph từ AgentRegistry.

    Đọc agent.subagents từ YAML → dynamic add nodes + edges.
    KHÔNG hardcode tên agent nào.

    Flow:
        User → coordinator → [route] → sub-agent ↔ tools → synthesize → END
    """
    registry = get_agent_registry()
    agent_names = registry.agent_names()
    all_tools = registry.get_all_tools()

    if not all_tools:
        # Fallback: import ALL_TOOLS nếu registry chưa có tools
        from hagent.agent.tools.automl_tools import ALL_TOOLS
        all_tools = ALL_TOOLS

    # Tool nodes
    tool_node_all = ToolNode(all_tools)

    graph = StateGraph(AutoMLState)

    # ── Fixed nodes ──────────────────────────────────────
    graph.add_node("coordinator", coordinator_node)
    graph.add_node("coordinator_tools", tool_node_all)
    graph.add_node("sub_tools", tool_node_all)
    graph.add_node("synthesize", synthesizer_node)

    # ── Dynamic sub-agent nodes (từ registry) ────────────
    node_functions = registry.get_node_functions()
    for name, node_fn in node_functions.items():
        graph.add_node(name, node_fn)
        logger.debug("Graph node added: %s", name)

    # ── Entry ────────────────────────────────────────────
    graph.set_entry_point("coordinator")

    # ── Coordinator routing (dynamic) ────────────────────
    route_map: dict[str, str] = {
        "coordinator_tools": "coordinator_tools",
        "end": END,
    }
    for name in agent_names:
        route_map[name] = name

    graph.add_conditional_edges("coordinator", coordinator_route, route_map)
    graph.add_edge("coordinator_tools", "coordinator")

    # ── Sub-agent routing (dynamic) ──────────────────────
    for name in agent_names:
        graph.add_conditional_edges(
            name,
            subagent_route,
            {"sub_tools": "sub_tools", "synthesize": "synthesize"},
        )

    # ── Sub tools → quay lại sub-agent (dynamic) ────────
    after_tools_map: dict[str, str] = {"synthesize": "synthesize"}
    for name in agent_names:
        after_tools_map[name] = name

    graph.add_conditional_edges("sub_tools", after_sub_tools, after_tools_map)

    # ── Synthesize → END ─────────────────────────────────
    graph.add_edge("synthesize", END)

    logger.info(
        "Graph built: %d sub-agents [%s]",
        len(agent_names),
        ", ".join(sorted(agent_names)),
    )
    return graph


# ── Compiled graph singleton ─────────────────────────────

_compiled_graph = None


def get_automl_graph():
    """Trả về compiled graph (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        graph = build_automl_graph()
        _compiled_graph = graph.compile()
        logger.info("DeerFlow-AutoML graph compiled ✓")
    return _compiled_graph


def reset_graph():
    """Reset compiled graph — dùng khi config thay đổi hoặc testing."""
    global _compiled_graph
    _compiled_graph = None


# ── Convenience runner ───────────────────────────────────


async def run_agent(
    message: str,
    *,
    user_id: str | None = None,
    user_token: str | None = None,
    world_model: dict[str, Any] | None = None,
    memory_context: str | None = None,
) -> dict[str, Any]:
    """Chạy multi-agent graph cho một message."""
    from langchain_core.messages import HumanMessage

    graph = get_automl_graph()

    initial_state: AutoMLState = {
        "messages": [HumanMessage(content=message)],
        "world_model": world_model,
        "memory_context": memory_context,
        "user_id": user_id,
        "user_token": user_token,
        "next_agent": None,
        "current_phase": None,
    }

    import os
    if user_token:
        os.environ["USER_TOKEN"] = user_token
    if user_id:
        os.environ["USER_ID"] = user_id

    final_state = await graph.ainvoke(initial_state)

    messages = final_state["messages"]
    last_ai_message = None
    tool_outputs = []

    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            tool_outputs.append({
                "tool_name": msg.name,
                "payload": _safe_json_parse(msg.content),
            })
        elif hasattr(msg, "content") and msg.content and not last_ai_message:
            if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                last_ai_message = msg

    response_text = last_ai_message.content if last_ai_message else "Không có phản hồi."

    return {
        "response": response_text,
        "tool_outputs": list(reversed(tool_outputs)),
        "sources": [],
        "provider": "deerflow-automl",
        "model": "multi-agent",
        "route": final_state.get("current_phase", "direct"),
    }


def _safe_json_parse(text: str) -> Any:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


# ── Streaming runner ─────────────────────────────────────


async def stream_agent(
    message: str,
    *,
    user_id: str | None = None,
    user_token: str | None = None,
    world_model: dict[str, Any] | None = None,
    memory_context: str | None = None,
):
    """Stream multi-agent graph events qua async generator."""
    from langchain_core.messages import HumanMessage

    graph = get_automl_graph()
    registry = get_agent_registry()
    valid_names = registry.agent_names()

    initial_state: AutoMLState = {
        "messages": [HumanMessage(content=message)],
        "world_model": world_model,
        "memory_context": memory_context,
        "user_id": user_id,
        "user_token": user_token,
        "next_agent": None,
        "current_phase": None,
    }

    import os
    if user_token:
        os.environ["USER_TOKEN"] = user_token
    if user_id:
        os.environ["USER_ID"] = user_id

    final_content = ""
    current_route = None

    async for event in graph.astream_events(initial_state, version="v2"):
        kind = event["event"]

        if kind == "on_chain_start":
            node_name = event.get("name", "")
            if node_name in valid_names:
                current_route = node_name
                yield {"type": "route", "agent": node_name}

        elif kind == "on_chat_model_stream":
            chunk = event["data"].get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                final_content += chunk.content
                yield {"type": "token", "content": chunk.content}

        elif kind == "on_tool_start":
            yield {
                "type": "tool_call",
                "tool": event.get("name", ""),
                "args": event.get("data", {}).get("input", {}),
            }

        elif kind == "on_tool_end":
            yield {
                "type": "tool_result",
                "tool": event.get("name", ""),
                "output": _safe_json_parse(
                    event.get("data", {}).get("output", "")
                ),
            }

    yield {
        "type": "done",
        "response": final_content,
        "route": current_route or "direct",
    }
