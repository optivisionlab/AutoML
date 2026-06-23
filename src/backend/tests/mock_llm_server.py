"""
Mock OpenAI-compatible LLM Server cho CI testing.

Chạy một FastAPI server giả lập OpenAI Chat Completions API.
Trả về response dự đoán được (deterministic) — KHÔNG cần GPU, KHÔNG cần model.

Usage:
    python tests/mock_llm_server.py          # Chạy trên port 11435
    python tests/mock_llm_server.py --port 8000

Hỗ trợ endpoints:
    POST /v1/chat/completions  — Giả lập OpenAI Chat Completions
    GET  /v1/models            — Liệt kê models
    GET  /health               — Health check
"""

from __future__ import annotations

import json
import time
import uuid
import argparse
import re
from typing import Any

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock LLM Server (CI)")


# ── Request/Response schemas ─────────────────────────────


class ChatMessage(BaseModel):
    role: str
    content: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str = "mock-model"
    messages: list[ChatMessage] = []
    temperature: float = 0.0
    max_tokens: int = 1024
    tools: list[dict] | None = None
    tool_choice: str | None = None
    stream: bool = False


# ── Intelligent mock responses ───────────────────────────

# Map từ keyword trong user message → tool call response
_TOOL_CALL_PATTERNS: list[tuple[list[str], dict]] = [
    (
        ["danh sách", "list", "liệt kê", "dataset"],
        {
            "name": "list_datasets",
            "arguments": json.dumps({"user_id": "test_user_123"}),
        },
    ),
    (
        ["thông tin", "info", "chi tiết", "get_dataset"],
        {
            "name": "get_dataset_info",
            "arguments": json.dumps({"dataset_id": "ds_001"}),
        },
    ),
    (
        ["thuật toán", "algorithm", "model", "available", "khả dụng"],
        {
            "name": "get_available_models",
            "arguments": json.dumps({"problem_type": "classification"}),
        },
    ),
    (
        ["train", "huấn luyện", "training", "start"],
        {
            "name": "start_training",
            "arguments": json.dumps({
                "user_id": "test_user_123",
                "dataset_id": "ds_001",
                "problem_type": "classification",
                "target_column": "target",
            }),
        },
    ),
    (
        ["job", "trạng thái", "status"],
        {
            "name": "get_job_info",
            "arguments": json.dumps({"job_id": "job_001"}),
        },
    ),
    (
        ["health", "sức khỏe", "hệ thống", "system"],
        {
            "name": "check_system_health",
            "arguments": json.dumps({}),
        },
    ),
]


def _find_tool_call(user_message: str, tools: list[dict] | None) -> dict | None:
    """Tìm tool call phù hợp dựa trên keyword matching."""
    if not tools:
        return None

    lower = user_message.lower()
    tool_names = {t["function"]["name"] for t in tools if "function" in t}

    for keywords, call in _TOOL_CALL_PATTERNS:
        if call["name"] in tool_names and any(kw in lower for kw in keywords):
            return call

    return None


def _generate_text_response(user_message: str) -> str:
    """Tạo response text đơn giản dựa trên nội dung message."""
    lower = user_message.lower()

    if any(kw in lower for kw in ["xin chào", "hello", "hi", "chào"]):
        return "Xin chào! Tôi là HAgent, trợ lý AI cho HAutoML. Bạn muốn tôi giúp gì?"

    if any(kw in lower for kw in ["dataset", "dữ liệu"]):
        return "Tôi sẽ giúp bạn với datasets. Bạn muốn xem danh sách, thông tin chi tiết, hay upload dataset mới?"

    if any(kw in lower for kw in ["train", "huấn luyện"]):
        return "Tôi sẽ giúp bạn huấn luyện model. Hãy cho tôi biết dataset ID và loại bài toán (classification/regression)."

    return "Tôi là HAgent. Tôi có thể giúp bạn quản lý datasets, huấn luyện models, và theo dõi jobs trên HAutoML."


# ── Endpoints ────────────────────────────────────────────


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    """Giả lập OpenAI Chat Completions API."""
    # Tìm user message cuối cùng
    user_message = ""
    for msg in reversed(req.messages):
        if msg.role == "user" and msg.content:
            user_message = msg.content
            break

    # Kiểm tra xem có nên trả tool call hay text response
    tool_call = _find_tool_call(user_message, req.tools)

    completion_id = f"chatcmpl-mock-{uuid.uuid4().hex[:8]}"
    created = int(time.time())

    if tool_call:
        # Trả tool call response
        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": req.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": f"call_{uuid.uuid4().hex[:8]}",
                                "type": "function",
                                "function": tool_call,
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        }

    # Trả text response
    response_text = _generate_text_response(user_message)
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": len(response_text.split()),
            "total_tokens": 100 + len(response_text.split()),
        },
    }


@app.get("/v1/models")
async def list_models():
    """Liệt kê mock models."""
    return {
        "object": "list",
        "data": [
            {
                "id": "mock-model",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "deerflow-automl-ci",
            }
        ],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "server": "mock-llm", "model": "mock-model"}


# ── Main ─────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock LLM Server for CI")
    parser.add_argument("--port", type=int, default=11435, help="Port to listen on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind")
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
