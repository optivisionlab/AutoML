"""
DeerFlow-AutoML — LangGraph StateGraph Definition.

This is the central graph that orchestrates the multi-agent AutoML system.
Phase 1: Single-agent with tool-calling (coordinator only).
Phase 2: Full multi-agent with conditional routing to sub-agents.

"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from langchain_core.messages import ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from hagent.agent.coordinator import coordinator_node
from hagent.agent.state import AutoMLState
from hagent.agent.tools.automl_tools import ALL_TOOLS

logger = logging.getLogger(__name__)


# ── Tool execution node ──────────────────────────────────

tool_node = ToolNode(ALL_TOOLS)


# ── Conditional edge: should we call tools? ──────────────


def should_continue(state: AutoMLState) -> Literal["tools", "end"]:
    """
    Kiểm tra xem coordinator có yêu cầu gọi tool hay không.

    Nếu message cuối có tool_calls → route tới tool node.
    Ngược lại → kết thúc (trả lời cho user).
    """
    messages = state["messages"]
    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"


# ── Graph builder ────────────────────────────────────────


def build_automl_graph() -> StateGraph:
    """
    Xây dựng LangGraph StateGraph cho DeerFlow-AutoML.

    Phase 1 (hiện tại):
        coordinator → [tools] → coordinator → ... → END

    Phase 2 (sắp tới):
        coordinator → route → sub_agent → coordinator → END

    Reference: DeerFlow's StateGraph with conditional edges
    """
    graph = StateGraph(AutoMLState)

    # ── Nodes ────────────────────────────────────────────
    graph.add_node("coordinator", coordinator_node)
    graph.add_node("tools", tool_node)

    # ── Edges ────────────────────────────────────────────

    # Entry point
    graph.set_entry_point("coordinator")

    # Coordinator → tools hoặc END
    graph.add_conditional_edges(
        "coordinator",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        },
    )

    # Tools → quay lại coordinator (để xử lý kết quả)
    graph.add_edge("tools", "coordinator")

    return graph


# ── Compiled graph singleton ─────────────────────────────

_compiled_graph = None


def get_automl_graph():
    """Trả về compiled graph (singleton, thread-safe)."""
    global _compiled_graph
    if _compiled_graph is None:
        graph = build_automl_graph()
        _compiled_graph = graph.compile()
        logger.info("DeerFlow-AutoML graph compiled successfully ✓")
    return _compiled_graph


# ── Convenience runner ───────────────────────────────────


async def run_agent(
    message: str,
    *,
    user_id: str | None = None,
    user_token: str | None = None,
    world_model: dict[str, Any] | None = None,
    memory_context: str | None = None,
) -> dict[str, Any]:
    """
    Chạy agent graph cho một message.

    Args:
        message: Tin nhắn từ người dùng.
        user_id: ID người dùng.
        user_token: JWT token.
        world_model: Snapshot World Model.
        memory_context: Long-term memory đã format.

    Returns:
        Dict với keys: response, tool_outputs, sources
    """
    from langchain_core.messages import HumanMessage

    graph = get_automl_graph()

    # Build initial state
    initial_state: AutoMLState = {
        "messages": [HumanMessage(content=message)],
        "world_model": world_model,
        "memory_context": memory_context,
        "user_id": user_id,
        "user_token": user_token,
    }

    # Inject user context vào environment cho tools
    import os
    if user_token:
        os.environ["USER_TOKEN"] = user_token
    if user_id:
        os.environ["USER_ID"] = user_id

    # Run graph
    final_state = await graph.ainvoke(initial_state)

    # Extract response
    messages = final_state["messages"]
    last_ai_message = None
    tool_outputs = []

    for msg in reversed(messages):
        if hasattr(msg, "content") and not isinstance(msg, ToolMessage):
            if hasattr(msg, "tool_calls"):
                # This is an AI message with possible tool calls
                pass
            if msg.content and not last_ai_message:
                last_ai_message = msg
        if isinstance(msg, ToolMessage):
            tool_outputs.append({
                "tool_name": msg.name,
                "payload": _safe_json_parse(msg.content),
            })

    response_text = last_ai_message.content if last_ai_message else "Không có phản hồi."

    return {
        "response": response_text,
        "tool_outputs": list(reversed(tool_outputs)),
        "sources": [],
        "provider": "deerflow-automl",
        "model": "coordinator",
    }


def _safe_json_parse(text: str) -> Any:
    """Parse JSON an toàn, trả về raw text nếu không parse được."""
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
    """
    Stream agent graph events qua async generator.

    Yields dicts:
        {"type": "token", "content": "..."}
        {"type": "tool_call", "tool": "...", "args": {...}}
        {"type": "tool_result", "tool": "...", "output": "..."}
        {"type": "done", "response": "..."}
    """
    from langchain_core.messages import HumanMessage

    graph = get_automl_graph()

    initial_state: AutoMLState = {
        "messages": [HumanMessage(content=message)],
        "world_model": world_model,
        "memory_context": memory_context,
        "user_id": user_id,
        "user_token": user_token,
    }

    import os
    if user_token:
        os.environ["USER_TOKEN"] = user_token
    if user_id:
        os.environ["USER_ID"] = user_id

    final_content = ""

    async for event in graph.astream_events(initial_state, version="v2"):
        kind = event["event"]

        if kind == "on_chat_model_stream":
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

    yield {"type": "done", "response": final_content}
