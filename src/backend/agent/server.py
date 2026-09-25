"""
HTTP API cho agent, để frontend gọi vào.

    cd src/backend
    python -m agent.server              # chạy ở cổng 9500

Vì sao chạy riêng thay vì thêm route vào app.py: container `hautoml-toolkit`
không mount source từ host, nên sửa app.py không có tác dụng với container đang
chạy - phải build lại ảnh. Chạy tách ra thì không đụng gì tới Docker.

Xác thực: frontend đã đăng nhập bằng NextAuth và có sẵn access_token, nên nó
gửi kèm token đó xuống đây. Agent dùng luôn token ấy, KHÔNG tự đăng nhập lại -
agent thao tác đúng với quyền của người đang dùng web.
"""

# Standard libraries
import os
import time
import uuid

# Third party libraries
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Local modules
from agent import providers
from agent.chat import ChatSession


# Load file .env
load_dotenv()


# Phiên không dùng tới quá lâu thì dọn, tránh giữ token trong RAM vô hạn.
SESSION_TTL_SECONDS = 60 * 60
MAX_SESSIONS = 200


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None
    access_token: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    tools: list[str]
    total_tokens: int


class _Entry:
    def __init__(self, session: ChatSession):
        self.session = session
        self.touched = time.time()


_sessions: dict[str, _Entry] = {}


def _sweep() -> None:
    """Dọn phiên hết hạn. Gọi trước mỗi request, đủ cho quy mô hiện tại."""
    now = time.time()
    dead = [key for key, entry in _sessions.items() if now - entry.touched > SESSION_TTL_SECONDS]

    # Quá nhiều phiên thì bỏ những cái cũ nhất, chặn rò rỉ bộ nhớ.
    if len(_sessions) - len(dead) > MAX_SESSIONS:
        alive = sorted(
            (k for k in _sessions if k not in dead),
            key=lambda k: _sessions[k].touched,
        )
        dead.extend(alive[: len(alive) - MAX_SESSIONS])

    for key in dead:
        _sessions.pop(key).session.close()


def _get_session(session_id: str | None, access_token: str | None) -> tuple[str, ChatSession]:
    _sweep()

    if session_id and session_id in _sessions:
        entry = _sessions[session_id]
        entry.touched = time.time()
        # Token có thể được làm mới phía frontend giữa chừng.
        if access_token:
            entry.session.api.access_token = access_token
        return session_id, entry.session

    session = ChatSession(verbose=False)
    if access_token:
        # Nhận token của người dùng web thay vì bắt agent đăng nhập lại.
        session.api.access_token = access_token

    new_id = uuid.uuid4().hex
    _sessions[new_id] = _Entry(session)
    return new_id, session


app = FastAPI(title="HAutoML Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    config = providers.resolve()
    return {
        "status": "ok",
        "provider": config.name,
        "model": config.model,
        "sessions": len(_sessions),
    }


@app.post("/agent/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    session_id, session = _get_session(request.session_id, request.access_token)

    before = len(session.messages)
    try:
        reply = session.send(request.message)
    except Exception as error:  # noqa: BLE001 - trả lỗi có cấu trúc cho frontend
        raise HTTPException(status_code=502, detail=f"{type(error).__name__}: {error}")

    # Lấy tên tool đã gọi trong lượt này, để frontend hiện "đang làm gì".
    tools_used = [
        call["function"]["name"]
        for message in session.messages[before:]
        if message.get("role") == "assistant"
        for call in message.get("tool_calls") or []
    ]

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        tools=tools_used,
        total_tokens=session.usage["total_tokens"],
    )


@app.post("/agent/reset")
async def reset(request: ChatRequest) -> dict:
    if request.session_id and request.session_id in _sessions:
        _sessions[request.session_id].session.reset()
        return {"ok": True}
    return {"ok": False, "detail": "Không tìm thấy phiên."}


def main() -> None:
    uvicorn.run(
        app,
        host=os.getenv("AGENT_HOST", "0.0.0.0"),
        port=int(os.getenv("AGENT_PORT", "9500")),
    )


if __name__ == "__main__":
    main()
