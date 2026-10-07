"""
Chat nhiều lượt với hệ thống agent HAutoML.

    cd src/backend
    python -m agent.chat

Người dùng nói chuyện với Agent Manager. Manager uỷ thác cho 4 sub-agent
(Prompt / Data / Model / Operation - xem team.py) rồi tổng hợp câu trả lời.
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
import threading
import uuid

# Local modules
from agent import providers, skills as skills_module, tools, tracing
from agent.agent_openai import MAX_STEPS, _new_usage, _print_usage, run_tool_loop
from agent.api_client import HAutoMLClient
from agent.events import EventBus
from agent.prompts import MANAGER, SUBAGENTS, SYSTEM_PROMPT, title
from agent.team import AgentTeam
from agent.watcher import JobWatcher


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
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Sự kiện xảy ra ngoài hội thoại (tải dataset, job huấn luyện xong).
        # Ghép vào đầu tin nhắn kế tiếp thay vì chèn thành tin nhắn riêng: hai
        # tin "user" liền nhau dễ bị một số provider từ chối hoặc gộp sai.
        # Có khoá vì watcher ghi vào từ thread nền.
        self.pending_events: list[str] = []
        self._pending_lock = threading.Lock()

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
            self.pending_events.append(text)

    @property
    def logged_in(self) -> bool:
        return bool(self.api.access_token)

    def recent_user_messages(self, limit: int) -> list[str]:
        return [m["content"] for m in self.messages if m.get("role") == "user"][-limit:]

    def _on_job_finished(self, summary: dict) -> None:
        """Watcher gọi khi job kết thúc: để lượt chat kế tiếp Manager biết kết quả."""
        job_id = summary.get("job_id")
        if summary.get("status") == 1:
            verdict = (summary.get("verification") or {}).get("passed")
            judged = {
                True: "ĐẠT các ràng buộc người dùng đặt ra",
                False: "KHÔNG đạt ràng buộc người dùng đặt ra",
                None: "không có ràng buộc nào để kiểm",
            }[verdict]
            text = (
                f"Job {job_id} đã huấn luyện xong: model tốt nhất {summary.get('best_model')}, "
                f"{summary.get('metric_sort')} = {summary.get('best_score')}; kiểm định: {judged}. "
                f"Chi tiết: {json.dumps(summary, ensure_ascii=False, default=str)}"
            )
        else:
            text = f"Job {job_id} không hoàn tất: {summary.get('error') or 'không rõ lý do'}."
        self.add_event(text)

    def send(self, user_message: str) -> str:
        """Gửi một câu, Manager chạy (và uỷ thác) cho tới khi trả lời xong."""
        tool_schemas, dispatch = self.team.tools_for(MANAGER)

        with self._pending_lock:
            events, self.pending_events = self.pending_events, []
        if events:
            notes = "\n".join(f"[Sự kiện] {event}" for event in events)
            user_message = f"{notes}\n\n{user_message}"

        before = len(self.messages)
        self.messages.append({"role": "user", "content": user_message})
        self.events.emit("turn_start", agent=MANAGER)

        # Gộp mọi bước của lượt này - kể cả của sub-agent - vào một trace, để
        # Langfuse cộng được tổng chi phí và thấy được ai làm gì (xem tracing.py).
        try:
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
                )
                if answer is None:
                    answer = (
                        f"(Tôi đã chạy quá {MAX_STEPS} bước mà chưa xong. "
                        "Thử hỏi lại theo cách cụ thể hơn.)"
                    )
                tracing.end(observation, output=answer)
        except Exception:
            # Bỏ dở lượt này khỏi lịch sử, kể cả tin của người dùng: để lại thì
            # lượt sau có hai tin "user" liền nhau. Sự kiện chưa kịp đọc thì
            # trả lại hàng đợi.
            del self.messages[before:]
            with self._pending_lock:
                self.pending_events[:0] = events
            raise

        self.events.emit("turn_done", agent=MANAGER, total_tokens=self.usage["total_tokens"])
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
    print("  Agent  : Manager → Prompt · Data · Model · Operation")
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
