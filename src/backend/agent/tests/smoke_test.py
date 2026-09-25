"""
Kiểm tra tầng tool mà KHÔNG cần LLM, không cần ANTHROPIC_API_KEY.

    cd src/backend
    python -m agent.tests.smoke_test

Chạy bước này trước khi cắm Claude vào. Nếu tầng tool đã sai thì agent chắc chắn
cũng sai, và debug qua LLM khó hơn nhiều.

Kỳ vọng của kịch bản: signup thành công, login thất bại với 403 vì tài khoản
chưa xác thực email. Đó là hành vi đúng của backend, không phải lỗi của tool.
"""

# Standard libraries
import json
import uuid

# Local modules
from agent import tools
from agent.api_client import HAutoMLClient


def _show(result: dict) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print()


def main() -> None:
    suffix = uuid.uuid4().hex[:8]
    username = f"agent_test_{suffix}"
    email = f"agent_test_{suffix}@example.com"
    password = "Test@12345"

    with HAutoMLClient() as client:
        print(f"Backend: {client.base_url}")
        print(f"Tài khoản thử nghiệm: {username} / {email}\n")

        print("[1] signup")
        _show(tools.signup(
            client,
            username=username,
            email=email,
            password=password,
            full_name="Agent Test",
            gender="male",
            date="01/01/2000",
            number="0900000000",
        ))

        print("[2] login  (kỳ vọng: ok=false, status_code=403 - chưa xác thực email)")
        _show(tools.login(client, username=username, password=password))

        print("[3] get_me (kỳ vọng: ok=false, 401 - chưa có token)")
        _show(tools.get_me(client))

    print("Muốn có sẵn tài khoản đã xác thực và một dataset để test tiếp:")
    print("    python -m agent.tests.seed")


if __name__ == "__main__":
    main()
