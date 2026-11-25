"""
Chạy bộ đánh giá với LLM thật (tốn token theo provider đã cấu hình).

    cd src/backend
    python -m agent.evals --provider openai --model gpt-4.1-mini --repeat 3 --out eval-report.json
    python -m agent.evals --only train_classification,ambiguous_target
    python -m agent.evals --baseline eval-before.json --out eval-after.json   # so với lần chạy trước

Thoát mã 1 khi tỉ lệ đạt < --min-pass, hoặc tụt so với --baseline: dùng làm cổng kiểm trước khi đổi prompt.
"""
import argparse
import json
import sys

from dotenv import load_dotenv

from agent.chat import ChatSession
from agent.evals.runner import DEFAULT_MIN_PASS_RATE, run_suite
from agent.evals.scenarios import SCENARIOS

# Không truyền --out thì vẫn ghi báo cáo ra đây: kết quả chạy tốn token không được chỉ nằm trên terminal.
DEFAULT_REPORT = "eval-last.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Đánh giá hành vi hệ thống agent HAutoML")
    parser.add_argument("--provider", help="Provider LLM (mặc định: theo .env)")
    parser.add_argument("--model", help="Tên model (mặc định: theo .env)")
    parser.add_argument("--repeat", type=int, default=3, help="Số lần chạy mỗi kịch bản (LLM không tất định)")
    parser.add_argument("--only", help="Chỉ chạy các kịch bản này (id, cách nhau bởi dấu phẩy)")
    parser.add_argument("--min-pass", type=float, default=DEFAULT_MIN_PASS_RATE, help="Ngưỡng tỉ lệ đạt chung")
    parser.add_argument("--baseline", help="Báo cáo JSON lần trước để so sánh")
    parser.add_argument("--out", default=DEFAULT_REPORT, help=f"Ghi báo cáo JSON đầy đủ ra file này "
                                                              f"(mặc định: {DEFAULT_REPORT})")
    args = parser.parse_args(argv)

    wanted = {s.strip() for s in (args.only or "").split(",") if s.strip()}
    scenarios = [s for s in SCENARIOS if not wanted or s.id in wanted]
    if not scenarios:
        print(f"Không có kịch bản nào khớp --only. Có: {', '.join(s.id for s in SCENARIOS)}", file=sys.stderr)
        return 2
    load_dotenv()  # key LLM / Langfuse: chỉ nạp khi thật sự chạy

    def make_session(backend):
        return ChatSession(api=backend, provider=args.provider, model=args.model, verbose=False, auto_login=False)

    def progress(run):
        mark = "ĐẠT " if run["passed"] else "LỖI "
        failed = [c["name"] for c in run["checks"] if not c["passed"]]
        print(f"  {mark} {run['scenario']:28s} llm={run['llm_calls']:<3d} tokens={run['total_tokens']:<7d}"
              + (f" | không đạt: {'; '.join(failed)}" if failed else ""), flush=True)

    report = run_suite(scenarios, make_session, repeat=args.repeat, on_run=progress)
    summary = report["summary"]
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=1))

    code = 0
    if summary["pass_rate"] < args.min_pass:
        print(f"\nTỉ lệ đạt {summary['pass_rate']} < ngưỡng {args.min_pass}", file=sys.stderr)
        code = 1
    if args.baseline:
        with open(args.baseline, encoding="utf-8") as file:
            before = json.load(file)["summary"]
        delta_pass = round(summary["pass_rate"] - before["pass_rate"], 3)
        delta_tokens = summary["avg_tokens_per_run"] - before["avg_tokens_per_run"]
        print(f"\nSo với baseline: tỉ lệ đạt {delta_pass:+}, token/lần chạy {delta_tokens:+}")
        for name, now in summary["by_scenario"].items():
            old = before["by_scenario"].get(name)
            if old and now["pass_rate"] < old["pass_rate"]:
                print(f"  TỤT: {name} {old['pass_rate']} -> {now['pass_rate']}", file=sys.stderr)
                code = 1
    if args.out:
        with open(args.out, "w", encoding="utf-8") as file:
            json.dump(report, file, ensure_ascii=False, indent=1)
        print(f"\nĐã ghi báo cáo: {args.out}")
    return code


if __name__ == "__main__":
    sys.exit(main())
