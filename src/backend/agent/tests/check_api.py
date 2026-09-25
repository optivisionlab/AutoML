"""
Chạy thử toàn bộ tool đọc dữ liệu bằng một tài khoản có thật, KHÔNG cần LLM.

    cd src/backend
    python -m agent.tests.check_api hoang14205@gmail.com Hoang12345

Hoặc đặt sẵn trong .env rồi gọi không tham số:

    AGENT_TEST_USER=hoang14205@gmail.com
    AGENT_TEST_PASSWORD=Hoang12345

Khác smoke_test.py: file kia tạo tài khoản mới để kiểm tra luồng đăng ký, còn
file này đăng nhập bằng tài khoản sẵn có để xem dữ liệu thật. Dùng nó để phân
biệt "tool sai" với "LLM sai" - nếu ở đây đã lỗi thì đừng đổ cho agent.
"""

# Standard libraries
import argparse
import json
import os

# Third party libraries
from dotenv import load_dotenv

# Local modules
from agent import tools
from agent.api_client import HAutoMLClient


# Load file .env
load_dotenv()


def _show(label: str, result: dict, limit: int = 600) -> None:
    status = "OK " if result.get("ok") else "LỖI"
    print(f"[{status}] {label}")
    print("      " + json.dumps(result, ensure_ascii=False)[:limit])
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Kiểm tra tool đọc dữ liệu, không cần LLM")
    parser.add_argument("username", nargs="?", default=os.getenv("AGENT_TEST_USER"))
    parser.add_argument("password", nargs="?", default=os.getenv("AGENT_TEST_PASSWORD"))
    parser.add_argument("--base-url", default=None)
    args = parser.parse_args()

    if not args.username or not args.password:
        parser.error(
            "Thiếu tài khoản. Truyền vào dòng lệnh, hoặc đặt AGENT_TEST_USER "
            "và AGENT_TEST_PASSWORD trong .env"
        )

    with HAutoMLClient(args.base_url) as client:
        print(f"Backend: {client.base_url}")
        print(f"Tài khoản: {args.username}\n")

        _show("list_my_datasets trước khi login (kỳ vọng LỖI 401)", tools.list_my_datasets(client))

        result = tools.login(client, username=args.username, password=args.password)
        _show("login", result)
        if not result.get("ok"):
            print("Đăng nhập thất bại, dừng tại đây.")
            raise SystemExit(1)

        _show("get_me", tools.get_me(client))
        print(f"      -> user_id được cache: {client.user_id}\n")

        datasets = tools.list_my_datasets(client)
        _show("list_my_datasets", datasets)

        # Chỉ xem chi tiết khi thật sự có dataset, không bịa ID.
        if datasets.get("ok") and datasets.get("datasets"):
            first_id = datasets["datasets"][0]["_id"]
            _show(f"get_dataset_info({first_id})", tools.get_dataset_info(client, dataset_id=first_id))
            _show(
                f"get_dataset_schema({first_id})",
                tools.get_dataset_schema(client, dataset_id=first_id),
                limit=1600,
            )
        else:
            print("[bỏ qua] get_dataset_info / get_dataset_schema - chưa có dataset nào\n")

        jobs = tools.list_my_jobs(client)
        _show("list_my_jobs", jobs)

        if jobs.get("ok") and jobs.get("jobs"):
            first_job = jobs["jobs"][0].get("job_id") or jobs["jobs"][0].get("_id")
            _show(f"get_job_info({first_job})", tools.get_job_info(client, job_id=first_job))
        else:
            print("[bỏ qua] get_job_info - chưa có job nào\n")

    print("Xong. Tầng tool hoạt động thì lỗi (nếu có) nằm ở tầng LLM.")


if __name__ == "__main__":
    main()
