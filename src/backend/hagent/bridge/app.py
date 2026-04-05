"""
HAgent Bridge — Ứng dụng FastAPI chính

Lớp trung gian giữa frontend ChatWidget và HAgent Gateway.
Tất cả cấu hình được tải từ hagent.yaml — KHÔNG có hard-code.

Xử lý:
  - Xác thực JWT
  - Lưu trữ cuộc hội thoại (MongoDB)
  - Điều phối provider/model (tải từ YAML)
  - Chuyển tiếp upload file
"""

import uuid
import logging
import asyncio
import os
import re
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request, Response
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

from .config import (
    get_bridge_config,
    get_hautoml_config,
    get_hooks_config,
    get_mongodb_config,
)
from .models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    SuggestionsResponse,
    ProviderInfo,
    ProvidersResponse,
)
from .auth import TokenPayload, get_current_user, get_optional_user
from . import conversation as conv_store

logger = logging.getLogger("hagent.bridge")

UUID_PATTERN = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
JOB_ID_LINE_RE = re.compile(rf"Job\s*ID\s*[:\-]\s*`?({UUID_PATTERN})`?", re.IGNORECASE)
GENERIC_UUID_RE = re.compile(rf"\b({UUID_PATTERN})\b")
TRAINING_STARTED_RE = re.compile(
    r"training\s+started|training\s+job\s+initiated|bắt\s+đầu\s+huấn\s+luyện|huấn\s+luyện\s+đã\s+bắt\s+đầu",
    re.IGNORECASE,
)
TRAINING_POLL_INTERVAL_SECONDS = float(os.getenv("HAGENT_TRAINING_POLL_INTERVAL_SECONDS", "10"))
TRAINING_POLL_TIMEOUT_SECONDS = int(os.getenv("HAGENT_TRAINING_POLL_TIMEOUT_SECONDS", "7200"))
_training_watch_tasks: dict[str, asyncio.Task] = {}


# ─── Vòng đời ứng dụng ──────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý startup/shutdown."""
    mongo_cfg = get_mongodb_config()
    bridge_cfg = get_bridge_config()

    # Kết nối MongoDB
    logger.info("Đang kết nối MongoDB tại %s ...", mongo_cfg["connect"])
    await conv_store.init_db()
    logger.info("Kết nối MongoDB thành công ✓")

    logger.info(
        "HAgent Bridge khởi chạy trên port %d — Chỉ dùng HAgent Gateway",
        bridge_cfg["port"]
    )

    yield

    if _training_watch_tasks:
        for task in list(_training_watch_tasks.values()):
            if not task.done():
                task.cancel()
        await asyncio.gather(*list(_training_watch_tasks.values()), return_exceptions=True)
        _training_watch_tasks.clear()

    await conv_store.close_db()
    logger.info("HAgent Bridge đã dừng.")


# ─── Khởi tạo ứng dụng ──────────────────────────────────


hagent_bridge = FastAPI(
    title="HAgent Bridge",
    description="Lớp trung gian giữa frontend ChatWidget và HAgent Gateway — Đa provider LLM, cấu hình từ YAML",
    version="2.0.0",
    lifespan=lifespan,
)

# Cấu hình CORS từ YAML
_bridge_cfg = get_bridge_config()
hagent_bridge.add_middleware(
    CORSMiddleware,
    allow_origins=_bridge_cfg.get("cors_origins", ["http://localhost:3000"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Hàm gọi LLM ───────────────────────────────────────


async def _call_hagent_gateway(
    message: str,
    history: list[dict] | None = None,
    user_token: str | None = None,
    user_id: str | None = None,
) -> dict:
    """
    Gửi tin nhắn tới HAgent Gateway qua webhook API.
    """
    hooks_cfg = get_hooks_config()
    hautoml_cfg = get_hautoml_config()
    from .config import get_gateway_config
    gw_cfg = get_gateway_config()
    gateway_url = f"http://{gw_cfg['host']}:{gw_cfg['port']}"
    import os
    gateway_url = os.getenv("HAGENT_GATEWAY_URL", gateway_url)

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
                    "provider": "hagent",
                    "model": "hagent-agent",
                }
            logger.warning("Gateway trả về %d: %s", resp.status_code, resp.text)
            return _error_response(f"Lỗi HAgent Gateway (HTTP {resp.status_code})")

    except httpx.ConnectError:
        logger.warning("Không kết nối được Gateway tại %s", gateway_url)
        return _error_response(f"Mất kết nối tới HAgent Gateway tại {gateway_url}")
    except Exception as e:
        logger.error("Lỗi khi gọi Gateway: %s", e)
        return _error_response(f"Lỗi truy vấn HAgent Gateway: {str(e)}")


def _error_response(msg: str) -> dict:
    """Tạo phản hồi lỗi chuẩn."""
    return {
        "message": f"⚠️ {msg}",
        "sources": [],
        "suggestions": ["Thử lại sau"],
        "provider": "hagent",
        "model": "hagent-agent",
    }


def _extract_training_job_id(message: str) -> str | None:
    """Chỉ lấy job_id khi nội dung cho thấy vừa submit training."""
    if not message:
        return None

    tagged_match = JOB_ID_LINE_RE.search(message)
    if tagged_match:
        return tagged_match.group(1)

    if not TRAINING_STARTED_RE.search(message):
        return None

    generic_match = GENERIC_UUID_RE.search(message)
    return generic_match.group(1) if generic_match else None


def _format_score(score) -> str:
    if score is None:
        return "N/A"

    if isinstance(score, (int, float)):
        if 0 <= score <= 1:
            return f"{score * 100:.2f}%"
        return f"{score:.6g}"

    return str(score)


def _format_training_success_message(job_id: str, job: dict) -> str:
    data = job.get("data") if isinstance(job.get("data"), dict) else {}
    data_name = data.get("name")
    best_model = job.get("best_model")
    best_score = _format_score(job.get("best_score"))
    time_limit_reached = job.get("time_limit_reached")

    lines = [
        "✅ Job training đã hoàn tất.",
        f"- Job ID: {job_id}",
    ]

    if data_name:
        lines.append(f"- Dataset: {data_name}")
    if best_model:
        lines.append(f"- Best model: {best_model}")

    lines.append(f"- Best score: {best_score}")

    if time_limit_reached is not None:
        lines.append(
            f"- Chạm giới hạn thời gian: {'Có' if bool(time_limit_reached) else 'Không'}"
        )

    lines.append("Bạn có thể mở Training History để xem đầy đủ chi tiết.")
    return "\n".join(lines)


def _format_training_failed_message(job_id: str, job: dict) -> str:
    error_detail = job.get("infor") or job.get("error") or "Không rõ nguyên nhân"
    return "\n".join([
        "❌ Job training kết thúc với trạng thái lỗi.",
        f"- Job ID: {job_id}",
        f"- Chi tiết: {error_detail}",
        "Bạn có thể gửi lại lệnh train hoặc kiểm tra cấu hình dataset/features.",
    ])


async def _poll_training_result_and_notify(
    conversation_id: str,
    user_id: str,
    user_token: str,
    job_id: str,
):
    """Theo dõi trạng thái job và ghi kết quả vào hội thoại khi kết thúc."""
    task_key = f"{conversation_id}:{job_id}"
    hautoml_base = get_hautoml_config()["base_url"].rstrip("/")
    deadline = time.monotonic() + TRAINING_POLL_TIMEOUT_SECONDS

    try:
        while time.monotonic() < deadline:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        f"{hautoml_base}/get-job-info",
                        params={"id": job_id},
                        headers={"Authorization": f"Bearer {user_token}"},
                    )

                if resp.status_code == 200:
                    job = resp.json()
                    raw_status = job.get("status")

                    try:
                        job_status = int(raw_status)
                    except Exception:
                        job_status = raw_status

                    if job_status == 1:
                        await conv_store.add_message(
                            conversation_id=conversation_id,
                            user_id=user_id,
                            role="assistant",
                            content=_format_training_success_message(job_id, job),
                            provider="hagent",
                            model="hagent-agent",
                        )
                        return

                    if job_status == -1:
                        await conv_store.add_message(
                            conversation_id=conversation_id,
                            user_id=user_id,
                            role="assistant",
                            content=_format_training_failed_message(job_id, job),
                            provider="hagent",
                            model="hagent-agent",
                        )
                        return

                elif resp.status_code in {401, 403}:
                    logger.warning(
                        "Không thể tiếp tục theo dõi job %s do lỗi xác thực (%d)",
                        job_id,
                        resp.status_code,
                    )
                    await conv_store.add_message(
                        conversation_id=conversation_id,
                        user_id=user_id,
                        role="assistant",
                        content=(
                            f"⚠️ Đã submit job {job_id}, nhưng không thể theo dõi kết quả tự động "
                            "do token hết hạn hoặc không hợp lệ. Bạn có thể kiểm tra ở Training History."
                        ),
                        provider="hagent",
                        model="hagent-agent",
                    )
                    return

            except Exception as e:
                logger.warning("Lỗi khi theo dõi job %s: %s", job_id, e)

            await asyncio.sleep(TRAINING_POLL_INTERVAL_SECONDS)

        await conv_store.add_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role="assistant",
            content=(
                f"ℹ️ Job {job_id} vẫn đang xử lý sau {TRAINING_POLL_TIMEOUT_SECONDS} giây. "
                "Mình sẽ dừng theo dõi tự động, bạn có thể mở Training History để xem tiến trình mới nhất."
            ),
            provider="hagent",
            model="hagent-agent",
        )
    finally:
        _training_watch_tasks.pop(task_key, None)


def _schedule_training_result_notification(
    conversation_id: str,
    user_id: str,
    user_token: str,
    job_id: str,
):
    task_key = f"{conversation_id}:{job_id}"
    existing = _training_watch_tasks.get(task_key)

    if existing and not existing.done():
        return

    _training_watch_tasks[task_key] = asyncio.create_task(
        _poll_training_result_and_notify(
            conversation_id=conversation_id,
            user_id=user_id,
            user_token=user_token,
            job_id=job_id,
        )
    )
    logger.info("Đã schedule theo dõi kết quả training cho job %s", job_id)


# ─── Endpoints ───────────────────────────────────────────


@hagent_bridge.post("/api/v1/chat/", response_model=ChatResponse)
async def chat(
    request: Request,
    req: ChatRequest,
    user: TokenPayload = Depends(get_current_user),
):
    logger.debug(f"CHAT ENDPOINT HEADERS: {request.headers}")
    """
    Endpoint chat chính — nhận tin nhắn, chuyển tiếp tới HAgent,
    lưu hội thoại vào MongoDB, trả phản hồi trợ lý.
    """
    conversation_id = req.conversation_id or uuid.uuid4().hex

    # Lưu tin nhắn người dùng
    await conv_store.add_message(
        conversation_id=conversation_id,
        user_id=user.user_id,
        role="user",
        content=req.message,
    )

    # Lấy lịch sử hội thoại
    history = await conv_store.get_message_history(conversation_id, user.user_id, limit=20)
    history_dicts = [{"role": m.role, "content": m.content} for m in history[:-1]]

    # Gọi HAgent Gateway
    result = await _call_hagent_gateway(
        message=req.message,
        history=history_dicts if history_dicts else None,
        user_token=user.raw_token,
        user_id=user.user_id,
    )

    # Lưu phản hồi trợ lý
    await conv_store.add_message(
        conversation_id=conversation_id,
        user_id=user.user_id,
        role="assistant",
        content=result["message"],
        provider=result.get("provider", ""),
        model=result.get("model", ""),
    )

    tracked_job_id = _extract_training_job_id(result["message"])
    if tracked_job_id:
        _schedule_training_result_notification(
            conversation_id=conversation_id,
            user_id=user.user_id,
            user_token=user.raw_token,
            job_id=tracked_job_id,
        )

    return ChatResponse(
        message=result["message"],
        conversation_id=conversation_id,
        sources=result.get("sources", []),
        suggestions=result.get("suggestions", []),
        provider=result.get("provider", ""),
        model=result.get("model", ""),
    )


@hagent_bridge.post("/api/v1/chat/upload", response_model=ChatResponse)
async def chat_with_file(
    message: str = Form(...),
    file: UploadFile = File(...),
    conversation_id: str | None = Form(None),
    user: TokenPayload = Depends(get_current_user),
):
    """Chat kèm upload file — chuyển tiếp file tới HAutoML."""
    hautoml_cfg = get_hautoml_config()
    conv_id = conversation_id or uuid.uuid4().hex

    # Chuyển tiếp file tới HAutoML để upload data
    file_info = ""
    try:
        file_content = await file.read()
        
        # Xác định data_type từ đuôi file
        filename = file.filename or "uploaded_data.csv"
        data_type = filename.split('.')[-1].lower() if '.' in filename else "csv"
        
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{hautoml_cfg['base_url']}/upload-dataset?user_id={user.user_id}",
                data={
                    "data_name": filename,
                    "data_type": data_type,
                },
                files={
                    "file_data": (filename, file_content, file.content_type)
                },
                headers={"Authorization": f"Bearer {user.raw_token}"},
            )
            if resp.status_code == 200:
                file_info = f"\n[File đã upload vào hệ thống dataset: {filename} — {len(file_content)} bytes]"
            else:
                file_info = f"\n[Upload file thất bại: {resp.status_code} - {resp.text}]"
    except Exception as e:
        file_info = f"\n[Lỗi upload file: {e}]"

    full_message = f"{message}{file_info}"
    await conv_store.add_message(conv_id, user.user_id, "user", full_message)

    history = await conv_store.get_message_history(conv_id, user.user_id, limit=20)
    history_dicts = [{"role": m.role, "content": m.content} for m in history[:-1]]

    result = await _call_hagent_gateway(
        message=full_message,
        history=history_dicts if history_dicts else None,
        user_token=user.raw_token,
        user_id=user.user_id,
    )

    await conv_store.add_message(
        conv_id, user.user_id, "assistant", result["message"],
        result.get("provider", ""), result.get("model", ""),
    )

    tracked_job_id = _extract_training_job_id(result["message"])
    if tracked_job_id:
        _schedule_training_result_notification(
            conversation_id=conv_id,
            user_id=user.user_id,
            user_token=user.raw_token,
            job_id=tracked_job_id,
        )

    return ChatResponse(
        message=result["message"], conversation_id=conv_id,
        sources=result.get("sources", []), suggestions=result.get("suggestions", []),
        provider=result.get("provider", ""), model=result.get("model", ""),
    )


@hagent_bridge.get("/api/v1/chat/health", response_model=HealthResponse)
async def health_check():
    """Kiểm tra kết nối tới HAgent Gateway và HAutoML backend."""
    import os
    from .config import get_gateway_config
    gw_cfg = get_gateway_config()
    gateway_url = os.getenv("HAGENT_GATEWAY_URL", f"http://{gw_cfg['host']}:{gw_cfg['port']}")
    hautoml_cfg = get_hautoml_config()

    # Kiểm tra HAgent Gateway
    hagent_ok = False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{gateway_url}/health")
            hagent_ok = resp.status_code == 200
    except Exception:
        pass

    # Kiểm tra HAutoML Backend
    hautoml_ok = False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{hautoml_cfg['base_url']}/home")
            hautoml_ok = resp.status_code == 200
    except Exception:
        pass

    return HealthResponse(
        hagent_url=gateway_url,
        connected=hagent_ok,
        hautoml_connected=hautoml_ok,
        mode="hagent",
        active_provider="hagent",
        active_model="hagent-agent",
        available_providers=["hagent"],
    )


@hagent_bridge.get("/api/v1/chat/suggestions", response_model=SuggestionsResponse)
async def get_suggestions():
    """Trả về gợi ý chat ban đầu cho widget."""
    return SuggestionsResponse(
        suggestions=[
            "📊 Hiển thị danh sách dataset của tôi",
            "🚀 Huấn luyện model phân loại mới",
            "📈 Có những thuật toán ML nào khả dụng?",
            "🔍 Kiểm tra trạng thái các job training",
            "💡 Giúp tôi chọn model phù hợp",
            "⚙️ Chuyển sang provider AI khác",
        ]
    )


@hagent_bridge.delete("/api/v1/chat/conversation/{conversation_id}")
async def clear_conversation(
    conversation_id: str,
    user: TokenPayload = Depends(get_current_user),
):
    """Xóa cuộc hội thoại và toàn bộ lịch sử."""
    deleted = await conv_store.delete_conversation(conversation_id, user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc hội thoại")
    return {"status": "deleted", "conversation_id": conversation_id}


@hagent_bridge.get("/api/v1/chat/providers", response_model=ProvidersResponse)
async def list_providers(
    user: TokenPayload | None = Depends(get_optional_user),
):
    """Liệt kê tất cả LLM provider khả dụng. Giờ chỉ còn HAgent."""
    providers = [
        ProviderInfo(
            name="HAgent",
            provider_id="hagent",
            models=["hagent-agent"],
            available=True,
            description="✅ HAgent",
        )
    ]
    return ProvidersResponse(
        default_provider="hagent",
        default_model="hagent-agent",
        providers=providers,
    )


@hagent_bridge.get("/api/v1/chat/conversations")
async def list_user_conversations(
    user: TokenPayload = Depends(get_current_user),
):
    """Liệt kê các cuộc hội thoại gần nhất của người dùng."""
    conversations = await conv_store.list_conversations(user.user_id)
    return {"conversations": conversations}


@hagent_bridge.get("/api/v1/chat/conversation/{conversation_id}")
async def get_conversation_history(
    conversation_id: str,
    user: TokenPayload = Depends(get_current_user),
):
    """Truy xuất toàn bộ lịch sử tin nhắn của một cuộc hội thoại cụ thể."""
    conversation = await conv_store.get_conversation(conversation_id, user.user_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc hội thoại")
    
    return {
        "conversation_id": conversation.conversation_id,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "provider": conversation.provider,
        "model": conversation.model,
        "messages": [
            {
                "id": str(uuid.uuid4()),
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                "provider": msg.provider,
                "model": msg.model
            }
            for msg in conversation.messages
        ]
    }


# ─── Điểm chạy chính ────────────────────────────────────


def main():
    """Chạy bridge server với uvicorn."""
    import uvicorn
    cfg = get_bridge_config()
    uvicorn.run(
        "hagent.bridge.app:hagent_bridge",
        host=cfg["host"],
        port=cfg["port"],
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
