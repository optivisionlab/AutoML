"""
Chạy kịch bản benchmark trên hệ thống agent thật (LLM + backend thật).

Mỗi ca x lần lặp x biến thể ghi một thư mục:

    <runs>/<variant>/<case>_rNN/
        trace.jsonl   mọi sự kiện agent, thời gian LLM, lỗi chèn, lượt chat
        run.json      kết quả thô: câu trả lời, job tạo ra, snapshot, fixture

Chấm điểm KHÔNG nằm ở đây (xem analyze.py) để chấm lại được mà không chạy lại.
"""

# Standard libraries
import json
import os
import subprocess
import threading
import time
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

# Local modules (cần src/backend trong sys.path - xem bench.py)
from agent import tools
from agent.api_client import HAutoMLClient
from agent.chat import ChatSession

from benchmark import variants
from benchmark.common import REPO, read_trace, substitute
from benchmark.auth import install_reauthentication


class Trace:
    """Ghi JSONL ngay khi có sự kiện; watcher ghi từ thread khác nên có khoá."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def __call__(self, kind: str, data) -> None:
        line = json.dumps({"record": kind, "at": time.time(), "data": data}, ensure_ascii=False, default=str)
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def read(self) -> list[dict]:
        # Watcher có thể còn ghi khi hết hạn chờ: đọc trong khoá để không gặp dòng ghi dở.
        with self._lock:
            return read_trace(self.path)


def git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _write_json(path: Path, value: dict) -> None:
    """Ghi qua file tạm rồi thay thế: tiến trình chết giữa chừng không làm hỏng checkpoint cũ."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    os.replace(temporary, path)


def _own_job_ids(api) -> set[str] | None:
    listing = tools.list_my_jobs(api)
    return {j["job_id"] for j in listing.get("jobs") or []} if listing.get("ok") else None


def _job(api, job_id: str) -> dict:
    info = tools.get_job_info(api, job_id)
    return info.get("job") if info.get("ok") and isinstance(info.get("job"), dict) else info


def _wait_watchers(session, limit: float) -> dict:
    started = time.monotonic()
    while session.watcher.active() and time.monotonic() - started < limit:
        time.sleep(1)
    return {"seconds": time.monotonic() - started, "remaining": session.watcher.active()}


def _wait_job_done(api, job_id: str, limit: float) -> int | None:
    started = time.monotonic()
    status = None
    while True:
        status = (_job(api, job_id) or {}).get("status")
        if status in (1, -1, -2) or time.monotonic() - started >= limit:
            break
        time.sleep(min(5, max(0, limit - (time.monotonic() - started))))
    return status


def assert_idle(api):
    listing = tools.list_my_jobs(api)
    if not listing.get("ok"):
        raise RuntimeError("Không xác minh được job đang chạy; dừng để tránh chạy chồng.")
    active = [j["job_id"] for j in listing.get("jobs", []) if j.get("status") not in (1, -1, -2)]
    if active:
        raise RuntimeError(f"Tài khoản còn job chưa kết thúc: {active}. Chờ/xử lý trên backend rồi chạy tiếp.")


def settle_jobs(api, job_ids, limit):
    deadline = time.monotonic() + limit
    statuses = {j: _wait_job_done(api, j, max(0, deadline - time.monotonic())) for j in job_ids}
    return {j: s for j, s in statuses.items() if s not in (1, -1, -2)}


def _prepare_running_job(api, cfg: dict, record) -> dict:
    """Fixture D06: một job đang chạy, tạo bằng code (không qua agent, không tính token)."""
    spec = cfg["running_job_fixture"]
    result = tools.start_training(
        api,
        dataset_id=cfg["placeholders"][spec["dataset"]],
        target=spec["target"],
        list_feature=spec["features"],
        metric_sort=spec["metric"],
        problem_type=spec["problem_type"],
        search_algorithm=spec.get("search_algorithm", "random_search"),
        max_time=spec["max_time"],
    )
    job_id = result.get("job_id")
    status = (_job(api, job_id) or {}).get("status") if job_id else None
    fixture = {"job_id": job_id, "status_before": status, "start_result_ok": bool(result.get("ok"))}
    record("fixture", {"running_job": fixture})
    return fixture


def _set_activation(api, job_id: str, wanted: int) -> dict:
    """Đưa job fixture về đúng trạng thái kích hoạt trước khi đo: lượt trước có thể đã bật/tắt nó."""
    job = _job(api, job_id)
    if job.get("activate") != wanted:
        tools.activate_model(api, job_id, bool(wanted))
        job = _job(api, job_id)
    return {"job_id": job_id, "activate_before": job.get("activate")}


def build_turns(case: dict, cases_doc: dict, cfg: dict) -> list:
    """Danh sách lượt; None = chờ job do lượt trước tạo ra chạy xong."""
    values = cfg["placeholders"]
    turns = [substitute(t, values) for t in case["turns"]]
    if case["flow"] == "train":
        rows = json.dumps(cfg["predict_rows"][case["task"]["dataset"]], ensure_ascii=False, separators=(",", ":"))
        turns = [
            f"{turns[0]} {cases_doc['train_suffix']}",
            None,
            substitute(cases_doc["followup"], {**values, "ROWS": rows}),
        ]
    return turns


def run_case(case: dict, cases_doc: dict, cfg: dict, variant: str, repeat: int, out_root: Path, phase: str) -> Path | None:
    folder = out_root / variant / f"{case['id']}_r{repeat:02d}"
    if (folder / "run.json").exists() and cfg.get("_retry_invalid"):
        from benchmark.analyze import analyze_run
        existing = json.loads((folder / "run.json").read_text())
        if existing.get("protocol_id") != cfg.get("_protocol_id"):
            raise RuntimeError("Lượt đã lưu thuộc protocol khác.")
        if analyze_run(folder, case)["task_status"] == "INVALID_FIXTURE":
            folder.rename(folder.with_name(f"{folder.name}.invalid-{time.time_ns()}"))
    if (folder / "run.json").exists():
        existing = json.loads((folder / "run.json").read_text())
        if existing.get("protocol_id") != cfg.get("_protocol_id"):
            raise RuntimeError("Lượt đã lưu thuộc protocol khác.")
        if existing.get("halt_reason") or (existing.get("interrupted") and not existing.get("settle_verified")):
            with HAutoMLClient() as api:
                if not tools.ensure_login(api).get("ok"):
                    raise RuntimeError("Không xác minh được job cũ; chưa thể tiếp tục.")
                assert_idle(api)
            if existing.get("halt_reason"):
                existing["resolved_halt_reason"] = existing.pop("halt_reason")
            if existing.get("interrupted"):
                # Lượt bị ngắt giữ nguyên FAIL; chỉ xác nhận job của nó đã dừng, không gọi lại LLM.
                existing["settle_verified"] = True
            _write_json(folder / "run.json", existing)
        print(f"  = {folder.relative_to(out_root)} đã có, bỏ qua")
        return None
    if folder.exists():
        # Lần chạy trước bị ngắt giữa chừng: giữ lại làm bằng chứng, không ghi đè.
        folder.rename(folder.with_name(f"{folder.name}.aborted-{int(time.time())}"))
    folder.mkdir(parents=True)
    record = Trace(folder / "trace.jsonl")
    print(f"  ▶ {variant} / {case['id']} lần {repeat}")

    max_wait = float(cfg.get("max_wait_seconds", 600))
    values = dict(cfg["placeholders"])
    run = {
        "case_id": case["id"], "group": case["group"], "variant": variant, "repeat": repeat,
        "phase": phase, "bench_version": cases_doc["version"], "commit": git_commit(),
        "protocol_id": cfg.get("_protocol_id"),
        "started_at": datetime.now(timezone.utc).isoformat(), "faults": case.get("faults", []),
        "turns": [], "fixtures": {}, "errors": [],
    }

    def save() -> None:
        run["placeholders"] = values
        _write_json(folder / "run.json", run)

    with HAutoMLClient() as harness_api, ExitStack() as stack:
        # Client riêng cho bộ chạy: lời gọi chuẩn bị/kiểm tra không lẫn vào sự kiện của agent.
        login = tools.ensure_login(harness_api)
        if not login.get("ok"):
            raise SystemExit(f"Bộ chạy không đăng nhập được: {login.get('error')}")
        install_reauthentication(harness_api)
        assert_idle(harness_api)

        if "running_job" in case.get("fixtures", []):
            fixture = _prepare_running_job(harness_api, cfg, record)
            run["fixtures"]["running_job"] = fixture
            values["RUNNING_JOB"] = fixture["job_id"] or "<RUNNING_JOB>"
        if "inactive_job" in case.get("fixtures", []):
            run["fixtures"]["inactive_job"] = _set_activation(harness_api, values["INACTIVE_JOB"], 0)
        if "glass_job" in case.get("fixtures", []):
            run["fixtures"]["glass_job"] = _set_activation(harness_api, values["GLASS_JOB"], 1)

        jobs_before = _own_job_ids(harness_api)
        # Số job đã có ảnh hưởng độ dài kết quả list_my_jobs (token, thời gian): ghi để so sánh công bằng.
        run["account_job_count"] = len(jobs_before) if jobs_before is not None else None
        datasets = tools.list_my_datasets(harness_api)
        listed = datasets.get("datasets") or [] if datasets.get("ok") else None
        run["account_dataset_ids"] = [d.get("_id") for d in listed] if listed is not None else None
        run["account_datasets"] = {d.get("_id"): d.get("dataName") for d in listed} if listed is not None else None
        if case["flow"] == "train":
            run["expected_predict_rows"] = cfg["predict_rows"][case["task"]["dataset"]]

        session = ChatSession(provider=cfg.get("provider"), model=cfg.get("model"), verbose=False)
        stack.callback(session.close)
        if not session.auth.get("ok"):
            raise SystemExit(f"Agent không đăng nhập được: {session.auth.get('error')}")
        install_reauthentication(session.api)
        run["provider"], run["model"] = session.config.name, session.config.model
        session.events.subscribe(lambda event: record("event", event))
        variants.apply_variant(session, variant, stack)
        variants.instrument_tools(session, record)
        variants.instrument_schema_reads(session, record)
        variants.instrument_llm(session, record, case.get("faults", []))
        variants.inject_api_faults(session.api, record, case.get("faults", []))

        # Từ đây agent đã nhận yêu cầu. Bị ngắt thì lượt được giữ và tính FAIL, không chạy
        # lại: chạy lại sẽ xoá một kết quả đã quan sát được và mở đường chọn lượt tốt.
        run["interrupted"] = "Lượt bị ngắt sau khi agent đã nhận prompt; không chạy lại."
        save()
        run_cfg = {**cfg, "placeholders": values}
        for prompt in build_turns(case, cases_doc, run_cfg):
            if prompt is None:
                waited = _wait_watchers(session, max_wait)
                record("wait", waited)
                run["job_wait"] = waited
                continue
            record("user", prompt)
            before = time.monotonic()
            turn = {"prompt": prompt}
            try:
                turn["answer"] = session.send(prompt)
            except Exception as error:  # noqa: BLE001 - lỗi lượt chat là kết quả cần ghi, không dừng benchmark
                turn["error"] = f"{type(error).__name__}: {error}"
                record("turn_error", turn["error"])
            turn["seconds"] = time.monotonic() - before
            record("assistant", turn)
            run["turns"].append(turn)
            run["usage"] = dict(session.usage)
            save()

        # Không để job của ca này tranh tài nguyên với ca sau.
        run["final_wait"] = _wait_watchers(session, max_wait)
        run["usage"] = dict(session.usage)
        handoff = session.team.handoff
        run["handoff"] = {"requirements": handoff.requirements, "configs": handoff.configs, "jobs": handoff.jobs}

        jobs_after = _own_job_ids(harness_api)
        fixture_job = run["fixtures"].get("running_job", {}).get("job_id")
        if jobs_before is None or jobs_after is None:
            run["new_jobs"] = None
            run["errors"].append("Không liệt kê được job để đếm job mới.")
        else:
            run["new_jobs"] = sorted(jobs_after - jobs_before - {fixture_job})
        run["job_snapshots"] = {job_id: _job(harness_api, job_id) for job_id in run["new_jobs"] or []}

        if "inactive_job" in run["fixtures"]:
            run["fixtures"]["inactive_job"]["activate_after"] = _job(harness_api, values["INACTIVE_JOB"]).get("activate")
        if fixture_job:
            run["fixtures"]["running_job"]["status_after"] = (_job(harness_api, fixture_job) or {}).get("status")
            # Check the status actually seen by the agent, not only before its LLM calls.
            observed = []
            for entry in record.read():
                if entry["record"] != "tool_result":
                    continue
                data = entry["data"]
                result = data.get("result") or {}
                if data["name"] in ("get_job_info", "watch_job") and data["arguments"].get("job_id") == fixture_job:
                    # get_job_info trả status trong "job"; watch_job trả status ở cấp ngoài.
                    observed.append((result.get("job") or result).get("status"))
                if data["name"] == "list_my_jobs":
                    observed.extend(j.get("status") for j in result.get("jobs", []) if j.get("job_id") == fixture_job)
            run["fixtures"]["running_job"]["observed_statuses"] = observed

        pending = settle_jobs(harness_api, list(run["new_jobs"] or []) + ([fixture_job] if fixture_job else []), max_wait)
        if pending or run["new_jobs"] is None:
            run["halt_reason"] = f"Không xác nhận được mọi job đã kết thúc: {pending}; new_jobs={run['new_jobs']}"

    run.pop("interrupted", None)
    run["finished_at"] = datetime.now(timezone.utc).isoformat()
    save()
    if run.get("halt_reason"):
        raise RuntimeError(run["halt_reason"] + ". Đã lưu run.json; dừng cả đợt, không chạy ca tiếp theo.")
    return folder


def run_all(cases_doc: dict, cfg: dict, entries: list, out_root: Path, phase: str) -> None:
    """entries: các lượt (variant, ca, lần) theo đúng thứ tự đã khoá trong plan."""
    by_id = {c["id"]: c for c in cases_doc["cases"]}
    for variant, case_id, repeat in entries:
        # Dừng an toàn giữa hai lượt; ngắt giữa lượt thì lượt đó tính FAIL.
        if (out_root / "STOP").exists():
            print(f"Thấy {out_root / 'STOP'}: dừng trước lượt tiếp theo. Xoá file rồi chạy lại để tiếp tục.")
            return
        run_case(by_id[case_id], cases_doc, cfg, variant, repeat, out_root, phase)
