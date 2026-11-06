"""
Benchmark hệ thống agent HAutoML - chạy, chấm test và xuất báo cáo.

Chạy từ thư mục gốc repository:

    python benchmark/bench.py init                     # tạo bench_config.json + pricing.json mẫu
    python benchmark/bench.py prepare                  # chia 4 dataset thật thành train/test
    python benchmark/bench.py prepare-ts               # dữ liệu nhóm T: 2 chuỗi thời gian thật, 96 bước test
    python benchmark/bench.py preflight --online       # kiểm dữ liệu/cấu hình/backend
    python benchmark/bench.py lock --phase pilot       # khóa trước khi chạy thử
    python benchmark/bench.py run --phase pilot        # chạy thử mỗi ca 1 lần
    python benchmark/bench.py lock                    # khóa plan chính thức
    python benchmark/bench.py run                      # chạy cả plan (full + ablation xen kẽ)
    python benchmark/bench.py score                    # chấm nhóm C trên *_test.csv
    python benchmark/bench.py report                   # -> report/<experiment>/<phase>/report.md

Chi tiết protocol: benchmark.md.
"""

# Standard libraries
import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_REPO), str(_REPO / "src" / "backend")]

# Local modules
from benchmark.common import ARTIFACTS, BACKEND, BENCH_DIR, CASES_PATH, CONFIG_PATH, PRICING_PATH, load_json  # noqa: E402
from benchmark import protocol  # noqa: E402


_PRICING_TEMPLATE = {
    "provider": None, "model": None, "price_date": None, "source_url": None,
    "input_price_usd_per_million": None, "output_price_usd_per_million": None, "billing_notes": None,
    "billing_mode": None,
}


def _runs_root(phase: str, cfg: dict) -> Path:
    return protocol.experiment_root(cfg, phase)


def _load_config() -> dict:
    cfg = load_json(CONFIG_PATH)
    if cfg is None:
        raise SystemExit(f"Chưa có {CONFIG_PATH}. Chạy: python benchmark/bench.py init")
    return cfg


def cmd_init(_args) -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    if CONFIG_PATH.exists():
        print(f"Đã có {CONFIG_PATH}, giữ nguyên.")
    else:
        cfg = load_json(BENCH_DIR / "config.example.json")
        try:
            from agent.providers import resolve
            resolved = resolve()
            cfg["provider"], cfg["model"] = resolved.name, resolved.model
        except (RuntimeError, ValueError):
            pass
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
        print(f"Đã tạo {CONFIG_PATH} - điền ID dataset/job vào 'placeholders'.")
    if not PRICING_PATH.exists():
        PRICING_PATH.write_text(json.dumps(_PRICING_TEMPLATE, indent=1) + "\n", encoding="utf-8")
        print(f"Đã tạo {PRICING_PATH} - điền bảng giá model (USD / 1M token).")


def cmd_prepare(_args) -> None:
    from benchmark.prepare_data import main

    main()


def cmd_prepare_ts(_args) -> None:
    from benchmark.prepare_ts import main

    main()


def selected_config(args):
    cfg = _load_config()
    if getattr(args, "experiment", None):
        cfg["experiment_id"] = args.experiment
    return cfg


def cmd_preflight(args):
    cfg = selected_config(args)
    cases = load_json(CASES_PATH)
    errors, warnings = protocol.preflight(cfg, cases, args.cases.split(",") if args.cases else None)
    if args.online and not errors:
        from benchmark.protocol import check_online
        errors += check_online(cfg)
    for message in warnings:
        print(f"NOTE: {message}")
    for message in errors:
        print(f"MISSING/ERROR: {message}")
    if errors:
        raise SystemExit(1)
    print("Preflight đạt. Chưa gọi LLM hoặc khởi tạo training.")


def cmd_lock(args):
    cfg = selected_config(args)
    cases = load_json(CASES_PATH)
    errors, _ = protocol.preflight(cfg, cases)
    if errors:
        raise ValueError("Chưa khóa được:\n- " + "\n- ".join(errors))
    root = _runs_root(args.phase, cfg)
    locked = protocol.freeze(root, protocol.snapshot(cfg, cases, load_json(PRICING_PATH), args.phase))
    print(f"Đã khóa {root / 'protocol.json'}\nProtocol: {locked['protocol_id']}\nPlan: {len(locked['payload']['plan'])} lượt (gồm ablation nếu bật).")


def cmd_run(args) -> None:
    from benchmark import runner
    from benchmark.variants_doc import VARIANT_DOCS

    cfg = selected_config(args)
    cases_doc = load_json(CASES_PATH)
    variants = set(args.variants.split(",")) if args.variants else None
    case_ids = set(args.cases.split(",")) if args.cases else None
    unknown = sorted((variants or set()) - set(VARIANT_DOCS)) + sorted((case_ids or set()) - {c["id"] for c in cases_doc["cases"]})
    if unknown:
        raise SystemExit(f"Biến thể/ca không có: {unknown}")

    if args.phase == "official" and (variants or case_ids or args.ablation or args.repeats is not None):
        # Lọc rồi chạy từng phần (vd full trước, ablation sau) phá lịch xen kẽ đã khoá.
        raise ValueError("Official chạy đúng lịch đã khóa, không lọc. Dừng bằng file STOP, chạy lại `run` để tiếp tục.")
    root = _runs_root(args.phase, cfg)
    locked = protocol.verify_current(root, cfg, cases_doc, load_json(PRICING_PATH), args.phase)
    # Chạy đúng thứ tự đã khoá (full và ablation xen kẽ); tuỳ chọn chỉ lọc, không thêm lượt.
    entries = [tuple(x) for x in locked["payload"]["plan"]
               if (variants is None or x[0] in variants) and (case_ids is None or x[1] in case_ids)
               and (not args.ablation or x[0] != "full") and (args.repeats is None or x[2] <= args.repeats)]
    if not entries:
        raise ValueError("Không có lượt nào trong plan đã khóa khớp bộ lọc.")
    errors, _ = protocol.preflight(cfg, cases_doc, sorted({e[1] for e in entries}))
    if errors:
        raise ValueError("\n".join(errors))
    if args.retry_invalid and list(root.glob("*/*/test/test_metrics.json")):
        raise ValueError("Đã chấm test; không được chạy lại fixture để chọn kết quả sau khi xem test.")

    print(f"Chạy {len(entries)} lượt theo thứ tự đã khóa ({args.phase})")
    runner.run_all(cases_doc, {**cfg, "_protocol_id": locked["protocol_id"], "_retry_invalid": args.retry_invalid}, entries, root, args.phase)


def cmd_score(args) -> None:
    from benchmark.scoring import score_all

    if args.phase == "pilot":
        # Protocol khoá ngưỡng: không xem điểm test trước khi chạy chính thức (benchmark.md mục 4).
        raise SystemExit("Không chấm test cho lượt chạy thử. Hiệu chỉnh ngưỡng bằng CV trên phần train.")
    cfg = selected_config(args)
    root = _runs_root(args.phase, cfg)
    locked = protocol.verify_current(root, cfg, load_json(CASES_PATH), load_json(PRICING_PATH), args.phase)
    protocol.require_complete(root, locked)
    score_all(root, locked["payload"]["cases"], locked["payload"]["config"], include_pilot=False)


def cmd_report(args) -> None:
    from benchmark.report import write_report

    cfg = selected_config(args)
    root = _runs_root(args.phase, cfg)
    locked = protocol.read_lock(root)
    out = ARTIFACTS / "report" / cfg["experiment_id"] / args.phase
    path = write_report(root, out, locked["payload"]["cases"], locked["payload"]["pricing"])
    print(f"Đã ghi {path}\n       {out / 'results.csv'}\n       {out / 'results.jsonl'}")


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env")
    parser = argparse.ArgumentParser(description="Benchmark hệ thống agent HAutoML")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Tạo file cấu hình mẫu")
    sub.add_parser("prepare", help="Chia dataset thành train/test cố định")
    sub.add_parser("prepare-ts", help="Dựng dữ liệu nhóm T (time series): train / 96 bước test")
    pre = sub.add_parser("preflight", help="Kiểm tra dữ liệu/cấu hình; không gọi LLM/train")
    pre.add_argument("--cases")
    pre.add_argument("--online", action="store_true", help="Đăng nhập và đọc metadata/fixture trên backend")
    pre.add_argument("--experiment")
    lock = sub.add_parser("lock", help="Khóa protocol và plan cho một phase")
    lock.add_argument("--phase", choices=("pilot", "official"), default="official")
    lock.add_argument("--experiment")

    run = sub.add_parser("run", help="Chạy kịch bản trên LLM + backend thật")
    run.add_argument("--phase", choices=("pilot", "official"), default="official")
    run.add_argument("--cases", help="Chỉ chạy các ca này trong plan, vd A01,C01")
    run.add_argument("--variants", help="Chỉ chạy các biến thể này trong plan, vd full")
    run.add_argument("--repeats", type=int, help="Chỉ chạy các lần lặp từ 1 tới số này")
    run.add_argument("--ablation", action="store_true", help="Chỉ chạy các lượt ablation trong plan")
    run.add_argument("--experiment")
    run.add_argument("--retry-invalid", action="store_true", help="Lưu trữ và chạy lại riêng lượt INVALID_FIXTURE; giữ nguyên FAIL")

    for name, help_text in (("score", "Chấm nhóm C và T trên tập test"), ("report", "Xuất báo cáo")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--phase", choices=("pilot", "official"), default="official")
        p.add_argument("--experiment")

    args = parser.parse_args()
    try:
        {"init": cmd_init, "prepare": cmd_prepare, "prepare-ts": cmd_prepare_ts, "preflight": cmd_preflight, "lock": cmd_lock,
         "run": cmd_run, "score": cmd_score, "report": cmd_report}[args.command](args)
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
