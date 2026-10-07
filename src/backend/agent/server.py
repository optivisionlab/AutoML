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

Báo tiến độ (SSE): một lượt chat có thể gọi LLM hàng chục lần qua 5 agent, và
job huấn luyện chạy nền hàng giờ. Hai luồng sự kiện:

    POST /agent/chat/stream   tiến độ của MỘT lượt chat, kết thúc bằng `reply`
    POST /agent/events        sự kiện nền (job đổi trạng thái, job xong) - giữ
                              mở ~1 phút rồi đóng, frontend mở lại kèm token mới

Dùng POST thay vì EventSource (GET) để gửi token trong body chứ không phải trên
URL - URL hay bị ghi vào log.
"""

# Standard libraries
import asyncio
import json
import os
import threading
import time
import uuid

# Third party libraries
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.datastructures import UploadFile

# Local modules
from agent import providers, tools, uploads
from agent.chat import ChatSession


# Load file .env
load_dotenv()


# Phiên không dùng tới quá lâu thì dọn, tránh giữ token trong RAM vô hạn.
SESSION_TTL_SECONDS = 60 * 60
MAX_SESSIONS = 200
# Phiên đang theo dõi job thì giữ lâu hơn - dọn đi là watcher chết theo. Vẫn
# có trần để một job treo không giữ phiên mãi.
WATCHING_TTL_SECONDS = 26 * 60 * 60
# Một kết nối /agent/events sống bao lâu trước khi bảo frontend mở lại. Ngắn
# hơn hạn token (15 phút) để token mới kịp được gửi lên cho watcher dùng.
EVENTS_STREAM_SECONDS = 55


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None
    access_token: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    # Tool các sub-agent đã gọi trong lượt này, theo thứ tự.
    tools: list[str]
    # Sub-agent Manager đã giao việc trong lượt này, theo thứ tự.
    agents: list[str]
    total_tokens: int
    # job_id đang được theo dõi nền.
    watching: list[str]


class EventsRequest(BaseModel):
    session_id: str
    access_token: str | None = None
    # seq của sự kiện cuối frontend đã nhận.
    after: int = 0


class _Entry:
    def __init__(self, session: ChatSession):
        self.session = session
        self.touched = time.time()
        # Một phiên chỉ chạy một lượt chat mỗi lúc: hai lượt song song sẽ ghi
        # xen vào cùng lịch sử hội thoại.
        self.turn_lock = threading.Lock()


_sessions: dict[str, _Entry] = {}


def _sweep() -> None:
    """Dọn phiên hết hạn. Gọi trước mỗi request, đủ cho quy mô hiện tại."""
    now = time.time()
    dead = [
        key
        for key, entry in _sessions.items()
        if now - entry.touched > (
            WATCHING_TTL_SECONDS if entry.session.watcher.active() else SESSION_TTL_SECONDS
        )
    ]

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

    # auto_login=False là bắt buộc ở đây: frontend phải gửi token của người dùng
    # đã đăng nhập. Nếu cho phép tự đăng nhập bằng AGENT_USER trong .env thì một
    # người CHƯA đăng nhập sẽ thao tác dưới danh nghĩa tài khoản đó.
    session = ChatSession(verbose=False, access_token=access_token, auto_login=False)

    new_id = uuid.uuid4().hex
    session.trace_session_id = new_id
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
        "watching_jobs": sum(len(e.session.watcher.active()) for e in _sessions.values()),
    }


def _require_login(session: ChatSession) -> None:
    # Chặn sớm và nói rõ, thay vì để từng tool trả 401 rời rạc khiến agent
    # phải đoán chuyện gì đang xảy ra.
    if not session.api.access_token:
        raise HTTPException(
            status_code=401,
            detail="Chưa đăng nhập. Frontend phải gửi access_token của phiên người dùng.",
        )


def _run_turn(session_id: str, entry: _Entry, message: str) -> ChatResponse:
    """
    Chạy một lượt chat. ĐỒNG BỘ - gọi qua thread, không chạy thẳng trong event loop.

    Một lượt có thể gọi LLM hàng chục lần; chạy trong event loop thì mọi request
    khác (kể cả luồng SSE) đứng chờ tới khi xong.
    """
    if not entry.turn_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Phiên này đang xử lý một tin nhắn khác.")

    session = entry.session
    try:
        start = session.events.last_seq
        reply = session.send(message)
    except HTTPException:
        raise
    except Exception as error:  # noqa: BLE001 - trả lỗi có cấu trúc cho frontend
        raise HTTPException(status_code=502, detail=f"{type(error).__name__}: {error}")
    finally:
        entry.turn_lock.release()

    happened = session.events.since(start)
    agents: list[str] = []
    for event in happened:
        if event["type"] == "agent_start" and event.get("agent") not in agents:
            agents.append(event["agent"])

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        # Tool sub-agent thực sự gọi, để frontend hiện "đã làm gì". Bỏ các tool
        # ask_* của Manager - đã có trong `agents`.
        tools=[
            event["name"]
            for event in happened
            if event["type"] == "tool_call" and not str(event.get("name", "")).startswith("ask_")
        ],
        agents=agents,
        total_tokens=session.usage["total_tokens"],
        watching=session.watcher.active(),
    )


@app.post("/agent/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    session_id, session = _get_session(request.session_id, request.access_token)
    _require_login(session)
    return await asyncio.to_thread(_run_turn, session_id, _sessions[session_id], request.message)


def _sse(event: str, data: dict, event_id: int | None = None) -> str:
    lines = [f"id: {event_id}"] if event_id is not None else []
    lines += [f"event: {event}", f"data: {json.dumps(data, ensure_ascii=False, default=str)}"]
    return "\n".join(lines) + "\n\n"


_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    # Nginx mặc định gom response lại rồi mới gửi - tắt đi để sự kiện tới ngay.
    "X-Accel-Buffering": "no",
}


@app.post("/agent/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    Như /agent/chat nhưng trả SSE: các sự kiện tiến độ trong lúc chạy, rồi một
    sự kiện `reply` (cùng nội dung ChatResponse) hoặc `error` ở cuối.
    """
    session_id, session = _get_session(request.session_id, request.access_token)
    _require_login(session)
    entry = _sessions[session_id]
    start = session.events.last_seq

    async def stream():
        yield _sse("session", {"session_id": session_id})
        turn = asyncio.create_task(asyncio.to_thread(_run_turn, session_id, entry, request.message))
        # Frontend ngắt giữa chừng thì lượt chat vẫn chạy nốt và vào lịch sử;
        # đọc exception để asyncio không cảnh báo "never retrieved".
        turn.add_done_callback(lambda task: task.cancelled() or task.exception())
        last = start

        while True:
            happened = await asyncio.to_thread(session.events.wait, last, 0.5)
            for event in happened:
                last = event["seq"]
                yield _sse(event["type"], event, event["seq"])

            if turn.done():
                for event in session.events.since(last):
                    last = event["seq"]
                    yield _sse(event["type"], event, event["seq"])
                try:
                    yield _sse("reply", turn.result().model_dump(), last)
                except HTTPException as error:
                    yield _sse("error", {"status_code": error.status_code, "detail": error.detail})
                return

    return StreamingResponse(stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.post("/agent/events")
async def background_events(request: EventsRequest, http: Request) -> StreamingResponse:
    """
    Sự kiện nền của một phiên (job đổi trạng thái, job xong), kể từ seq `after`.

    Đóng sau EVENTS_STREAM_SECONDS bằng sự kiện `reconnect`. Frontend mở lại kèm
    token mới nhất - đó là cách token tới được watcher đang theo dõi job hàng giờ.
    """
    entry = _sessions.get(request.session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên.")

    entry.touched = time.time()
    if request.access_token:
        entry.session.api.access_token = request.access_token
    bus = entry.session.events

    async def stream():
        last = request.after
        deadline = time.monotonic() + EVENTS_STREAM_SECONDS
        yield ": connected\n\n"

        while time.monotonic() < deadline:
            if await http.is_disconnected():
                return
            happened = await asyncio.to_thread(bus.wait, last, 5)
            for event in happened:
                last = event["seq"]
                yield _sse(event["type"], event, event["seq"])
            if not happened:
                # Comment SSE giữ kết nối không bị proxy cắt vì im lặng.
                yield ": ping\n\n"

        yield _sse("reconnect", {"after": last, "watching": entry.session.watcher.active()})

    return StreamingResponse(stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


# Phần dư ngoài nội dung file trong một request multipart: boundary, tên trường,
# data_name, access_token... 64 KB là thừa thãi, chỉ để không chặn nhầm file
# dung đúng 20 MB.
_MULTIPART_OVERHEAD = 64 * 1024
_MAX_DATASET_NAME = 100


@app.post("/agent/upload")
async def upload(request: Request) -> dict:
    """
    Nhận file dataset từ khung chat và đưa vào kho dataset của người dùng.

    Form (multipart): file, access_token, session_id (tuỳ chọn),
                      data_name (tuỳ chọn), data_type = classification | regression

    Giới hạn 20 MB được chặn HAI lớp, vì Starlette KHÔNG giới hạn dung lượng
    file (max_part_size của nó chỉ áp cho trường chữ):
      1. Content-Length, kiểm tra TRƯỚC khi đọc body - chặn sớm, rẻ.
      2. Đếm byte thật sau khi đọc - chốt cuối, kể cả khi client không gửi
         Content-Length hoặc gửi sai.
    """
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > uploads.MAX_UPLOAD_BYTES + _MULTIPART_OVERHEAD:
        raise HTTPException(
            status_code=413,
            detail=f"File vượt giới hạn {uploads.MAX_UPLOAD_MB} MB.",
        )

    try:
        form = await request.form(max_files=1, max_fields=10)
    except Exception as error:  # noqa: BLE001 - form hỏng thì báo 400, đừng để 500
        raise HTTPException(status_code=400, detail=f"Không đọc được form tải lên: {error}")

    file = form.get("file")
    if not isinstance(file, UploadFile):
        raise HTTPException(status_code=400, detail="Thiếu trường 'file'.")

    data_type = str(form.get("data_type") or "classification").strip().lower()
    if data_type not in uploads.DATA_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"data_type phải là một trong: {', '.join(uploads.DATA_TYPES)}.",
        )

    # Đọc tối đa 20 MB + 1 byte: đủ để biết có vượt không mà không phải nạp cả
    # một file khổng lồ vào RAM.
    content = await file.read(uploads.MAX_UPLOAD_BYTES + 1)
    await file.close()

    check = uploads.check_dataset_file(file.filename or "", content)
    if not check.ok:
        raise HTTPException(status_code=check.status_code, detail=check.error)

    data_name = str(form.get("data_name") or "").strip() or uploads.default_dataset_name(check.clean_name)
    data_name = data_name[:_MAX_DATASET_NAME]

    session_id, session = _get_session(
        str(form.get("session_id") or "") or None,
        str(form.get("access_token") or "") or None,
    )
    if not session.api.access_token:
        raise HTTPException(
            status_code=401,
            detail="Chưa đăng nhập. Frontend phải gửi access_token của phiên người dùng.",
        )

    result = tools.upload_dataset_file(
        session.api,
        filename=check.clean_name,
        content=content,
        data_name=data_name,
        data_type=data_type,
        mime_type=check.mime_type,
    )
    if not result["ok"]:
        code = result.get("status_code") or 502
        # status 0 = không tới được backend. 401/403 giữ nguyên. Mọi lỗi khác
        # của backend ở đây đều là "không đọc được file" (backend trả 404 cho
        # trường hợp này, nghe rất khó hiểu với người dùng).
        status = 502 if code == 0 else code if code in (401, 403) else 422
        raise HTTPException(status_code=status, detail=result.get("error"))

    dataset = result["dataset"]
    session.add_event(
        f"Người dùng vừa tải lên dataset '{dataset['name']}' (id: {dataset['id']}, "
        f"loại bài toán: {dataset['type']}, file: {check.clean_name}). Dataset này "
        "đã nằm trong kho của họ. Dùng id này luôn nếu họ hỏi về nó, không cần "
        "liệt kê lại."
    )

    return {
        "ok": True,
        "session_id": session_id,
        "dataset": {**dataset, "filename": check.clean_name, "size_bytes": len(content)},
    }


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
