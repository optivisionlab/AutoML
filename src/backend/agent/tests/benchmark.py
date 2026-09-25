"""
Chạy một bộ kịch bản qua agent và ghi lại các bước nó thực sự thực hiện.

    cd src/backend
    python -m agent.tests.benchmark --list              # xem kịch bản, không gọi LLM
    python -m agent.tests.benchmark --only login_profile
    python -m agent.tests.benchmark --max 3
    python -m agent.tests.benchmark --out ket-qua.json

Mỗi kịch bản khai một prompt và chuỗi tool KỲ VỌNG. Harness so chuỗi tool agent
thật sự gọi với chuỗi kỳ vọng, đo số lượt gọi LLM, token và thời gian.

CẢNH BÁO QUOTA: mỗi kịch bản tốn 2-4 lượt gọi LLM. Tier miễn phí của Gemini là
20 lượt/ngày, nên chạy cả bộ có thể hết quota. Dùng --only hoặc --max khi thử.

Cách chấm: so khớp theo THỨ TỰ CON (subsequence), không phải bằng nhau tuyệt
đối. Agent gọi thêm tool hợp lý (vd get_me để lấy thông tin) vẫn tính đạt, miễn
là các tool bắt buộc xuất hiện đúng thứ tự. Đây là chủ ý: cùng một prompt, LLM
có thể chọn đường khác nhau mà vẫn đúng.
"""

# Standard libraries
import argparse
import json
import os
import time
import uuid
from dataclasses import dataclass, field

# Third party libraries
from dotenv import load_dotenv

# Local modules
from agent import providers, tools
from agent.agent_openai import run_agent


# Load file .env
load_dotenv()


@dataclass
class Scenario:
    name: str
    prompt: str
    expect_tools: list[str]
    note: str = ""
    # Kịch bản tạo tài khoản mới cần chuỗi ngẫu nhiên để chạy lại được nhiều lần
    randomize: bool = False


def build_scenarios(username: str, password: str) -> list[Scenario]:
    login = f"Đăng nhập bằng {username} mật khẩu {password}"

    return [
        Scenario(
            name="login_profile",
            prompt=f"{login} rồi cho tôi xem hồ sơ của tôi",
            expect_tools=["login", "get_me"],
            note="Luồng cơ bản nhất",
        ),
        Scenario(
            name="list_datasets",
            prompt=f"{login}, tôi đang có những dataset nào?",
            expect_tools=["login", "list_my_datasets"],
            note="Tool tự lấy user_id, LLM không được truyền vào",
        ),
        Scenario(
            name="dataset_schema",
            prompt=f"{login}. Dataset của tôi có những thuộc tính nào, cột nào làm biến mục tiêu được?",
            expect_tools=["login", "list_my_datasets", "get_dataset_schema"],
            note="Phải liệt kê trước để lấy ID thật, không được bịa ID",
        ),
        Scenario(
            name="no_jobs_honesty",
            prompt=f"{login} rồi cho tôi biết model tốt nhất của tôi đạt accuracy bao nhiêu",
            expect_tools=["login", "list_my_jobs"],
            note="Bẫy bịa số: chưa có job nào, agent phải nói thẳng là chưa có",
        ),
        # Kỳ vọng phụ thuộc môi trường: system prompt bảo agent ưu tiên
        # dev_verify_account khi tool dev đang bật, nên chuỗi tool khác hẳn.
        # Nếu cố định một chuỗi thì benchmark sẽ báo trượt oan.
        Scenario(
            name="signup_unverified",
            prompt=(
                "Đăng ký tài khoản tên bench_{rand}, email bench_{rand}@example.com, "
                "mật khẩu Test@12345, họ tên Bench Test, nam, sinh 01/01/2000, "
                "sđt 0900000000. Rồi đăng nhập giúp tôi."
            ),
            expect_tools=(
                ["signup", "dev_verify_account"]
                if tools.dev_tools_enabled()
                else ["signup", "login"]
            ),
            note=(
                "Tool dev BẬT: agent phải tự xác thực rồi báo rõ đây là đường tắt dev"
                if tools.dev_tools_enabled()
                else "Tool dev TẮT: login phải bị 403, agent giải thích chứ không retry mù"
            ),
            randomize=True,
        ),
    ]


def _matches_in_order(actual: list[str], expected: list[str]) -> bool:
    """Kiểm tra expected xuất hiện trong actual theo đúng thứ tự (subsequence)."""
    remaining = list(expected)

    for name in actual:
        if remaining and name == remaining[0]:
            remaining.pop(0)

    return not remaining


@dataclass
class Result:
    scenario: str
    passed: bool = False
    tools: list[str] = field(default_factory=list)
    llm_calls: int = 0
    total_tokens: int = 0
    seconds: float = 0.0
    failed_tools: list[str] = field(default_factory=list)
    answer: str = ""
    error: str = ""


def run_scenario(scenario: Scenario, verbose: bool) -> Result:
    events: list[dict] = []
    prompt = scenario.prompt

    if scenario.randomize:
        prompt = prompt.replace("{rand}", uuid.uuid4().hex[:6])

    result = Result(scenario=scenario.name)
    started = time.time()

    try:
        result.answer = run_agent(prompt, verbose=verbose, on_event=events.append)
    except Exception as error:  # noqa: BLE001 - benchmark phải sống sót mọi lỗi
        result.error = f"{type(error).__name__}: {error}"

    result.seconds = round(time.time() - started, 1)
    result.tools = [e["name"] for e in events if e["type"] == "tool_call"]
    result.failed_tools = [
        f"{e['name']}: {e.get('error')}"
        for e in events
        if e["type"] == "tool_call" and not e["ok"]
    ]
    result.llm_calls = sum(1 for e in events if e["type"] == "llm_call")
    result.total_tokens = sum(e["total_tokens"] for e in events if e["type"] == "llm_call")
    result.passed = not result.error and _matches_in_order(result.tools, scenario.expect_tools)

    return result


def _print_report(scenarios: list[Scenario], results: list[Result]) -> None:
    by_name = {s.name: s for s in scenarios}

    print("\n" + "=" * 78)
    print("KẾT QUẢ BENCHMARK")
    print("=" * 78)

    for result in results:
        scenario = by_name[result.scenario]
        mark = "ĐẠT " if result.passed else "TRƯỢT"

        print(f"\n[{mark}] {result.scenario}   ({result.seconds}s, "
              f"{result.llm_calls} lượt LLM, {result.total_tokens} token)")
        print(f"        kỳ vọng : {' -> '.join(scenario.expect_tools)}")
        print(f"        thực tế : {' -> '.join(result.tools) or '(không gọi tool nào)'}")

        if scenario.note:
            print(f"        ghi chú : {scenario.note}")
        # Tool trả ok=false không phải lúc nào cũng là lỗi: kịch bản
        # signup_unverified CẦN login thất bại 403.
        for failure in result.failed_tools:
            print(f"        tool lỗi: {failure}")
        if result.error:
            print(f"        NGOẠI LỆ: {result.error}")

    passed = sum(1 for r in results if r.passed)
    print("\n" + "-" * 78)
    print(f"Tổng: {passed}/{len(results)} đạt | "
          f"{sum(r.llm_calls for r in results)} lượt gọi LLM | "
          f"{sum(r.total_tokens for r in results)} token | "
          f"{round(sum(r.seconds for r in results), 1)}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark các bước thực hiện của agent")
    parser.add_argument("--username", default=os.getenv("AGENT_TEST_USER"))
    parser.add_argument("--password", default=os.getenv("AGENT_TEST_PASSWORD"))
    parser.add_argument("--only", action="append", help="Chỉ chạy kịch bản tên này (lặp lại được)")
    parser.add_argument("--max", type=int, default=None, help="Chạy tối đa N kịch bản")
    parser.add_argument("--list", action="store_true", help="Liệt kê kịch bản rồi thoát, không gọi LLM")
    parser.add_argument("--out", default=None, help="Ghi kết quả ra file JSON")
    parser.add_argument("--quiet", action="store_true", help="Không in log tool từng bước")
    args = parser.parse_args()

    if not args.username or not args.password:
        parser.error(
            "Thiếu tài khoản. Dùng --username/--password, hoặc đặt AGENT_TEST_USER "
            "và AGENT_TEST_PASSWORD trong .env"
        )

    scenarios = build_scenarios(args.username, args.password)

    if args.only:
        wanted = set(args.only)
        unknown = wanted - {s.name for s in scenarios}
        if unknown:
            parser.error(f"Không có kịch bản: {', '.join(sorted(unknown))}")
        scenarios = [s for s in scenarios if s.name in wanted]

    if args.max is not None:
        scenarios = scenarios[: args.max]

    if args.list:
        print(f"{len(scenarios)} kịch bản:\n")
        for scenario in scenarios:
            print(f"  {scenario.name}")
            print(f"    kỳ vọng: {' -> '.join(scenario.expect_tools)}")
            print(f"    {scenario.note}\n")
        print(f"Ước tính: khoảng {len(scenarios) * 3} lượt gọi LLM nếu chạy hết.")
        return

    config = providers.resolve()
    print(f"Provider : {config.name} / {config.model}")
    print(f"Kịch bản : {len(scenarios)} (ước tính ~{len(scenarios) * 3} lượt gọi LLM)\n")

    results = []
    for index, scenario in enumerate(scenarios, start=1):
        print(f"--- [{index}/{len(scenarios)}] {scenario.name}")
        results.append(run_scenario(scenario, verbose=not args.quiet))

    _print_report(scenarios, results)

    if args.out:
        payload = {
            "provider": config.name,
            "model": config.model,
            "results": [r.__dict__ for r in results],
        }
        with open(args.out, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        print(f"\nĐã ghi kết quả vào {args.out}")


if __name__ == "__main__":
    main()
