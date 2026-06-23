"""
DeerFlow-AutoML — SSE Streaming support.

Provides Server-Sent Events streaming for the chat interface,
enabling real-time token-by-token responses and tool execution updates.

Reference: deerflow/docs/STREAMING.md
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


async def sse_stream(
    message: str,
    *,
    user_id: str | None = None,
    user_token: str | None = None,
    world_model: dict[str, Any] | None = None,
    memory_context: str | None = None,
) -> AsyncIterator[str]:
    """
    SSE stream wrapper cho DeerFlow-AutoML agent.

    Yields SSE-formatted strings:
        data: {"type": "token", "content": "..."}\n\n
        data: {"type": "tool_call", "tool": "...", "args": {...}}\n\n
        data: {"type": "tool_result", "tool": "...", "output": "..."}\n\n
        data: {"type": "done", "response": "..."}\n\n

    Usage in FastAPI:
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            sse_stream(message, user_id=uid),
            media_type="text/event-stream",
        )
    """
    from hagent.agent.graph import stream_agent

    try:
        async for event in stream_agent(
            message,
            user_id=user_id,
            user_token=user_token,
            world_model=world_model,
            memory_context=memory_context,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    except Exception as exc:
        logger.exception("SSE streaming error")
        error_event = {
            "type": "error",
            "error": str(exc),
        }
        yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    finally:
        # Send stream-end sentinel
        yield "data: [DONE]\n\n"
