"""
Dựng lại dữ liệu thử nghiệm: một tài khoản đã xác thực + một dataset.

    cd src/backend
    python -m agent.tests.seed
    python -m agent.tests.seed --username me@example.com --password Test@12345

Dùng khi MongoDB bị xoá sạch (docker compose down, docker system prune) và cần
có lại dữ liệu để chạy check_api hoặc benchmark.

Chạy được nhiều lần: tài khoản đã tồn tại thì bỏ qua bước đăng ký, dataset trùng
tên thì không tải lên nữa.

Chỉ dùng khi phát triển - nó gọi dev_verify_account để bỏ qua khâu xác thực
email, nên cần AGENT_DEV_TOOLS=1.
"""

# Standard libraries
import argparse
import os
from pathlib import Path

# Third party libraries
from dotenv import load_dotenv

# Local modules
from agent import tools
from agent.api_client import ApiError, HAutoMLClient


# Load file .env
load_dotenv()


# CSV có sẵn trong repo, nhỏ (9.8 KB) và là bài toán phân loại rõ ràng.
DEFAULT_DATASET = Path(__file__).resolve().parent.parent / "assets" / "end_users" / "glass.csv"
DEFAULT_DATASET_NAME = "Glass Identification"


def _ensure_account(client: HAutoMLClient, username: str, password: str, email: str) -> str | None:
    """Đăng ký nếu chưa có, xác thực, rồi đăng nhập. Trả về user_id."""
    result = tools.signup(
        client,
        username=username,
        email=email,
        password=password,
        full_name="Seed Test",
        gender="male",
        date="01/01/2000",
        number="0900000000",
    )

    if result["ok"]:
        user_id = result["user"]["id"]
        print(f"  đã tạo tài khoản: {username} ({user_id})")

        verified = tools.dev_verify_account(client, user_id=user_id, email=email)
        if not verified["ok"]:
            print(f"  KHÔNG xác thực được: {verified.get('error')}")
            return None
        print("  đã xác thực")
        return user_id

    # 409 nghĩa là tài khoản có sẵn từ lần seed trước - không phải lỗi.
    if result.get("status_code") != 409:
        print(f"  đăng ký thất bại: {result.get('error')}")
        return None

    print(f"  tài khoản đã tồn tại: {username}")
    login = tools.login(client, username=email, password=password)
    if not login["ok"]:
        print(f"  KHÔNG đăng nhập được: {login.get('error')}")
        return None

    me = tools.get_me(client)
    return me["user"]["_id"] if me["ok"] else None


def _ensure_dataset(client: HAutoMLClient, user_id: str, csv_path: Path, data_name: str) -> None:
    existing = tools.list_my_datasets(client)
    if existing["ok"]:
        for dataset in existing["datasets"]:
            if dataset.get("dataName") == data_name:
                print(f"  dataset đã có: {data_name} ({dataset['_id']})")
                return

    if not csv_path.is_file():
        print(f"  KHÔNG thấy file: {csv_path}")
        return

    try:
        dataset = client.upload_dataset(
            user_id=user_id,
            data_name=data_name,
            data_type="classification",
            file_path=str(csv_path),
        )
    except ApiError as error:
        print(f"  tải lên thất bại: {error}")
        return

    print(f"  đã tải lên dataset: {data_name} ({dataset.get('_id')})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dựng lại dữ liệu thử nghiệm")
    parser.add_argument("--username", default=os.getenv("AGENT_TEST_USER", "seeduser"))
    parser.add_argument("--password", default=os.getenv("AGENT_TEST_PASSWORD", "Test@12345"))
    parser.add_argument("--email", default=None, help="Mặc định: <username>@example.com")
    parser.add_argument("--csv", default=str(DEFAULT_DATASET))
    parser.add_argument("--data-name", default=DEFAULT_DATASET_NAME)
    parser.add_argument("--base-url", default=None)
    args = parser.parse_args()

    if not tools.dev_tools_enabled():
        raise SystemExit(
            "Cần AGENT_DEV_TOOLS=1 trong .env - seed dùng dev_verify_account để "
            "bỏ qua khâu xác thực email."
        )

    # Cho phép truyền email trực tiếp qua --username, như check_api vẫn làm.
    username = args.username
    email = args.email or (username if "@" in username else f"{username}@example.com")
    if "@" in username:
        username = username.split("@")[0]

    with HAutoMLClient(args.base_url) as client:
        print(f"Backend: {client.base_url}")

        try:
            client._request("GET", "/home")
        except ApiError as error:
            raise SystemExit(f"Backend chưa sẵn sàng: {error}")

        user_id = _ensure_account(client, username, args.password, email)
        if not user_id:
            raise SystemExit("Dừng: không dựng được tài khoản.")

        _ensure_dataset(client, user_id, Path(args.csv), args.data_name)

    print("\nXong. Chạy thử:")
    print(f"  python -m agent.tests.check_api {email} {args.password}")
    print(f"  python -m agent.tests.benchmark --username {email} --password {args.password} --max 2")


if __name__ == "__main__":
    main()
