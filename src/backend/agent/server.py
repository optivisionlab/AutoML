"""
HTTP API cho agent, để frontend gọi vào.

    cd src/backend
    python -m agent.server              # chạy ở cổng 9500

Vì sao chạy riêng thay vì thêm route vào app.py: container `hautoml-toolkit`
không mount source từ host, nên sửa app.py không có tác dụng với container đang
chạy - phải build lại ảnh. Chạy tách ra thì không đụng gì tới Docker.

Xác thực: frontend đã đăng nhập bằng NextAuth và có sẵn access_token, nên nó
gửi kèm token đó xuống đây. Agent dùng luôn token ấy, KHÔNG tự đăng nhập lại -
agent thao tác đúng với quyền của người đang dùng web. NextAuth làm mới token
thì frontend gửi token mới qua POST /agent/token, kể cả giữa một lượt chat.

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
import functools
import json
import logging
import os
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor

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
from agent.agent_openai import describe_error, log_exception
from agent.api_client import ApiError, HAutoMLClient
from agent.chat import ChatSession


# Load file .env
load_dotenv()


# Phiên không dùng tới quá lâu thì dọn, tránh giữ token trong RAM vô hạn.
SESSION_TTL_SECONDS = 60 * 60
MAX_SESSIONS = 200
# Hạn mức theo NGƯỜI DÙNG (review 2026-11-08): không có thì một tài khoản gửi hàng trăm request không
# kèm session_id là chiếm hết pool lượt chat, tiêu key LLM của hệ thống và đẩy phiên của người khác ra.
MAX_SESSIONS_PER_OWNER = 8
MAX_BUSY_TURNS_PER_OWNER = 2
# Body JSON (mọi endpoint trừ /agent/upload): chặn TRƯỚC khi FastAPI đọc body và trước khi kiểm token,
# người chưa đăng nhập không làm server hết RAM được bằng một body vài GB.
MAX_JSON_BODY_BYTES = 256 * 1024


def _user_hourly_tokens() -> int:
    """Trần token LLM mỗi người dùng trong 60 phút gần nhất (AGENT_USER_TOKENS_PER_HOUR, 0 = tắt)."""
    raw = os.getenv("AGENT_USER_TOKENS_PER_HOUR", "").strip()
    return int(raw) if raw.isdigit() else 1_000_000


# owner -> các (thời điểm, số token) của lượt chat trong giờ qua. Hạn mức 2 lượt bận / người chặn song song,
# nhưng một tài khoản chạy liên tục 2 lượt x trần token mỗi lượt vẫn đốt key LLM của hệ thống.
_owner_spend: dict[str, deque] = {}
_spend_lock = threading.Lock()


def _spent_last_hour(owner: str) -> int:
    cutoff = time.time() - 3600
    with _spend_lock:
        history = _owner_spend.get(owner)
        if not history:
            return 0
        while history and history[0][0] < cutoff:
            history.popleft()
        return sum(tokens for _, tokens in history)


def _record_spend(owner: str, tokens: int) -> None:
    if tokens <= 0:
        return
    with _spend_lock:
        _owner_spend.setdefault(owner, deque()).append((time.time(), tokens))
MAX_MESSAGE_CHARS = 20_000
_MAX_ID_CHARS = 64
_MAX_TOKEN_CHARS = 8192
# Phiên đang theo dõi job thì giữ lâu hơn - dọn đi là watcher chết theo. Vẫn
# có trần để một job treo không giữ phiên mãi.
WATCHING_TTL_SECONDS = 26 * 60 * 60
# Một kết nối /agent/events sống bao lâu trước khi bảo frontend mở lại. Ngắn
# hơn hạn token (15 phút) để token mới kịp được gửi lên cho watcher dùng.
EVENTS_STREAM_SECONDS = 55
# Luồng chat im lặng quá lâu (một lời gọi LLM dài) thì proxy như nginx cắt kết
# nối (mặc định 60 giây) - gửi comment SSE giữ kết nối.
CHAT_PING_SECONDS = 15
# Chờ sự kiện bằng cách hỏi bus định kỳ trong event loop, KHÔNG chiếm thread:
# trước đây mỗi kết nối SSE giữ một thread của pool mặc định (16 thread trên máy
# 12 nhân), vài chục tab đang theo dõi job là mọi request khác phải xếp hàng.
_EVENT_POLL_SECONDS = 0.25


def _turn_workers() -> int:
    raw = os.getenv("AGENT_MAX_CONCURRENT_TURNS", "").strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else 32


# Lượt chat chạy hàng phút: pool riêng, để các việc ngắn dùng asyncio.to_thread
# (xác minh token, upload) không phải chờ sau chúng.
_TURN_POOL = ThreadPoolExecutor(max_workers=_turn_workers(), thread_name_prefix="agent-turn")
# Lượt đang chạy + đang xếp hàng của MỌI người dùng: quá ngưỡng thì trả 503 thay vì xếp hàng vô hạn.
MAX_PENDING_TURNS = _turn_workers() * 4
# Upload gọi backend tới 120 giây: pool riêng, không chiếm pool mặc định mà việc xác minh token dùng.
_UPLOAD_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-upload")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)
    session_id: str | None = Field(default=None, max_length=_MAX_ID_CHARS)
    access_token: str | None = Field(default=None, max_length=_MAX_TOKEN_CHARS)
    # seq cuối frontend đã nhận. /agent/chat/stream phát lại các sự kiện sau mốc
    # này - sự kiện nền (vd job_done) rơi vào lúc luồng /agent/events đang chờ
    # kết nối lại không bị bỏ qua.
    after: int | None = None
    # Mã lượt do frontend tạo, server gắn lại vào turn_start / turn_done / turn_failed.
    turn_id: str | None = Field(default=None, max_length=64)


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
    session_id: str = Field(..., max_length=_MAX_ID_CHARS)
    access_token: str | None = Field(default=None, max_length=_MAX_TOKEN_CHARS)
    # seq của sự kiện cuối frontend đã nhận.
    after: int = 0


class AutoActivateRequest(BaseModel):
    session_id: str = Field(..., max_length=_MAX_ID_CHARS)
    access_token: str | None = Field(default=None, max_length=_MAX_TOKEN_CHARS)
    job_id: str = Field(..., min_length=1, max_length=64)
    enabled: bool


class TokenRequest(BaseModel):
    session_id: str = Field(..., max_length=_MAX_ID_CHARS)
    access_token: str | None = Field(default=None, max_length=_MAX_TOKEN_CHARS)


class _Entry:
    def __init__(self, session: ChatSession, owner: str):
        self.session = session
        # user_id của chủ phiên. Mọi request vào phiên này phải mang token của
        # đúng người đó - session_id thôi không đủ (xem _resolve_owner).
        self.owner = owner
        self.touched = time.time()
        # Một phiên chỉ chạy một lượt chat mỗi lúc: hai lượt song song sẽ ghi
        # xen vào cùng lịch sử hội thoại.
        self.turn_lock = threading.Lock()
        # Số upload đang chạy trên phiên này (gọi backend tới 120 giây): phiên bận, không được dọn - dọn là
        # đóng HTTP client giữa lúc đang gửi file.
        self.uploads = 0

    def busy(self) -> bool:
        return self.turn_lock.locked() or self.uploads > 0


_sessions: dict[str, _Entry] = {}


def _sweep() -> None:
    """Dọn phiên hết hạn. Gọi trước mỗi request, đủ cho quy mô hiện tại."""
    now = time.time()
    # Phiên đang chạy một lượt chat thì không bao giờ dọn: close() giữa chừng
    # làm đứt mọi lời gọi backend của lượt đó.
    busy = {key for key, entry in _sessions.items() if entry.busy()}
    dead = [
        key
        for key, entry in _sessions.items()
        if key not in busy and now - entry.touched > (
            WATCHING_TTL_SECONDS if entry.session.watcher.active() else SESSION_TTL_SECONDS
        )
    ]

    # Quá nhiều phiên thì bỏ những phiên RẢNH cũ nhất, chặn rò rỉ bộ nhớ. Phiên đang theo dõi job
    # KHÔNG bao giờ bị dọn để nhường chỗ (watcher chết, lời hứa tự kích hoạt mất, người dùng không
    # được báo) - hết chỗ thì phiên MỚI bị từ chối (_get_session trả 503).
    if len(_sessions) - len(dead) > MAX_SESSIONS:
        alive = sorted(
            (k for k in _sessions if k not in dead and k not in busy and not _sessions[k].session.watcher.active()),
            key=lambda k: _sessions[k].touched,
        )
        dead.extend(alive[: max(0, len(_sessions) - len(dead) - MAX_SESSIONS)])

    for key in dead:
        _sessions.pop(key).session.close()


# token -> (user_id, hết hạn cache). Xác minh qua backend tốn một request, nên
# nhớ ngắn hạn: frontend gửi cùng token ở mọi lượt chat / kết nối SSE.
_OWNER_CACHE_SECONDS = 60
_BAD_TOKEN_CACHE_SECONDS = 5
_owner_cache: dict[str, tuple[str, float]] = {}
_owner_lock = threading.Lock()


def _owner_of(access_token: str) -> str | None:
    """
    user_id của token, do BACKEND xác nhận qua /me. Token sai/hết hạn -> None.

    Không tự đọc trường `sub` trong JWT: không kiểm chữ ký thì ai cũng tự viết
    được một token mang `sub` của người khác.
    """
    now = time.time()
    with _owner_lock:
        cached = _owner_cache.get(access_token)
        if cached and cached[1] > now:
            # "" = token sai vừa bị backend từ chối: không gọi lại /me liên tục cho cùng token rác.
            return cached[0] or None

    client = HAutoMLClient()
    client.access_token = access_token
    try:
        user = client.get_me()
    except ApiError as error:
        # Chỉ 401/403 mới là token sai/hết hạn. Backend không tới được hoặc lỗi 5xx
        # mà trả 401 thì frontend bảo người dùng đăng nhập lại - sai, và mất tin nhắn.
        if error.status_code in (401, 403):
            with _owner_lock:
                if len(_owner_cache) > 1000:
                    _owner_cache.clear()
                _owner_cache[access_token] = ("", now + _BAD_TOKEN_CACHE_SECONDS)
            return None
        raise BackendUnavailable(error.detail) from error
    finally:
        client.close()

    owner = str(user.get("_id") or user.get("id") or "")
    if not owner:
        return None
    with _owner_lock:
        # Dọn bớt khi cache phình (token đổi mỗi 15 phút).
        if len(_owner_cache) > 1000:
            _owner_cache.clear()
        _owner_cache[access_token] = (owner, now + _OWNER_CACHE_SECONDS)
    return owner


class BackendUnavailable(RuntimeError):
    """Không xác minh được token vì backend HAutoML không phản hồi (không phải token sai)."""


async def _resolve_owner(access_token: str | None) -> str:
    """Chặn request không có token hợp lệ. Chạy trong thread: gọi HTTP đồng bộ."""
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Chưa đăng nhập. Frontend phải gửi access_token của phiên người dùng.",
        )
    try:
        owner = await asyncio.to_thread(_owner_of, access_token)
    except BackendUnavailable as error:
        raise HTTPException(
            status_code=503, detail="Backend HAutoML tạm thời không phản hồi, thử lại sau.",
        ) from error
    if owner is None:
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn. Đăng nhập lại.")
    return owner


def _find_entry(session_id: str | None, owner: str) -> _Entry | None:
    """Phiên của đúng người này. Phiên của người khác coi như không tồn tại."""
    entry = _sessions.get(session_id) if session_id else None
    if entry is None or entry.owner != owner:
        return None
    return entry


def _make_room_for(owner: str) -> None:
    """
    Trước khi tạo phiên MỚI: mỗi người dùng tối đa MAX_SESSIONS_PER_OWNER phiên - vượt thì dọn phiên
    rảnh, không theo dõi job, cũ nhất của CHÍNH người đó. Không dọn được (mọi phiên đều bận / đang theo
    dõi job) thì 429; cả server hết chỗ thì 503. Không bao giờ dọn phiên của người khác để nhường chỗ.
    """
    mine = [key for key, entry in _sessions.items() if entry.owner == owner]
    if len(mine) >= MAX_SESSIONS_PER_OWNER:
        idle = sorted(
            (k for k in mine if not _sessions[k].busy() and not _sessions[k].session.watcher.active()),
            key=lambda k: _sessions[k].touched,
        )
        for key in idle[: len(mine) - MAX_SESSIONS_PER_OWNER + 1]:
            _sessions.pop(key).session.close()
        if sum(1 for entry in _sessions.values() if entry.owner == owner) >= MAX_SESSIONS_PER_OWNER:
            raise HTTPException(
                status_code=429,
                detail="Bạn đang có quá nhiều phiên chat đang chạy / theo dõi job. Dùng lại phiên hiện có hoặc thử lại sau.",
            )
    if len(_sessions) >= MAX_SESSIONS:
        raise HTTPException(status_code=503, detail="Agent đang quá tải, thử lại sau ít phút.")


def _get_session(session_id: str | None, access_token: str, owner: str) -> tuple[str, ChatSession]:
    """
    Lấy phiên cũ nếu nó thuộc về `owner`, không thì tạo phiên mới.

    Gửi session_id của người khác kèm token của mình KHÔNG lấy được phiên đó:
    nhận về một phiên mới tinh, không thấy lịch sử của họ.
    """
    _sweep()

    entry = _find_entry(session_id, owner)
    if entry is not None:
        entry.touched = time.time()
        # Token được làm mới phía frontend sau mỗi 15 phút.
        entry.session.api.access_token = access_token
        return session_id, entry.session

    _make_room_for(owner)

    # auto_login=False là bắt buộc ở đây: frontend phải gửi token của người dùng
    # đã đăng nhập. Nếu cho phép tự đăng nhập bằng AGENT_USER trong .env thì một
    # người CHƯA đăng nhập sẽ thao tác dưới danh nghĩa tài khoản đó.
    session = ChatSession(verbose=False, access_token=access_token, auto_login=False)

    new_id = uuid.uuid4().hex
    session.trace_session_id = new_id
    _sessions[new_id] = _Entry(session, owner)
    return new_id, session


app = FastAPI(title="HAutoML Agent API")


class _JsonBodyLimit:
    """
    Middleware ASGI: body của mọi endpoint (trừ /agent/upload có giới hạn riêng) tối đa
    MAX_JSON_BODY_BYTES. Đọc và đếm body TRƯỚC khi FastAPI parse JSON (vốn chạy trước handler kiểm
    token), vượt trần thì trả 413 ngay - kể cả gửi chunked không có Content-Length.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") == "/agent/upload":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length", b"")
        if declared.isdigit() and int(declared) > MAX_JSON_BODY_BYTES:
            return await self._too_large(send)
        chunks, size, more = [], 0, True
        while more:
            message = await receive()
            if message["type"] != "http.request":
                return  # client ngắt giữa chừng
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > MAX_JSON_BODY_BYTES:
                return await self._too_large(send)
            chunks.append(chunk)
            more = message.get("more_body", False)
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()  # sau body: chờ http.disconnect như bình thường (SSE cần)

        return await self.app(scope, replay, send)

    @staticmethod
    async def _too_large(send):
        body = json.dumps({"detail": f"Request quá lớn (tối đa {MAX_JSON_BODY_BYTES // 1024} KB)."}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


app.add_middleware(_JsonBodyLimit)

# Chỉ frontend của hệ thống được gọi agent từ trình duyệt. Không dùng cookie
# (token nằm trong body) nên không cần allow_credentials.
_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("AGENT_CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
async def health() -> dict:
    # Liveness không phụ thuộc cấu hình LLM: upload vẫn dùng được khi thiếu key.
    result = {
        "status": "ok",
        "llm_ready": False,
        "provider": None,
        "model": None,
    }
    try:
        config = providers.resolve()
    except (RuntimeError, ValueError) as error:
        result.update(status="degraded", configuration_error=str(error))
    else:
        result.update(llm_ready=True, provider=config.name, model=config.model)
    return result


async def _wait_events(bus, after: int, timeout: float) -> list[dict]:
    """Sự kiện mới hơn `after`, chờ tối đa `timeout` giây mà không giữ thread nào."""
    deadline = time.monotonic() + timeout
    while True:
        happened = bus.since(after)
        if happened or time.monotonic() >= deadline:
            return happened
        await asyncio.sleep(_EVENT_POLL_SECONDS)


def _start_turn(session_id: str, entry: "_Entry", message: str, turn_id: str | None = None) -> asyncio.Future:
    """
    Giữ phiên (turn_lock) NGAY lúc nhận lượt chat rồi mới xếp vào pool.

    Giữ khoá bên trong thread thì lượt đang XẾP HÀNG (pool đầy) để phiên trống:
    tin thứ hai không bị 409 mà xếp hàng chạy nối tiếp, /agent/reset xoá được
    phiên rồi lượt huấn luyện đang chờ vẫn chạy sau đó, và _sweep có thể dọn
    phiên đó. Khoá được nhả trong _run_turn (threading.Lock nhả được từ thread khác).

    Raises:
        HTTPException 409: phiên đang có lượt chạy hoặc đang chờ chạy.
    """
    if entry.turn_lock.locked():
        raise HTTPException(status_code=409, detail="Phiên này đang xử lý một tin nhắn khác.")
    # Đếm rồi giữ khoá liền nhau trong event loop (không có await ở giữa) nên không có race.
    busy = [e for e in _sessions.values() if e.turn_lock.locked()]
    if sum(1 for e in busy if e.owner == entry.owner) >= MAX_BUSY_TURNS_PER_OWNER:
        raise HTTPException(
            status_code=429, detail="Bạn đang có tin nhắn khác chưa xử lý xong ở phiên khác - đợi xong rồi gửi tiếp.",
        )
    if len(busy) >= MAX_PENDING_TURNS:
        raise HTTPException(status_code=503, detail="Agent đang quá tải, thử lại sau ít phút.")
    budget = _user_hourly_tokens()
    if budget and _spent_last_hour(entry.owner) >= budget:
        raise HTTPException(
            status_code=429,
            detail="Bạn đã dùng hết hạn mức xử lý của agent trong 1 giờ qua - thử lại sau ít phút.",
        )
    if not entry.turn_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Phiên này đang xử lý một tin nhắn khác.")
    # Lượt đang XẾP HÀNG cũng là lượt đang chạy với trang vừa tải lại (hello báo turn_id).
    entry.session.current_turn_id = turn_id
    # Tin đã nhận mà chưa vào lịch sử: nút Huỷ tự kích hoạt bấm trong lúc lượt xếp hàng thì tin này
    # là cũ hơn lần huỷ (không được dùng làm lời đồng ý bật lại).
    entry.session.incoming_user_message = True

    def never_ran() -> None:
        entry.session.current_turn_id = None
        entry.session.incoming_user_message = False
        try:
            entry.session.team.clamp_auto_marks()
        finally:
            # Lỗi ở đâu cũng phải nhả khoá, không thì phiên kẹt 409 mãi.
            entry.turn_lock.release()

    try:
        work = _TURN_POOL.submit(_run_turn, session_id, entry, message, turn_id)
    except BaseException:
        never_ran()
        raise

    def release_if_never_ran(future) -> None:
        # Bị huỷ khi còn xếp hàng (request bị huỷ, server tắt): _run_turn không bao giờ
        # chạy nên không nhả khoá - nhả ở đây, không thì phiên kẹt 409 mãi.
        if future.cancelled():
            never_ran()

    work.add_done_callback(release_if_never_ran)
    return asyncio.wrap_future(work)


def _run_turn(session_id: str, entry: _Entry, message: str, turn_id: str | None = None) -> ChatResponse:
    """
    Chạy một lượt chat. ĐỒNG BỘ - gọi qua thread, không chạy thẳng trong event loop.

    Một lượt có thể gọi LLM hàng chục lần; chạy trong event loop thì mọi request
    khác (kể cả luồng SSE) đứng chờ tới khi xong. Chỉ gọi qua _start_turn: khi
    vào đây turn_lock ĐÃ được giữ, và được nhả khi lượt xong.
    """
    session = entry.session
    tokens_before = session.usage["total_tokens"]
    try:
        start = session.events.last_seq
        reply = session.send(message, turn_id=turn_id)
    except HTTPException:
        raise
    except Exception as error:  # noqa: BLE001 - trả lỗi có cấu trúc cho frontend
        # Chi tiết đầy đủ chỉ vào log server; người dùng nhận bản đã lược.
        log_exception(logging.getLogger("agent.server"), "lượt chat lỗi")
        raise HTTPException(status_code=502, detail=describe_error(error))
    finally:
        _record_spend(entry.owner, session.usage["total_tokens"] - tokens_before)
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
    owner = await _resolve_owner(request.access_token)
    session_id, session = _get_session(request.session_id, request.access_token, owner)
    # shield: request bị huỷ thì lượt vẫn chạy nốt (như luồng SSE), không bị huỷ giữa hàng đợi.
    return await asyncio.shield(_start_turn(session_id, _sessions[session_id], request.message, request.turn_id))


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
    owner = await _resolve_owner(request.access_token)
    session_id, session = _get_session(request.session_id, request.access_token, owner)
    entry = _sessions[session_id]
    start = session.events.last_seq
    # Phát lại sự kiện frontend chưa nhận - chỉ khi vẫn là phiên cũ của nó (phiên
    # mới thì seq của frontend thuộc phiên khác, không so được).
    replay_from = start
    if request.after is not None and request.session_id == session_id:
        replay_from = max(0, min(start, request.after))

    # Bắt đầu lượt NGAY, không đợi luồng SSE được đọc: phiên đang bận thì trả 409
    # thẳng, và client ngắt trước khi đọc luồng thì lượt vẫn chạy và nhả khoá.
    turn = _start_turn(session_id, entry, request.message, request.turn_id)
    # Frontend ngắt giữa chừng thì lượt chat vẫn chạy nốt và vào lịch sử;
    # đọc exception để asyncio không cảnh báo "never retrieved".
    turn.add_done_callback(lambda task: task.cancelled() or task.exception())

    async def stream():
        # start_seq: sự kiện có seq <= mốc này là phát lại, không thuộc lượt này.
        yield _sse("session", {"session_id": session_id, "start_seq": start})
        last = replay_from
        quiet_since = time.monotonic()

        while True:
            happened = await _wait_events(session.events, last, 0.5)
            for event in happened:
                last = event["seq"]
                yield _sse(event["type"], event, event["seq"])
            if happened:
                quiet_since = time.monotonic()
            elif time.monotonic() - quiet_since >= CHAT_PING_SECONDS:
                yield ": ping\n\n"
                quiet_since = time.monotonic()

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
    owner = await _resolve_owner(request.access_token)
    entry = _find_entry(request.session_id, owner)
    if entry is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên.")

    entry.touched = time.time()
    entry.session.api.access_token = request.access_token
    bus = entry.session.events

    async def stream():
        last = request.after
        deadline = time.monotonic() + EVENTS_STREAM_SECONDS
        # Mốc seq hiện tại của phiên: frontend vừa tải lại trang mà chưa phát lại được lịch sử
        # biết những sự kiện có seq <= mốc này là CŨ (chỉ cập nhật job, không báo lại). Kèm job
        # đang theo dõi và lời hứa tự kích hoạt: phiên dài thì sự kiện của job có thể đã trôi
        # khỏi bộ đệm, thẻ job vẫn phải dựng lại được (kèm nút huỷ).
        watcher = entry.session.watcher
        yield _sse("hello", {
            "last_seq": bus.last_seq, "watching": watcher.active(), "auto_activate": watcher.auto_activate_map(),
            # Điều kiện sẽ kiểm trước khi tự kích hoạt (rỗng = bất kể điểm) - thẻ job hiện đúng.
            "auto_activate_constraints": watcher.auto_activate_constraints_map(),
            # Lượt đang chạy: trang vừa tải lại không biết turn_id của nó - phải chờ kết quả.
            "turn_id": entry.session.current_turn_id,
        })

        while time.monotonic() < deadline:
            if await http.is_disconnected():
                return
            # Không chờ quá hạn đóng kênh: frontend mở lại đúng nhịp (kèm token mới).
            happened = await _wait_events(bus, last, max(0.0, min(5.0, deadline - time.monotonic())))
            for event in happened:
                last = event["seq"]
                yield _sse(event["type"], event, event["seq"])
            if not happened:
                # Comment SSE giữ kết nối không bị proxy cắt vì im lặng.
                yield ": ping\n\n"

        # Chụp trạng thái TRƯỚC, rồi gửi nốt sự kiện còn lại: job vừa xong giữa hai lần đọc vẫn
        # có job_done trong luồng này, không bị một danh sách watching mới hơn che mất (frontend
        # thôi nghe trước khi nhận kết quả).
        watching = entry.session.watcher.active()
        auto = entry.session.watcher.auto_activate_map()
        auto_constraints = entry.session.watcher.auto_activate_constraints_map()
        for event in bus.since(last):
            last = event["seq"]
            yield _sse(event["type"], event, event["seq"])
        yield _sse("reconnect", {
            "after": last, "watching": watching, "auto_activate": auto, "auto_activate_constraints": auto_constraints,
        })

    return StreamingResponse(stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


# Phần dư ngoài nội dung file trong một request multipart: boundary, tên trường,
# data_name, access_token... 64 KB là thừa thãi, chỉ để không chặn nhầm file
# dung đúng 20 MB.
_MULTIPART_OVERHEAD = 64 * 1024
_MAX_DATASET_NAME = 100
_MAX_UPLOAD_BODY = uploads.MAX_UPLOAD_BYTES + _MULTIPART_OVERHEAD


def _limit_body(receive, limit: int):
    """
    Bọc `receive` của ASGI để đếm byte NGAY KHI nhận từ socket.

    request.form() của Starlette ghi cả file xuống file tạm trước khi trả về,
    nên đếm byte sau đó là quá muộn: gửi không kèm Content-Length (chunked)
    vẫn ghi được file vài GB xuống đĩa. Ở đây vượt trần là dừng đọc luôn.
    """
    received = 0

    async def limited():
        nonlocal received
        message = await receive()
        if message["type"] == "http.request":
            received += len(message.get("body", b""))
            if received > limit:
                raise HTTPException(
                    status_code=413,
                    detail=f"File vượt giới hạn {uploads.MAX_UPLOAD_MB} MB.",
                )
        return message

    return limited


@app.post("/agent/upload")
async def upload(request: Request) -> dict:
    """
    Nhận file dataset từ khung chat và đưa vào kho dataset của người dùng.

    Form (multipart): file, access_token, session_id (tuỳ chọn),
                      data_name (tuỳ chọn), data_type = classification | regression | time_series

    Giới hạn 20 MB được chặn HAI lớp, vì Starlette KHÔNG giới hạn dung lượng
    file (max_part_size của nó chỉ áp cho trường chữ):
      1. Content-Length, kiểm tra TRƯỚC khi đọc body - chặn sớm, rẻ.
      2. Đếm byte ngay khi nhận từ socket (_limit_body) - chặn cả khi client
         không gửi Content-Length hoặc gửi sai, trước khi kịp ghi xuống đĩa.
    """
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > _MAX_UPLOAD_BODY:
        raise HTTPException(
            status_code=413,
            detail=f"File vượt giới hạn {uploads.MAX_UPLOAD_MB} MB.",
        )

    if _UPLOADS_IN_FLIGHT.locked():
        raise HTTPException(status_code=503, detail="Đang có quá nhiều tệp được tải lên, thử lại sau ít phút.")
    async with _UPLOADS_IN_FLIGHT:
        return await _read_and_store_upload(request)


def _release_upload(entry: "_Entry") -> None:
    entry.uploads = max(0, entry.uploads - 1)


# Token nằm TRONG form nên form (tới 20 MB, ghi tạm xuống đĩa) được đọc trước khi kiểm token: giới hạn số
# upload đang xử lý cùng lúc để người chưa đăng nhập không mở hàng trăm kết nối 20 MB.
_UPLOADS_IN_FLIGHT = asyncio.Semaphore(8)


async def _read_and_store_upload(request: Request) -> dict:
    request = Request(request.scope, _limit_body(request.receive, _MAX_UPLOAD_BODY))
    try:
        form = await request.form(max_files=1, max_fields=10)
    except HTTPException:
        raise
    except Exception as error:  # noqa: BLE001 - form hỏng thì báo 400, đừng để 500
        raise HTTPException(status_code=400, detail=f"Không đọc được form tải lên: {error}")

    try:
        return await _store_upload(form)
    finally:
        # Starlette không tự đóng form của Request dựng lại ở trên: đóng để xoá
        # file tạm ngay, kể cả khi trả lỗi giữa chừng.
        await form.close()


async def _store_upload(form) -> dict:
    """Phần sau khi đã đọc form: xác thực, kiểm tra file, đưa vào kho dataset."""
    # Xác thực TRƯỚC khi đọc và kiểm tra file: người chưa đăng nhập không được
    # bắt server xử lý gì thêm. Token nằm trong form nên không kiểm sớm hơn được.
    access_token = str(form.get("access_token") or "") or None
    owner = await _resolve_owner(access_token)

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

    check = await asyncio.to_thread(uploads.check_dataset_file, file.filename or "", content)
    if not check.ok:
        raise HTTPException(status_code=check.status_code, detail=check.error)

    data_name = str(form.get("data_name") or "").strip() or uploads.default_dataset_name(check.clean_name)
    data_name = data_name[:_MAX_DATASET_NAME]

    session_id, session = _get_session(str(form.get("session_id") or "") or None, access_token, owner)

    # Gọi HTTP đồng bộ (tới 120 giây) - chạy trong thread để không chặn event
    # loop, nếu không mọi request khác kể cả luồng SSE đều đứng chờ.
    entry = _sessions[session_id]
    loop = asyncio.get_running_loop()
    entry.uploads += 1
    # Bộ đếm giảm khi THREAD gửi file thật sự xong - client ngắt (coroutine bị huỷ) thì thread vẫn đang dùng
    # HTTP client của phiên, phiên phải còn "bận" tới lúc đó.
    work = _UPLOAD_POOL.submit(functools.partial(
        tools.upload_dataset_file,
        session.api,
        filename=check.clean_name,
        content=content,
        data_name=data_name,
        data_type=data_type,
        mime_type=check.mime_type,
    ))
    work.add_done_callback(lambda _: loop.call_soon_threadsafe(_release_upload, entry))
    result = await asyncio.wrap_future(work)
    if not result["ok"] and result.get("outcome_unknown"):
        raise HTTPException(status_code=502, detail=result.get("error"))
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
        f"loại bài toán người dùng chọn khi tải lên: {dataset['type']}, file: {check.clean_name}). Dataset này "
        "đã nằm trong kho của họ. Dùng id này luôn nếu họ hỏi về nó, không cần "
        "liệt kê lại."
    )

    return {
        "ok": True,
        "session_id": session_id,
        "dataset": {**dataset, "filename": check.clean_name, "size_bytes": len(content)},
    }


@app.post("/agent/token")
async def update_token(request: TokenRequest) -> dict:
    """
    Nhận access token mới ngay khi frontend vừa làm mới phiên đăng nhập.

    Token chỉ tới agent theo request: lượt chat kéo dài qua lúc token hết hạn
    (15 phút) mà chưa có job nào được theo dõi - nên /agent/events chưa mở - thì
    agent cứ dùng token cũ và nhận 401 giữa lượt. Không chờ turn_lock: thay token
    giữa lượt chính là mục đích; lượt chat đọc token mỗi lần gọi API.
    """
    owner = await _resolve_owner(request.access_token)
    entry = _find_entry(request.session_id, owner)
    if entry is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên.")
    entry.touched = time.time()
    entry.session.api.access_token = request.access_token
    return {"ok": True}


@app.post("/agent/auto-activate")
async def auto_activate(request: AutoActivateRequest) -> dict:
    """
    Bật/tắt tự kích hoạt model khi một job đang chạy xong - nút "Huỷ tự kích hoạt" trên thẻ job.
    Không chờ turn_lock: đổi ý giữa lúc agent đang trả lời vẫn phải có hiệu lực ngay.
    """
    owner = await _resolve_owner(request.access_token)
    entry = _find_entry(request.session_id, owner)
    if entry is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên.")
    entry.touched = time.time()
    # Token vừa được xác minh là mới nhất: watcher dùng nó khi kích hoạt (token cũ có thể đã hết hạn).
    entry.session.api.access_token = request.access_token
    # Cùng một đường (có khoá) với tool set_auto_activate; ghi mốc huỷ và báo Manager ở lượt sau.
    outcome = entry.session.team.change_auto_activate(request.job_id, request.enabled, by_button=True)
    if outcome == "in_progress":
        raise HTTPException(status_code=409, detail="Model đang được kích hoạt - không huỷ được nữa.")
    if outcome == "finished":
        raise HTTPException(status_code=409, detail="Lời hứa tự kích hoạt của job này đã xử lý xong hoặc đã hết hiệu lực.")
    if outcome != "ok":
        raise HTTPException(status_code=404, detail="Job không còn được theo dõi trong phiên này.")
    return {"ok": True, "job_id": request.job_id, "auto_activate": request.enabled}


@app.post("/agent/reset")
async def reset(request: ChatRequest) -> dict:
    owner = await _resolve_owner(request.access_token)
    entry = _find_entry(request.session_id, owner)
    if entry is None:
        return {"ok": False, "detail": "Không tìm thấy phiên."}
    # Reset giữa lượt chat sẽ xoá dữ liệu chuyển giữa các agent ngay lúc chúng
    # đang dùng (start_training mất config_id) và làm mất câu trả lời của lượt đó.
    if not entry.turn_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Phiên đang xử lý một tin nhắn, thử lại sau khi xong.")
    try:
        entry.session.reset()
    finally:
        entry.turn_lock.release()
    return {"ok": True}


def main() -> None:
    uvicorn.run(
        app,
        host=os.getenv("AGENT_HOST", "0.0.0.0"),
        port=int(os.getenv("AGENT_PORT", "9500")),
    )


if __name__ == "__main__":
    main()
