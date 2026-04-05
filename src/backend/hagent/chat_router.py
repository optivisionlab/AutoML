"""
HAgent — Chat Router tích hợp vào backend chính

Các endpoint chat được mount trực tiếp vào FastAPI app chính (app.py).
Hệ thống CHỈ sử dụng HAgent Gateway — không có multi-provider.
Lưu lịch sử chat vào MongoDB database AutoML.
"""

import uuid
import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from pymongo.asynchronous.database import AsyncDatabase
from pydantic import BaseModel, Field

from database.database import get_db
from users.routers import get_current_user
from hagent import chat_store
from hagent.bridge.config import (
    get_hooks_config,
    get_hautoml_config,
    get_gateway_config,
)

logger = logging.getLogger("hagent.chat_router")

router = APIRouter(prefix="/api/v1/chat", tags=["HAgent Chat"])


# ─── Schemas ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., description="Nội dung tin nhắn")
    conversation_id: str | None = Field(None, description="ID cuộc hội thoại (tạo mới nếu null)")
    context: dict | None = Field(None, description="Ngữ cảnh bổ sung")


class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    sources: list[str] = []
    suggestions: list[str] = []


class HealthResponse(BaseModel):
    hagent_url: str
    connected: bool
    hautoml_connected: bool
    mode: str


# ─── Gọi HAgent Gateway ───────────────────────────────

SYSTEM_PROMPT = (
    "Bạn là HAgent, trợ lý AI cho nền tảng HAutoML. "
    "Trả lời bằng ngôn ngữ mà người dùng sử dụng."
)


async def _call_hagent_gateway(
    message: str,
    history: list[dict] | None = None,
    user_token: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Gửi tin nhắn tới HAgent Gateway."""
    hooks_cfg = get_hooks_config()
    hautoml_cfg = get_hautoml_config()
    gw_cfg = get_gateway_config()
    gateway_url = os.getenv("HAGENT_GATEWAY_URL", f"http://{gw_cfg['host']}:{gw_cfg['port']}")

    payload = {
        "message": message,
        "context": {
            "user_token": user_token or "",
            "user_id": user_id or "",
            "hautoml_url": hautoml_cfg["base_url"],
        },
    }
    if history:
        payload["history"] = history

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{gateway_url}{hooks_cfg.get('path', '/hooks')}/agent",
                json=payload,
                headers={
                    "Authorization": f"Bearer {hooks_cfg.get('token', '')}",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "message": data.get("response", data.get("message", "")),
                    "sources": data.get("sources", []),
                    "suggestions": data.get("suggestions", []),
                }
            logger.warning("Gateway trả về %d: %s", resp.status_code, resp.text)
    except httpx.ConnectError:
        logger.warning("Không kết nối được HAgent Gateway tại %s", gateway_url)
    except Exception as e:
        logger.error("Lỗi khi gọi Gateway: %s", e)

    return {
        "message": "⚠️ Không thể kết nối tới HAgent Gateway. Vui lòng kiểm tra hệ thống.",
        "sources": [],
        "suggestions": ["Thử lại sau", "Kiểm tra trạng thái hệ thống"],
    }


# ─── Endpoints ───────────────────────────────────────────


@router.post("/", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    request: Request,
    db: AsyncDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Endpoint chat chính — gọi HAgent Gateway, lưu hội thoại vào database."""
    user_id = current_user["_id"]
    conversation_id = req.conversation_id or uuid.uuid4().hex

    # Lấy token từ header
    auth_header = request.headers.get("Authorization", "")
    user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

    # Lưu tin nhắn người dùng
    await chat_store.add_message(db, conversation_id, user_id, "user", req.message)

    # Lấy lịch sử hội thoại
    history = await chat_store.get_message_history(db, conversation_id, user_id, limit=20)
    history_dicts = [{"role": m["role"], "content": m["content"]} for m in history[:-1]]

    # Gọi HAgent Gateway
    result = await _call_hagent_gateway(
        message=req.message,
        history=history_dicts if history_dicts else None,
        user_token=user_token,
        user_id=str(user_id),
    )

    # Lưu phản hồi trợ lý
    await chat_store.add_message(db, conversation_id, user_id, "assistant", result["message"])

    return ChatResponse(
        message=result["message"],
        conversation_id=conversation_id,
        sources=result.get("sources", []),
        suggestions=result.get("suggestions", []),
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

    history = await chat_store.get_message_history(db, conv_id, user_id, limit=20)
    history_dicts = [{"role": m["role"], "content": m["content"]} for m in history[:-1]]

    result = await _call_hagent_gateway(
        message=full_message,
        history=history_dicts if history_dicts else None,
        user_token=user_token,
        user_id=str(user_id),
    )

    await chat_store.add_message(db, conv_id, user_id, "assistant", result["message"])

    return ChatResponse(
        message=result["message"],
        conversation_id=conv_id,
        sources=result.get("sources", []),
        suggestions=result.get("suggestions", []),
    )


@router.get("/health")
async def health_check():
    """Kiểm tra kết nối tới HAgent Gateway."""
    gw_cfg = get_gateway_config()
    gateway_url = os.getenv("HAGENT_GATEWAY_URL", f"http://{gw_cfg['host']}:{gw_cfg['port']}")
    hautoml_cfg = get_hautoml_config()

    hagent_ok = False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{gateway_url}/health")
            hagent_ok = resp.status_code == 200
    except Exception:
        pass

    hautoml_ok = False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{hautoml_cfg['base_url']}/home")
            hautoml_ok = resp.status_code == 200
    except Exception:
        pass

    return {
        "hagent_url": gateway_url,
        "connected": hagent_ok,
        "hautoml_connected": hautoml_ok,
        "mode": "hagent",
    }


@router.get("/suggestions")
async def get_suggestions():
    """Gợi ý chat ban đầu."""
    return {
        "suggestions": [
            "📊 Hiển thị danh sách dataset của tôi",
            "🚀 Huấn luyện model phân loại mới",
            "📈 Có những thuật toán ML nào khả dụng?",
            "🔍 Kiểm tra trạng thái các job training",
            "💡 Giúp tôi chọn model phù hợp",
        ]
    }


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
