"""
Chat nhiều lượt với agent HAutoML.

    cd src/backend
    python -m agent.chat

Khác `agent.cli`: cli chạy một lượt rồi thoát, mỗi lần phải đăng nhập lại từ
đầu. Ở đây một phiên chat giữ nguyên lịch sử hội thoại VÀ phiên đăng nhập, nên
đăng nhập một lần rồi hỏi tiếp bao nhiêu câu cũng được - agent nhớ ngữ cảnh và
không tốn thêm lượt login.

Lệnh trong lúc chat:
    /cost     xem token đã dùng của cả phiên
    /tools    liệt kê tool agent đang có
    /reset    xoá lịch sử hội thoại (vẫn giữ đăng nhập)
    /exit     thoát
"""

# Standard libraries
import argparse
import json

# Local modules
from agent import providers, tools
from agent.agent_openai import (
    MAX_STEPS,
    _accumulate_usage,
    _active_tools,
    _assistant_message,
    _call_tool,
    _new_usage,
    _print_usage,
    _redact,
)
from agent.api_client import HAutoMLClient
from agent.prompts import SYSTEM_PROMPT


class ChatSession:
    """
    Một phiên chat: giữ lịch sử hội thoại và một HAutoMLClient sống xuyên suốt.

    Client sống lâu chính là lý do không phải đăng nhập lại - access_token và
    user_id nằm trong nó, các lượt sau dùng lại ngay.
    """

    def __init__(self, base_url=None, provider=None, model=None, verbose=True):
        self.config = providers.resolve(provider, model)
        self.llm = providers.build_client(self.config)
        self.api = HAutoMLClient(base_url)
        self.verbose = verbose
        self.usage = _new_usage()
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def close(self) -> None:
        self.api.close()

    def reset(self) -> None:
        """Xoá lịch sử nhưng giữ đăng nhập - client không bị đụng tới."""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    @property
    def logged_in(self) -> bool:
        return bool(self.api.access_token)

    def send(self, user_message: str) -> str:
        """Gửi một câu và chạy vòng lặp tool cho tới khi agent trả lời xong."""
        tool_schemas, dispatch = _active_tools()
        self.messages.append({"role": "user", "content": user_message})

        for _ in range(MAX_STEPS):
            response = self.llm.chat.completions.create(
                model=self.config.model,
                messages=self.messages,
                tools=tool_schemas,
                tool_choice="auto",
            )
            _accumulate_usage(self.usage, response.usage)

            message = response.choices[0].message
            self.messages.append(_assistant_message(message))

            if not message.tool_calls:
                return message.content or ""

            for call in message.tool_calls:
                arguments: dict = {}
                try:
                    arguments = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError as error:
                    result = {"ok": False, "error": f"Tham số tool không phải JSON hợp lệ: {error}"}
                else:
                    if self.verbose:
                        shown = json.dumps(_redact(arguments), ensure_ascii=False)
                        print(f"  · {call.function.name}({shown})")
                    result = _call_tool(self.api, dispatch, call.function.name, arguments)

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        return (
            f"(Tôi đã chạy quá {MAX_STEPS} bước mà chưa xong. "
            "Thử hỏi lại theo cách cụ thể hơn.)"
        )


def _print_tools() -> None:
    schemas, _ = _active_tools()
    print(f"\n{len(schemas)} tool đang bật:")
    for schema in schemas:
        function = schema["function"]
        print(f"  {function['name']:26} {function['description'][:64]}")
    print()


def _print_banner(session: ChatSession) -> None:
    print("=" * 66)
    print("  HAutoML Agent - chat")
    print("=" * 66)
    print(f"  Model  : {session.config.name} / {session.config.model}")
    print(f"  Backend: {session.api.base_url}")
    if tools.dev_tools_enabled():
        print("  Tool dev: ĐANG BẬT (AGENT_DEV_TOOLS)")
    if providers.tracing_enabled():
        print("  Langfuse: đang theo dõi chi phí")
    print()
    print("  Lệnh: /cost  /tools  /reset  /exit")
    print("  Gõ tiếng Việt bình thường, ví dụ:")
    print('    "đăng nhập hoang@example.com mật khẩu Test@12345"')
    print('    "tôi có dataset nào"')
    print('    "dataset đó có những cột gì"')
    print("=" * 66 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat nhiều lượt với agent HAutoML")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--quiet", action="store_true", help="Không hiện tool được gọi")
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
            if line == "/reset":
                session.reset()
                state = "vẫn đang đăng nhập" if session.logged_in else "chưa đăng nhập"
                print(f"  (đã xoá lịch sử hội thoại, {state})\n")
                continue
            if line.startswith("/"):
                print("  (lệnh không rõ. Có: /cost /tools /reset /exit)\n")
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
        session.close()
        if providers.tracing_enabled():
            tracer = providers.get_tracer()
            if tracer is not None:
                tracer.flush()
        print("Tạm biệt.")


if __name__ == "__main__":
    main()
