"""
Chat nhiều lượt với hệ thống agent HAutoML.

    cd src/backend
    python -m agent.chat

Người dùng nói chuyện với Agent Manager. Manager uỷ thác cho 5 sub-agent
(Prompt / Data / Model / Operation / SQL - xem team.py) rồi tổng hợp câu trả lời.
Hành động thật (huấn luyện, bật / tắt model) chỉ chạy khi người dùng xác nhận ngay trong terminal.
Terminal hiện từng bước: agent nào được giao việc gì, nó gọi tool nào.

Khác `agent.cli`: cli chạy một lượt rồi thoát. Ở đây một phiên giữ nguyên lịch
sử hội thoại, phiên đăng nhập, dữ liệu đã chuyển giữa các agent (R, hồ sơ dữ
liệu, config đã kiểm) và các job đang được theo dõi nền.

Lệnh trong lúc chat:
    /cost     xem token đã dùng của cả phiên
    /tools    tool của từng agent
    /jobs     job đang được theo dõi nền
    /reset    xoá lịch sử hội thoại (vẫn giữ đăng nhập và job đang theo dõi)
    /exit     thoát
"""

# Standard libraries
import argparse
import json
import os
import threading
import time
import uuid

# Local modules
from agent import providers, skills as skills_module, tools, tracing
from agent.agent_openai import (
    MAX_STEPS,
    ContextOverflow,
    TurnBudgetExceeded,
    TurnCancelled,
    TurnDeadlineExceeded,
    describe_error,
    estimate_tokens,
    is_context_overflow,
    _new_usage,
    _print_usage,
    run_tool_loop,
    turn_token_budget,
)
from agent.api_client import HAutoMLClient
from agent.events import EventBus
from agent.prompts import MANAGER, SUBAGENTS, SYSTEM_PROMPT, title
from agent.team import AgentTeam
from agent.watcher import JobWatcher


# Ranh giới giữa câu tóm tắt và JSON chi tiết trong một dòng sự kiện job.
_EVENT_DETAIL = " Chi tiết: "


DEFAULT_TURN_DEADLINE_SECONDS = 600


def turn_deadline_seconds() -> float:
    """
    AGENT_TURN_DEADLINE_SECONDS (mặc định 600): thời gian tối đa của MỘT lượt chat (audit AG-03). Lượt bình thường
    mất vài chục giây; provider treo / lặp thì lượt dừng đúng hạn, nhả phiên và thread thay vì giữ hàng chục phút.
    """
    raw = os.getenv("AGENT_TURN_DEADLINE_SECONDS", "").strip()
    try:
        value = float(raw) if raw else DEFAULT_TURN_DEADLINE_SECONDS
    except ValueError:
        return DEFAULT_TURN_DEADLINE_SECONDS
    return value if value > 0 else DEFAULT_TURN_DEADLINE_SECONDS


def _full_turns() -> int:
    """
    Số lượt TRƯỚC lượt hiện tại giữ ĐỦ các bước tool trong lịch sử của Manager
    (AGENT_HISTORY_FULL_TURNS, mặc định 4). Lượt cũ hơn chỉ giữ câu của người
    dùng và câu trả lời cuối. Benchmark chỉ có kịch bản 1-2 lượt nên không đổi.
    """
    raw = os.getenv("AGENT_HISTORY_FULL_TURNS", "").strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else 4


# Lượt CŨ (đã gọn) giữ tối đa bấy nhiêu lượt, mỗi tin tối đa bấy nhiêu ký tự: phiên dài hàng trăm lượt
# (TTL được gia hạn liên tục) hay một tin dán cả file CSV không làm mọi lượt sau gửi lại hàng trăm nghìn token.
_MAX_OLD_TURNS = 30
_EVENT_CHARS = 8_000
_OLD_MESSAGE_CHARS = 2_000


DEFAULT_MAX_TOOL_CALLS_PER_TURN = 40


def _max_tool_calls_per_turn() -> int:
    """
    AGENT_MAX_TOOL_CALLS_PER_TURN (mặc định 40): tổng số lần gọi tool của MỘT lượt, cả Manager lẫn sub-agent. Lượt
    huấn luyện đầy đủ dùng khoảng 10-15; trần chặn trường hợp vòng lặp tool tốn tiền mà trần bước không bắt được.
    """
    raw = os.getenv("AGENT_MAX_TOOL_CALLS_PER_TURN", "").strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else DEFAULT_MAX_TOOL_CALLS_PER_TURN


DEFAULT_HISTORY_TOKEN_BUDGET = 60_000


def _history_token_budget() -> int:
    """
    AGENT_HISTORY_TOKEN_BUDGET (mặc định 60 000, ước lượng ~3 ký tự/token): lịch sử Manager vượt mức này thì kết
    quả tool cũ bị thay bằng bản tóm gọn. Đếm theo lượt thôi không đủ: 4 lượt mỗi lượt vài kết quả tool 40k ký tự
    đã đủ làm mỗi bước của Manager gửi lại hàng chục nghìn token.
    """
    raw = os.getenv("AGENT_HISTORY_TOKEN_BUDGET", "").strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else DEFAULT_HISTORY_TOKEN_BUDGET


_DIGEST_NOTE = "Kết quả đầy đủ đã lược khỏi lịch sử; gọi lại tool nếu cần."
_DIGEST_KEYS = ("ok", "status_code", "result_truncated")


def _tool_digest(content: str) -> str:
    """
    Bản tóm gọn của một kết quả tool cũ: ok / lỗi / mọi ID (dataset_id, config_id, job_id...). Thứ Manager cần
    nhớ qua các lượt là ID và kết quả đúng sai, không phải bảng schema hay báo cáo dài.
    """
    try:
        data = json.loads(content)
    except (TypeError, ValueError):
        data = None
    if not isinstance(data, dict):
        return json.dumps({"masked": True, "note": _DIGEST_NOTE, "preview": _clip(str(content), 200)}, ensure_ascii=False)
    digest = {key: data[key] for key in _DIGEST_KEYS if key in data}
    if data.get("error") is not None:
        digest["error"] = _clip(str(data["error"]), 300)
    for key, value in data.items():
        if key.endswith(("_id", "_ids")) and isinstance(value, (str, int, list)):
            digest[key] = value
    configs = [c.get("config_id") for c in data.get("configs") or [] if isinstance(c, dict) and c.get("config_id")]
    if configs:
        digest["config_ids"] = configs
    pending = [a.get("action_id") for a in data.get("awaiting_confirmation") or [] if isinstance(a, dict)]
    if pending:
        digest["awaiting_confirmation_action_ids"] = pending
    digest.update(masked=True, note=_DIGEST_NOTE)
    return json.dumps(digest, ensure_ascii=False, default=str)


def _is_digest(content) -> bool:
    return isinstance(content, str) and '"masked": true' in content and _DIGEST_NOTE in content


_CONTEXT_OVERFLOW_AFTER_TOOLS_MESSAGE = (
    "Yêu cầu này vượt giới hạn ngữ cảnh của mô hình sau khi đã chạy một số bước (các việc đã làm vẫn giữ nguyên). "
    "Lịch sử sẽ được rút gọn - bạn gửi lại yêu cầu, hoặc chia nhỏ hơn."
)
_CONTEXT_OVERFLOW_MESSAGE = (
    "Cuộc trò chuyện đã quá dài so với giới hạn của mô hình, kể cả sau khi rút gọn. "
    "Bấm 'Cuộc trò chuyện mới' để tiếp tục."
)


def _clip(text: str, limit: int = _OLD_MESSAGE_CHARS) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + f"…(lược {len(text) - limit} ký tự)"


def _strip_event_details(text: str) -> str:
    """Bỏ phần JSON chi tiết của dòng sự kiện job, giữ câu tóm tắt."""
    return "\n".join(line.split(_EVENT_DETAIL)[0] for line in (text or "").splitlines())

class ChatSession:
    """
    Một phiên chat: lịch sử hội thoại của Agent Manager + mọi thứ sống xuyên suốt.

    HAutoMLClient sống lâu là lý do không phải đăng nhập lại - access_token và
    user_id nằm trong nó. Watcher dùng chung client này, nên khi frontend gửi
    token mới, job đang theo dõi cũng dùng được ngay.
    """

    def __init__(
        self,
        base_url=None,
        provider=None,
        model=None,
        verbose=True,
        access_token: str | None = None,
        auto_login: bool = True,
        api: HAutoMLClient | None = None,
    ):
        """
        Args:
            access_token: Token của người dùng ĐÃ đăng nhập. Frontend truyền
                token của phiên web xuống đây - đó là đường dùng thật.
            auto_login: Chỉ dành cho chạy ở terminal. Khi không có
                access_token, tự đăng nhập bằng AGENT_USER trong .env.
                Frontend PHẢI đặt False: nếu không, người dùng chưa đăng nhập
                sẽ vô tình thao tác dưới danh nghĩa tài khoản trong .env.
            api: Client dựng sẵn - để test thay backend thật bằng bản giả.
        """
        # LLM dựng LƯỜI, lúc gửi tin đầu tiên. Không dựng ngay ở đây vì có việc
        # không cần LLM (tải dataset lên): nếu key LLM thiếu hoặc hết hạn mức thì
        # nút tải file không được chết theo.
        self._provider, self._model = provider, model
        self._config = None
        self._llm = None
        self.api = api or HAutoMLClient(base_url)
        self.verbose = verbose
        self.usage = _new_usage()
        # Trần token mỗi lượt chat (AGENT_TURN_TOKEN_BUDGET) và mốc đầu lượt.
        self.turn_budget = turn_token_budget()
        self._turn_start = 0
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Sự kiện xảy ra ngoài hội thoại (tải dataset, job huấn luyện xong).
        # Ghép vào đầu tin nhắn kế tiếp thay vì chèn thành tin nhắn riêng: hai
        # tin "user" liền nhau dễ bị một số provider từ chối hoặc gộp sai.
        # Có khoá vì watcher ghi vào từ thread nền.
        self.pending_events: list[str] = []
        self._pending_lock = threading.Lock()
        # turn_id của lượt đang chạy (None khi rảnh) - /agent/events báo trong `hello`.
        self.current_turn_id: str | None = None
        # Hạn của lượt đang chạy (time.monotonic) và cờ "người dùng bấm Dừng" (audit AG-03). Cờ chỉ xoá khi lượt
        # KẾT THÚC: bấm Dừng lúc lượt còn xếp hàng thì lượt đó dừng ngay ở bước đầu.
        self._turn_deadline: float | None = None
        self.cancel_requested = threading.Event()
        # Có lượt chat đang chạy hoặc đang xếp hàng (server đặt lúc nhận lượt, xoá khi lượt xong / không bao giờ
        # chạy): nút Dừng chỉ có hiệu lực lúc này - turn_lock còn bị giữ bởi xác nhận / reset nữa.
        self.turn_pending = False

        # Gom các lượt chat cùng phiên thành một Session trên Langfuse. server.py
        # đặt lại bằng session_id của nó để hai bên khớp nhau.
        self.trace_session_id = uuid.uuid4().hex
        self.events = EventBus()
        if verbose:
            self.events.subscribe(_print_event)
        self.team = AgentTeam(self)
        self.watcher = JobWatcher(self.api, self.events.emit, on_finish=self._on_job_finished)

        # LLM không có tool đăng nhập, nên token phải được đặt ở đây.
        if access_token:
            self.api.access_token = access_token
            self.auth = {"ok": True, "note": "Dùng token của phiên đã đăng nhập."}
        elif auto_login:
            self.auth = tools.ensure_login(self.api)
        else:
            self.auth = {
                "ok": False,
                "error": "Thiếu access_token. Người dùng cần đăng nhập trước.",
            }

    @property
    def config(self):
        if self._config is None:
            self._config = providers.resolve(self._provider, self._model)
        return self._config

    @property
    def llm(self):
        if self._llm is None:
            self._llm = providers.build_client(self.config)
        return self._llm

    @llm.setter
    def llm(self, client) -> None:
        self._llm = client

    def close(self) -> None:
        self.watcher.stop()
        self.api.close()

    def reset(self) -> None:
        """
        Xoá lịch sử và dữ liệu chuyển giữa các agent, nhưng giữ đăng nhập và
        job đang theo dõi - job vẫn đang chạy thật trên backend.
        """
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        with self._pending_lock:
            self.pending_events.clear()
        self.team.reset()

    def add_event(self, text: str) -> None:
        """Ghi một sự kiện để lượt chat sau Manager biết. KHÔNG gọi LLM, không tốn token."""
        with self._pending_lock:
            # Lỗi job / tóm tắt có thể chứa giá trị ô dữ liệu dài: không để một sự kiện chiếm cả context.
            self.pending_events.append(_clip(text, _EVENT_CHARS))

    @property
    def logged_in(self) -> bool:
        return bool(self.api.access_token)

    def compact_history(self, full_turns: int | None = None, force_mask: bool = False) -> None:
        """
        Gọn lịch sử: lượt cũ chỉ còn câu người dùng + câu trả lời cuối của Manager.

        Mỗi bước của Manager gửi lại TOÀN BỘ lịch sử, và số token đó tính vào trần
        của lượt. Không gọn thì phiên dài (web giữ phiên tới 1 giờ, 26 giờ khi có
        job) sớm muộn vượt trần mỗi lượt, hoặc vượt context của model - lượt lỗi bị
        bỏ khỏi lịch sử nhưng lịch sử vẫn dài như cũ, nên mọi lượt sau lỗi y hệt.

        Bỏ assistant tool_calls cùng các tool message của nó nên chuỗi tin vẫn hợp
        lệ. ID job/config đã nằm trong câu trả lời cuối và trong team.handoff.

        Ngoài số lượt, lịch sử còn có trần TOKEN (AGENT_HISTORY_TOKEN_BUDGET): vượt trần (hoặc force_mask) thì
        mọi kết quả tool cũ được thay bằng bản tóm gọn giữ ID, rồi giảm dần số lượt giữ đầy đủ.
        """
        keep = full_turns or _full_turns()
        self._compact_turns(keep)
        budget = _history_token_budget()
        if force_mask or estimate_tokens(self.messages) > budget:
            self._mask_tool_results()
        while estimate_tokens(self.messages) > budget and keep > 1:
            keep -= 1
            self._compact_turns(keep)

    def _mask_tool_results(self) -> None:
        """Thay nội dung mọi tool message trong lịch sử bằng bản tóm gọn (cấu trúc tool_calls giữ nguyên)."""
        for message in self.messages:
            if message.get("role") == "tool" and not _is_digest(message.get("content")):
                message["content"] = _tool_digest(message.get("content") or "")

    def _compact_turns(self, keep: int) -> None:
        """Giữ đủ các bước tool của `keep` lượt gần nhất; lượt cũ hơn chỉ còn câu hỏi và câu trả lời."""
        starts = [i for i, m in enumerate(self.messages) if m.get("role") == "user"]
        if len(starts) <= keep:
            return
        cut = starts[-keep]
        compacted = []
        for message in self.messages[1:cut]:
            role = message.get("role")
            if role == "user":
                compacted.append({"role": "user", "content": _clip(_strip_event_details(message.get("content")))})
            elif role == "assistant" and not message.get("tool_calls"):
                compacted.append({"role": "assistant", "content": _clip(message.get("content") or "(không có nội dung)")})
        starts_old = [i for i, m in enumerate(compacted) if m["role"] == "user"]
        if len(starts_old) > _MAX_OLD_TURNS:
            dropped = len(starts_old) - _MAX_OLD_TURNS
            compacted = [
                {"role": "user", "content": f"(Hệ thống đã lược bớt {dropped} lượt cũ nhất của cuộc trò chuyện.)"},
                {"role": "assistant", "content": "(Đã ghi nhận.)"},
                *compacted[starts_old[-_MAX_OLD_TURNS]:],
            ]
        self.messages = [self.messages[0], *compacted, *self.messages[cut:]]

    def recent_user_messages(self, limit: int) -> list[str]:
        """
        Vài tin gần nhất của người dùng, cho sub-agent không thấy lịch sử.

        Bỏ phần JSON chi tiết của sự kiện job: Manager cần nó để trả lời, còn
        Prompt Agent chỉ cần câu tóm tắt - giữ lại thì mỗi lần gọi tốn thêm
        hàng nghìn token cho dữ liệu nó không dùng.
        """
        recent = [m["content"] for m in self.messages if m.get("role") == "user"][-limit:]
        return [_strip_event_details(text) for text in recent]

    def _on_job_finished(self, summary: dict) -> None:
        """Watcher gọi khi job kết thúc: để lượt chat kế tiếp Manager biết kết quả."""
        job_id = summary.get("job_id")
        if summary.get("summary_error"):
            activation = summary.get("activation")
            activated = "" if activation is None else (
                " Model ĐÃ được tự kích hoạt." if activation.get("ok") else f" Model CHƯA được kích hoạt: {activation.get('error')}"
            )
            text = (
                f"Job {job_id} đã kết thúc (status {summary.get('status')}) nhưng hệ thống gặp lỗi: "
                f"{str(summary['summary_error']).rstrip('.')}. Dùng get_job_info để xem, đừng suy diễn điểm hay "
                f"kiểm định.{activated}"
            )
        elif summary.get("status") == 1:
            # watcher chỉ kèm "verification" khi người dùng CÓ đặt ràng buộc.
            verification = summary.get("verification")
            checks = (verification or {}).get("checks") or []
            unchecked = [c["metric"] for c in checks if c.get("passed") is None]
            if not verification:
                judged = "người dùng không đặt ràng buộc nào"
            elif verification.get("passed") is None:
                checked_ok = [c["metric"] for c in checks if c.get("passed") is True]
                judged = (
                    "CHƯA kiểm đủ - job không có điểm cho metric "
                    f"{', '.join(unchecked)} mà người dùng đặt ràng buộc"
                    + (f" (các ràng buộc kiểm được - {', '.join(checked_ok)} - đều đạt)" if checked_ok else "")
                    + "; đừng nói là đạt mọi ràng buộc"
                )
            else:
                judged = (
                    "ĐẠT các ràng buộc người dùng đặt ra"
                    if verification["passed"]
                    else "KHÔNG đạt ràng buộc người dùng đặt ra"
                )
                if verification["passed"] and summary.get("score_source") != "holdout":
                    # Audit AG-02: "đạt" theo điểm CV không phải cam kết hiệu năng thật.
                    judged += (
                        " - nhưng THEO ĐIỂM CROSS-VALIDATION trên chính dữ liệu dùng để chọn model, có thể lạc quan; "
                        "đừng nói như cam kết hiệu năng thật"
                        if summary.get("score_source") == "cv" else
                        " - nhưng không rõ điểm có đo trên tập kiểm tra riêng không, có thể lạc quan"
                    )
                if unchecked:
                    judged += f" (riêng {', '.join(unchecked)} không kiểm được vì job không có điểm)"
            if verification and summary.get("problem_type") == "time_series":
                judged += f". {tools.FORECAST_SCORE_NOTE.rstrip('.')}"
            # Chỉ có khi người dùng dặn "train xong kích hoạt luôn" (watcher tự kích hoạt).
            activation = summary.get("activation")
            if activation is None:
                activated = ""
            elif activation.get("ok"):
                activated = " Model ĐÃ được tự kích hoạt theo yêu cầu của người dùng, dự đoán được ngay."
            else:
                activated = f" Model CHƯA được kích hoạt: {activation.get('error')}"
                if activation.get("needs_confirmation") and self.team.propose_activation_after_job(summary):
                    activated += " Đã hiện thẻ xác nhận KÍCH HOẠT cho người dùng - họ bấm thì model mới được bật."
            source = f" Nguồn điểm: {summary.get('score_note')}" if summary.get("score_note") else ""
            text = (
                f"Job {job_id} đã huấn luyện xong: model tốt nhất {summary.get('best_model')}, "
                f"{summary.get('metric_sort')} = {summary.get('best_score')}; kiểm định: {judged}.{activated}{source} "
                "Đủ các metric của model tốt nhất nằm trong best_model_scores, xếp hạng các "
                f"model trong leaderboard.{_EVENT_DETAIL}{json.dumps(summary, ensure_ascii=False, default=str)}"
            )
        elif summary.get("reason") == "auth_lost":
            text = (
                f"Job {job_id}: chưa biết kết quả vì mất phiên đăng nhập. Agent sẽ theo dõi tiếp khi người dùng "
                "đăng nhập lại (lời hứa tự kích hoạt, nếu có, vẫn giữ). KHÔNG tạo lại job."
            )
        else:
            text = f"Job {job_id} không hoàn tất: {summary.get('error') or 'không rõ lý do'}."
            if summary.get("auto_activate_skipped"):
                text += (
                    " Model CHƯA được tự kích hoạt và lời hứa tự kích hoạt đã HẾT HIỆU LỰC (thôi theo dõi). "
                    "Báo người dùng: khi job xong cần kích hoạt thủ công (hoặc nhờ agent dùng activate_model)."
                )
        self.add_event(text)

    def time_left(self) -> float | None:
        """Số giây còn lại của lượt đang chạy (None = không trong lượt nào)."""
        return None if self._turn_deadline is None else self._turn_deadline - time.monotonic()

    def request_cancel(self, turn_id: str | None = None) -> bool:
        """
        Người dùng bấm Dừng: lượt đang chạy (hoặc đang xếp hàng) dừng ở ranh giới bước kế tiếp. False nếu không có
        lượt nào, hoặc turn_id không khớp lượt đang chạy (cờ huỷ cũ không được giết lượt SAU).
        """
        if not self.turn_pending:
            return False
        if turn_id and self.current_turn_id and turn_id != self.current_turn_id:
            return False
        self.cancel_requested.set()
        return True

    def end_turn(self) -> None:
        """Lượt kết thúc (hay không bao giờ chạy): thôi nhận nút Dừng, xoá cờ huỷ."""
        self.turn_pending = False
        self.current_turn_id = None
        self._turn_deadline = None
        self.cancel_requested.clear()

    def count_tool_call(self, name: str) -> str | None:
        """Đếm một lần gọi tool của lượt; quá trần thì trả câu lỗi (tool không chạy), không thì None."""
        limit = _max_tool_calls_per_turn()
        used = getattr(self, "_turn_tool_calls", 0)
        if used >= limit:
            return (
                f"Lượt này đã gọi {used} tool, chạm trần {limit}. KHÔNG gọi thêm tool; tổng hợp kết quả đã có "
                "và trả lời ngay."
            )
        self._turn_tool_calls = used + 1
        return None

    def check_budget(self, agent: str) -> None:
        """Gọi trước MỖI lời gọi LLM trong lượt, của mọi agent: trần token, hạn lượt, và nút Dừng."""
        if self.cancel_requested.is_set():
            raise TurnCancelled(f"người dùng đã bấm Dừng (trước khi {title(agent)} gọi LLM)")
        left = self.time_left()
        if left is not None and left <= 0:
            raise TurnDeadlineExceeded(
                f"lượt chat chạy quá {int(turn_deadline_seconds())} giây (dừng trước khi {title(agent)} gọi LLM)"
            )
        spent = self.usage["total_tokens"] - self._turn_start
        if spent >= self.turn_budget:
            raise TurnBudgetExceeded(
                f"đã dùng {spent} token, vượt trần {self.turn_budget} của một lượt "
                f"(dừng trước khi {title(agent)} gọi LLM)"
            )

    def send(self, user_message: str, turn_id: str | None = None) -> str:
        """Như _send; giữ turn_id của lượt ĐANG chạy để trang vừa tải lại còn chờ được kết quả."""
        self.current_turn_id = turn_id
        self.turn_pending = True
        self._turn_deadline = time.monotonic() + turn_deadline_seconds()
        try:
            return self._send(user_message, turn_id)
        finally:
            self.end_turn()

    def _run_manager(self, tool_schemas: list, dispatch: dict, user_message: str) -> str:
        """Một lần chạy vòng tool-calling của Manager trên self.messages (tin user đã nằm cuối lịch sử)."""
        with tracing.turn(
            MANAGER, input=user_message, session_id=self.trace_session_id, user_id=self.api.user_id,
        ) as observation:
            answer = run_tool_loop(
                self.llm,
                self.config.model,
                self.messages,
                tool_schemas,
                dispatch,
                self.api,
                self.usage,
                agent=MANAGER,
                emit=self.events.emit,
                max_steps=MAX_STEPS,
                check_budget=self.check_budget,
                time_left=self.time_left,
                cancel_event=self.cancel_requested,
                before_tool=self.count_tool_call,
            )
            if answer is None:
                answer = (
                    f"(Tôi đã chạy quá {MAX_STEPS} bước mà chưa xong. "
                    "Thử hỏi lại theo cách cụ thể hơn.)"
                )
                self.messages.append({"role": "assistant", "content": answer})
            tracing.end(observation, output=answer)
        return answer

    def _send(self, user_message: str, turn_id: str | None = None) -> str:
        """
        Gửi một câu, Manager chạy (và uỷ thác) cho tới khi trả lời xong.

        turn_id: mã lượt do frontend tạo, gắn vào turn_start / turn_done / turn_failed.
            Luồng lượt chat đứt giữa chừng thì frontend nhận câu trả lời qua kênh nền và
            ghép đúng lượt theo mã này (seq không đủ: phiên đổi thì seq bắt đầu lại).
        """
        # Lượt nào cũng phải kết thúc bằng turn_done hoặc turn_failed - kể cả khi hỏng
        # ngay ở bước chuẩn bị - không thì frontend mất luồng sẽ chờ mãi.
        try:
            tool_schemas, dispatch = self.team.tools_for(MANAGER)
            # Lượt trước vượt context giữa chừng: rút gọn mạnh ngay, không chờ vượt trần token mặc định.
            force_mask, self._force_mask_next = getattr(self, "_force_mask_next", False), False
            self.compact_history(full_turns=1 if force_mask else None, force_mask=force_mask)
        except Exception as error:
            self.events.emit("turn_failed", agent=MANAGER, error=describe_error(error), turn_id=turn_id)
            raise

        with self._pending_lock:
            events, self.pending_events = self.pending_events, []
        if events:
            # Gộp khoảng trắng: dòng xuống trong sự kiện (vd traceback trong lỗi job) mà để
            # nguyên thì các dòng sau không có tiền tố [Sự kiện] và bị coi là lời người dùng.
            notes = "\n".join(f"[Sự kiện] {' '.join(event.split())}" for event in events)
            user_message = f"{notes}\n\n{user_message}"

        before = len(self.messages)
        jobs_before = set(self.team.handoff.jobs)
        self.team.begin_turn()
        self._turn_start = self.usage["total_tokens"]
        self._turn_tool_calls = 0
        self.messages.append({"role": "user", "content": user_message})
        self.events.emit("turn_start", agent=MANAGER, turn_id=turn_id)

        # Gộp mọi bước của lượt này - kể cả của sub-agent - vào một trace, để
        # Langfuse cộng được tổng chi phí và thấy được ai làm gì (xem tracing.py).
        try:
            try:
                answer = self._run_manager(tool_schemas, dispatch, user_message)
            except Exception as first:  # noqa: BLE001 - chỉ xử lý riêng lỗi vượt context, còn lại raise như cũ
                if not is_context_overflow(first):
                    raise
                if any(m.get("role") == "tool" for m in self.messages[before:]):
                    # Lượt đã chạy tool (có thể đã nhập dataset, tạo thẻ xác nhận): chạy lại là làm trùng việc.
                    # Đi theo đường lỗi thường (báo lại việc đã làm qua after_failed_turn); lượt sau tự rút gọn.
                    self._force_mask_next = True
                    raise ContextOverflow(_CONTEXT_OVERFLOW_AFTER_TOOLS_MESSAGE) from first
                # Provider từ chối vì lịch sử quá dài: bỏ dở lượt này, rút gọn mạnh rồi chạy lại ĐÚNG một lần.
                # Không làm vậy thì mọi lượt sau lỗi y hệt cho tới khi người dùng reset.
                del self.messages[before:]
                self.compact_history(full_turns=1, force_mask=True)
                before = len(self.messages)
                self.messages.append({"role": "user", "content": user_message})
                try:
                    answer = self._run_manager(tool_schemas, dispatch, user_message)
                except Exception as second:  # noqa: BLE001
                    if is_context_overflow(second):
                        raise ContextOverflow(_CONTEXT_OVERFLOW_MESSAGE) from second
                    raise
        except TurnBudgetExceeded as error:
            # Lịch sử vẫn hợp lệ (dừng ở đầu vòng lặp / trước lời gọi LLM), chỉ cần thêm câu trả lời.
            # Việc sub-agent đã làm xong (vd thẻ xác nhận đã tạo) vẫn giữ nguyên.
            if isinstance(error, TurnCancelled):
                answer = "Đã dừng theo yêu cầu của bạn. Những việc đã làm xong trước lúc dừng vẫn giữ nguyên."
                self.events.emit("turn_cancelled", agent=MANAGER, error=str(error))
            elif isinstance(error, TurnDeadlineExceeded):
                answer = (
                    f"Yêu cầu này chạy quá lâu nên tôi đã dừng lại ({error}). Bạn thử lại sau, hoặc chia thành từng bước."
                )
                self.events.emit("turn_budget_exceeded", agent=MANAGER, error=str(error))
            else:
                answer = (
                    "Yêu cầu này tốn quá nhiều xử lý nên tôi đã dừng lại "
                    f"({error}). Bạn thử hỏi cụ thể hơn, hoặc chia thành từng bước."
                )
                self.events.emit("turn_budget_exceeded", agent=MANAGER, error=str(error))
            self.messages.append({"role": "assistant", "content": answer})
        except Exception as error:
            # Bỏ dở lượt này khỏi lịch sử, kể cả tin của người dùng: để lại thì
            # lượt sau có hai tin "user" liền nhau. Sự kiện chưa kịp đọc thì
            # trả lại hàng đợi.
            del self.messages[before:]
            with self._pending_lock:
                self.pending_events[:0] = events
            # Job đã tạo trong lượt lỗi vẫn chạy thật trên backend. Lịch sử của lượt
            # bị bỏ nên phải báo lại, không thì người dùng gửi lại câu cũ là Manager
            # tạo thêm một job trùng chạy hàng giờ.
            for note in self.team.after_failed_turn():
                self.add_event(note)
            created = [job_id for job_id in self.team.handoff.jobs if job_id not in jobs_before]
            if created:
                self.add_event(
                    f"Lượt chat trước bị lỗi giữa chừng NHƯNG đã tạo job {', '.join(created)}; job vẫn "
                    "chạy nền và đang được theo dõi. KHÔNG tạo lại job cho cùng yêu cầu đó - báo người "
                    "dùng job đã chạy."
                )
            # Frontend mất luồng lượt chat giữa chừng chỉ còn chờ sự kiện kết thúc lượt
            # trên kênh nền: lượt lỗi cũng phải có sự kiện, không thì nó chờ mãi.
            self.events.emit("turn_failed", agent=MANAGER, error=describe_error(error), turn_id=turn_id)
            raise

        # Kèm câu trả lời: sự kiện nằm trong bộ đệm và được phát lại, nên luồng lượt chat
        # đứt giữa chừng (đổi wifi, máy ngủ) thì frontend vẫn nhận được câu trả lời này
        # qua kênh nền - lượt chat chạy xong trên server và đã vào lịch sử của agent.
        self.events.emit(
            "turn_done", agent=MANAGER, total_tokens=self.usage["total_tokens"], reply=answer, turn_id=turn_id,
        )
        return answer


def _print_event(event: dict) -> None:
    """In tiến độ ra terminal - cùng các sự kiện mà frontend nhận qua SSE."""
    kind = event["type"]
    agent = event.get("agent")
    sub = agent in SUBAGENTS

    if kind == "agent_start":
        task = " ".join(str(event.get("task", "")).split())
        print(f"  ▸ {title(agent)}: {task[:110]}")
    elif kind == "agent_done" and not event.get("ok"):
        print(f"  ◂ {title(agent)} hỏng: {event.get('error')}")
    elif kind == "tool_call" and not str(event.get("name", "")).startswith("ask_"):
        shown = json.dumps(event.get("arguments") or {}, ensure_ascii=False)
        mark = "✓" if event.get("ok") else f"✗ {event.get('error')}"
        print(f"  {'    ' if sub else ''}· {event['name']}({shown[:100]}) {mark}")
    elif kind == "config_checked":
        mark = "hợp lệ" if event.get("ok") else f"KHÔNG hợp lệ: {event.get('errors')}"
        print(f"      ⚙ validate_config: {mark}")
    elif kind in ("job_started", "job_status", "job_done", "job_failed", "job_watch_timeout"):
        details = {k: v for k, v in event.items() if k not in ("seq", "type", "time", "agent", "config")}
        print(f"  [job] {kind}: {json.dumps(details, ensure_ascii=False, default=str)[:200]}")


def _ask_pending(session: ChatSession) -> None:
    """
    Thẻ xác nhận trong terminal: hành động thật (huấn luyện, bật / tắt model, bật tự kích hoạt) chỉ chạy khi
    người dùng gõ đúng lựa chọn ở đây - giống nút Xác nhận trên web, LLM không tự làm được.
    """
    from agent.actions import ActionError
    from agent.team import _describe_action

    for action in session.team.actions.pending():
        offers_auto = bool((action.get("offers") or {}).get("auto_activate"))
        print(f"  [xác nhận] {_describe_action(action)}")
        print(f"    {json.dumps(action.get('summary') or {}, ensure_ascii=False, default=str)[:400]}")
        options = "c = xác nhận" + (", a = xác nhận + tự kích hoạt khi xong" if offers_auto else "") + ", n = từ chối"
        try:
            choice = input(f"    ({options}, Enter = để sau) > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        try:
            if choice in {"c", "a"} and (choice == "c" or offers_auto):
                result = session.team.confirm_action(action["action_id"], action["token"], auto_activate=choice == "a")
                print(f"    -> {'đã thực hiện' if result.get('ok') else 'không thực hiện được: ' + str(result.get('error'))}\n")
            elif choice == "n":
                session.team.reject_action(action["action_id"], action["token"])
                print("    -> đã từ chối\n")
        except ActionError as error:
            print(f"    -> {error}\n")


def _print_tools() -> None:
    for agent in (MANAGER, *SUBAGENTS):
        skill = skills_module.get_skill(agent)
        print(f"\n{title(agent)} ({len(skill.tools)} tool):")
        for name in skill.tools:
            print(f"  {name}")
    print()


def _print_banner(session: ChatSession) -> None:
    print("=" * 66)
    print("  HAutoML Agent - chat")
    print("=" * 66)
    print(f"  Model  : {session.config.name} / {session.config.model}")
    print(f"  Backend: {session.api.base_url}")
    print("  Agent  : Manager → Prompt · Data · Model · Operation · SQL")
    if providers.tracing_enabled():
        print("  Langfuse: đang theo dõi chi phí")
    print()
    if session.auth.get("ok"):
        print("  Đăng nhập: tự động (AGENT_USER trong .env)")
    else:
        print(f"  ĐĂNG NHẬP LỖI: {session.auth.get('error')}")
    print()
    print("  Lệnh: /cost  /tools  /jobs  /reset  /exit")
    print("  Gõ tiếng Việt bình thường, ví dụ:")
    print('    "tôi có dataset nào"')
    print('    "dataset đó có những cột gì"')
    print('    "huấn luyện mô hình trên dataset đó, accuracy trên 0.9"')
    print("=" * 66 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat nhiều lượt với agent HAutoML")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--quiet", action="store_true", help="Không hiện các bước của agent")
    args = parser.parse_args()

    session = ChatSession(
        base_url=args.base_url,
        provider=args.provider,
        model=args.model,
        verbose=not args.quiet,
    )
    _print_banner(session)

    try:
        while True:
            try:
                line = input("Bạn > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not line:
                continue

            if line in {"/exit", "/quit"}:
                break
            if line == "/cost":
                _print_usage(session.usage)
                continue
            if line == "/tools":
                _print_tools()
                continue
            if line == "/jobs":
                active = session.watcher.active()
                print(f"  ({'đang theo dõi: ' + ', '.join(active) if active else 'không có job nào đang theo dõi'})\n")
                continue
            if line == "/reset":
                session.reset()
                state = "vẫn đang đăng nhập" if session.logged_in else "chưa đăng nhập"
                print(f"  (đã xoá lịch sử hội thoại, {state})\n")
                continue
            if line.startswith("/"):
                print("  (lệnh không rõ. Có: /cost /tools /jobs /reset /exit)\n")
                continue

            try:
                answer = session.send(line)
            except Exception as error:  # noqa: BLE001 - phiên chat không được chết
                print(f"\nAgent > (lỗi) {type(error).__name__}: {error}\n")
                continue

            print(f"\nAgent > {answer}\n")
            _ask_pending(session)
    finally:
        if session.usage["calls"]:
            print("\nTổng cả phiên:")
            _print_usage(session.usage)
        if session.watcher.active():
            print("Job vẫn chạy nền trên backend - mở lại chat và hỏi để xem kết quả.")
        session.close()
        _flush_tracer()
        print("Tạm biệt.")


def _flush_tracer() -> None:
    """Tiến trình sắp thoát: phải flush không thì trace cuối bị mất."""
    tracer = providers.get_tracer()
    if tracer is not None:
        tracer.flush()


if __name__ == "__main__":
    main()
