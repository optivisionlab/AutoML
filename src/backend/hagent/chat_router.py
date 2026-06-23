"""
HAgent — Chat Router tích hợp DeerFlow-AutoML

Các endpoint chat mount trực tiếp vào FastAPI app chính (app.py).
Sử dụng LangGraph agent runtime thay vì OpenClaw Gateway.
Hỗ trợ cả synchronous và SSE streaming responses.
Lưu lịch sử chat vào MongoDB database AutoML.
"""

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from pymongo.asynchronous.database import AsyncDatabase
from pydantic import BaseModel, Field

from database.database import get_db
from users.routers import get_current_user
from hagent import chat_store
from hagent.bridge.config import (
    get_hautoml_config,
    get_suggestions,
    get_error_messages,
)

logger = logging.getLogger("hagent.chat_router")

router = APIRouter(prefix="/api/v1/chat", tags=["HAgent Chat"])


# ─── Schemas ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., description="Nội dung tin nhắn")
    conversation_id: str | None = Field(None, description="ID cuộc hội thoại (tạo mới nếu null)")
    context: dict | None = Field(None, description="Ngữ cảnh bổ sung")
    model: str | None = Field(None, description="Tên model LLM (None = dùng default từ config)")


class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    sources: list[str] = []
    suggestions: list[str] = []
    tool_outputs: list[dict] = []
    provider: str = ""
    model: str = ""


class StreamChatRequest(BaseModel):
    message: str = Field(..., description="Nội dung tin nhắn")
    conversation_id: str | None = Field(None, description="ID cuộc hội thoại")
    model: str | None = Field(None, description="Tên model LLM")


class HealthResponse(BaseModel):
    agent_runtime: str
    hautoml_connected: bool
    available_models: list[dict]
    mode: str


# ─── World Model helper ──────────────────────────────────


async def _load_world_model(db: AsyncDatabase, user_id: str) -> dict | None:
    """Load World Model snapshot cho user."""
    try:
        from hagent.world.state_store import WorldStateStore
        store = WorldStateStore(db)
        return await store.get_snapshot(str(user_id))
    except Exception as exc:
        logger.debug("Không load được World Model: %s", exc)
        return None


# ─── Gọi DeerFlow-AutoML Agent ────────────────────────────


async def _call_agent(
    message: str,
    *,
    user_token: str | None = None,
    user_id: str | None = None,
    world_model: dict | None = None,
) -> dict:
    """Gọi LangGraph agent runtime — thay thế OpenClaw Gateway."""
    error_messages = get_error_messages()

    try:
        from hagent.agent.graph import run_agent

        result = await run_agent(
            message,
            user_id=user_id,
            user_token=user_token,
            world_model=world_model,
        )
        return {
            "message": result.get("response", ""),
            "sources": result.get("sources", []),
            "suggestions": [],
            "tool_outputs": result.get("tool_outputs", []),
            "provider": result.get("provider", "deerflow-automl"),
            "model": result.get("model", ""),
        }

    except Exception as exc:
        logger.exception("Agent runtime error")
        # Phân loại lỗi từ config
        err_str = str(exc).lower()
        if "api key" in err_str or "authentication" in err_str or "401" in err_str:
            msg = error_messages.get("llm_auth", str(exc))
        elif "rate limit" in err_str or "429" in err_str:
            msg = error_messages.get("llm_rate_limit", str(exc))
        elif "timeout" in err_str:
            msg = error_messages.get("timeout", str(exc))
        else:
            msg = error_messages.get("generic", str(exc))

        return {
            "message": f"⚠️ {msg}",
            "sources": [],
            "suggestions": ["Thử lại sau", "Kiểm tra trạng thái hệ thống"],
            "tool_outputs": [],
            "provider": "error",
            "model": "",
        }


# ─── Endpoints ───────────────────────────────────────────


@router.post("/", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    request: Request,
    db: AsyncDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Endpoint chat chính — gọi LangGraph agent, lưu hội thoại vào database."""
    user_id = current_user["_id"]
    conversation_id = req.conversation_id or uuid.uuid4().hex

    # Lấy token từ header
    auth_header = request.headers.get("Authorization", "")
    user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

    # Lưu tin nhắn người dùng
    await chat_store.add_message(db, conversation_id, user_id, "user", req.message)

    # Load World Model
    world_model = await _load_world_model(db, str(user_id))

    # Gọi DeerFlow-AutoML Agent
    result = await _call_agent(
        message=req.message,
        user_token=user_token,
        user_id=str(user_id),
        world_model=world_model,
    )

    # Lưu phản hồi trợ lý
    await chat_store.add_message(db, conversation_id, user_id, "assistant", result["message"])

    return ChatResponse(
        message=result["message"],
        conversation_id=conversation_id,
        sources=result.get("sources", []),
        suggestions=result.get("suggestions", []),
        tool_outputs=result.get("tool_outputs", []),
        provider=result.get("provider", ""),
        model=result.get("model", ""),
    )


@router.post("/stream")
async def chat_stream(
    req: StreamChatRequest,
    request: Request,
    db: AsyncDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    SSE streaming endpoint — trả về real-time token-by-token.

    Response format: Server-Sent Events (text/event-stream)
    Events:
        data: {"type": "token", "content": "..."}
        data: {"type": "tool_call", "tool": "...", "args": {...}}
        data: {"type": "tool_result", "tool": "...", "output": "..."}
        data: {"type": "done", "response": "..."}
        data: [DONE]
    """
    user_id = current_user["_id"]
    conversation_id = req.conversation_id or uuid.uuid4().hex

    auth_header = request.headers.get("Authorization", "")
    user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

    # Lưu tin nhắn người dùng
    await chat_store.add_message(db, conversation_id, user_id, "user", req.message)

    # Load World Model
    world_model = await _load_world_model(db, str(user_id))

    from hagent.agent.streaming import sse_stream

    async def _stream_wrapper():
        """Wrap SSE stream và lưu response cuối cùng vào DB."""
        full_response = ""
        async for chunk in sse_stream(
            req.message,
            user_id=str(user_id),
            user_token=user_token,
            world_model=world_model,
        ):
            yield chunk
            # Thu thập response để lưu DB
            if '"type": "done"' in chunk:
                import json
                try:
                    data = json.loads(chunk.replace("data: ", "").strip())
                    full_response = data.get("response", "")
                except (json.JSONDecodeError, ValueError):
                    pass

        # Lưu phản hồi hoàn chỉnh
        if full_response:
            await chat_store.add_message(
                db, conversation_id, user_id, "assistant", full_response,
            )

    return StreamingResponse(
        _stream_wrapper(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Conversation-Id": conversation_id,
        },
    )


@router.post("/upload", response_model=ChatResponse)
async def chat_with_file(
    request: Request,
    message: str = Form(...),
    file: UploadFile = File(...),
    conversation_id: str | None = Form(None),
    db: AsyncDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Chat kèm upload file."""
    user_id = current_user["_id"]
    conv_id = conversation_id or uuid.uuid4().hex
    hautoml_cfg = get_hautoml_config()

    auth_header = request.headers.get("Authorization", "")
    user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

    import httpx
    file_info = ""
    try:
        file_content = await file.read()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{hautoml_cfg['base_url']}/upload_files",
                files={"files": (file.filename, file_content, file.content_type)},
            )
            if resp.status_code == 200:
                file_info = f"\n[File đã upload: {file.filename} — {len(file_content)} bytes]"
            else:
                file_info = f"\n[Upload file thất bại: {resp.status_code}]"
    except Exception as e:
        file_info = f"\n[Lỗi upload file: {e}]"

    full_message = f"{message}{file_info}"
    await chat_store.add_message(db, conv_id, user_id, "user", full_message)

    world_model = await _load_world_model(db, str(user_id))

    result = await _call_agent(
        message=full_message,
        user_token=user_token,
        user_id=str(user_id),
        world_model=world_model,
    )

    await chat_store.add_message(db, conv_id, user_id, "assistant", result["message"])

    return ChatResponse(
        message=result["message"],
        conversation_id=conv_id,
        sources=result.get("sources", []),
        suggestions=result.get("suggestions", []),
        tool_outputs=result.get("tool_outputs", []),
        provider=result.get("provider", ""),
        model=result.get("model", ""),
    )


@router.get("/health")
async def health_check():
    """Kiểm tra kết nối — DeerFlow-AutoML agent + HAutoML backend."""
    import httpx
    hautoml_cfg = get_hautoml_config()

    hautoml_ok = False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{hautoml_cfg['base_url']}/home")
            hautoml_ok = resp.status_code == 200
    except Exception:
        pass

    # Liệt kê LLM models từ config
    from hagent.agent.llm_config import list_available_models
    models = list_available_models()

    return {
        "agent_runtime": "deerflow-automl (LangGraph)",
        "hautoml_connected": hautoml_ok,
        "available_models": models,
        "mode": "multi-agent",
    }


@router.get("/suggestions")
async def get_chat_suggestions():
    """Gợi ý chat ban đầu — đọc từ config."""
    suggestions = get_suggestions()
    return {"suggestions": suggestions}


@router.get("/models")
async def list_llm_models():
    """Liệt kê các LLM models khả dụng."""
    from hagent.agent.llm_config import list_available_models
    return {"models": list_available_models()}


@router.delete("/conversation/{conversation_id}")
async def clear_conversation(
    conversation_id: str,
    db: AsyncDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Xóa cuộc hội thoại."""
    deleted = await chat_store.delete_conversation(db, conversation_id, current_user["_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc hội thoại")
    return {"status": "deleted", "conversation_id": conversation_id}


@router.get("/conversations")
async def list_user_conversations(
    db: AsyncDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Liệt kê các cuộc hội thoại gần nhất của người dùng."""
    conversations = await chat_store.list_conversations(db, current_user["_id"])
    return {"conversations": conversations}


@router.get("/conversation/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    db: AsyncDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Lấy toàn bộ tin nhắn của một cuộc hội thoại."""
    messages = await chat_store.get_message_history(db, conversation_id, current_user["_id"], limit=200)
    return {
        "conversation_id": conversation_id,
        "messages": [
            {
                "role": m["role"],
                "content": m["content"],
                "timestamp": m.get("timestamp", ""),
            }
            for m in messages
        ],
    }
