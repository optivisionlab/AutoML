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
import resource
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

from benchmark import consent, jobinfo, variants
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


def _datasets(api) -> dict | None:
    """{dataset_id: tên} của tài khoản benchmark; None khi không đọc được."""
    listing = tools.list_my_datasets(api)
    if not listing.get("ok"):
        return None
    return {d.get("_id"): d.get("dataName") for d in listing.get("datasets") or []}


_CONTENT_ROWS_LIMIT = 60_000


def _describe_dataset(api, dataset_id: str) -> dict:
    """
    Số dòng, tên cột và dấu vân tay NỘI DUNG của dataset vừa tạo trong ca (nhóm S): đúng hình dạng chưa đủ,
    phải đúng các dòng cần nhập (vd đúng các mẫu age = 28). Chỉ lưu hash, không chép dữ liệu vào run.json.
    """
    from benchmark.common import content_fingerprint

    schema = tools.get_dataset_schema(api, dataset_id)
    if not schema.get("ok"):
        return {"ok": False, "error": schema.get("error")}
    info = {"ok": True, "rows": schema.get("total_rows"), "columns": [c.get("name") for c in schema.get("columns") or []]}
    if isinstance(info["rows"], int) and 0 < info["rows"] <= _CONTENT_ROWS_LIMIT:
        try:
            records = (api.get_dataset_preview(dataset_id, num_rows=info["rows"]) or {}).get("records") or []
            info["content_rows"] = len(records)
            info["content_sha256"] = content_fingerprint(records)
        except Exception as error:  # noqa: BLE001 - thiếu bằng chứng nội dung là lỗi đo, không phải lỗi agent
            info["content_error"] = f"{type(error).__name__}: {error}"
    return info


def _delete_dataset(api, dataset_id: str) -> dict:
    """Xoá dataset ca vừa tạo (chỉ bản ghi tbl_Data; job và model đã train không bị xoá)."""
    try:
        api._request("DELETE", f"/datasets/{dataset_id}")
        return {"ok": True}
    except Exception as error:  # noqa: BLE001 - dọn dẹp lỗi thì ghi lại, không đổi kết quả đo
        return {"ok": False, "error": f"{type(error).__name__}: {error}"}


def _db_probe(api, probe: dict, values: dict) -> dict:
    """
    Đọc trạng thái bảng nguồn qua API của backend (cùng đường chỉ đọc mà agent dùng), trước và sau ca
    S07: chứng minh database KHÔNG bị ghi - kể cả khi agent cố gửi câu lệnh ghi.
    """
    connection = substitute(probe["connection"], values)
    try:
        result = api.preview_database_query(connection, {"kind": "sql", "sql": probe["sql"], "params": {}, "row_limit": 5})
        return {"ok": True, "rows": [list(r.values()) if isinstance(r, dict) else r for r in result.get("rows") or []]}
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": f"{type(error).__name__}: {error}"}


def _usage_now() -> dict:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # Linux: ru_maxrss tính bằng KB, là đỉnh của CẢ tiến trình (tăng dần qua các lượt, không reset được).
    return {"cpu": usage.ru_utime + usage.ru_stime, "maxrss_mb": usage.ru_maxrss / 1024, "wall": time.monotonic()}


def rows_key(case: dict) -> str:
    """Khoá của predict_rows trong config: mặc định theo dataset; S06 (cột chữ thường từ PostgreSQL) có khoá riêng."""
    return case["task"].get("rows_key", case["task"]["dataset"])


def build_turns(case: dict, cases_doc: dict, cfg: dict) -> list:
    """Danh sách lượt; None = chờ job do lượt trước tạo ra chạy xong."""
    values = cfg["placeholders"]
    turns = [substitute(t, values) for t in case["turns"]]
    if case["flow"] == "train":
        rows = json.dumps(cfg["predict_rows"][rows_key(case)], ensure_ascii=False, separators=(",", ":"))
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
        datasets_before = _datasets(harness_api)
        run["account_dataset_ids"] = list(datasets_before) if datasets_before is not None else None
        run["account_datasets"] = datasets_before
        if case["flow"] == "train":
            run["expected_predict_rows"] = cfg["predict_rows"][rows_key(case)]
        if case.get("db_probe"):
            run["db_probe_before"] = _db_probe(harness_api, case["db_probe"], values)

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

        # Người dùng mô phỏng bấm nút trên thẻ xác nhận theo chính sách cố định của ca (consent.py).
        policy = consent.policy_for(case, cases_doc)
        run["consent_policy"] = policy
        run["consent"] = []
        own_jobs: set[str] = set()
        max_continuations = int(cfg.get("max_continuations", 2))
        usage_start = _usage_now()

        def expected_config() -> dict | None:
            """Config người dùng đã yêu cầu (đáp án của ca); dataset nhập trong ca thay cho <IMPORTED_ID>."""
            from benchmark.analyze import task_config
            imports = list(session.team.handoff.imported_datasets)
            return task_config(case, {**values, **({"IMPORTED_ID": imports[0]} if len(imports) == 1 else {})})

        def process(stage: str) -> list[dict]:
            decisions = consent.process_pending(session, policy, record, own_jobs, stage, expected_config())
            run["consent"].extend(decisions)
            return decisions

        def send(prompt: str, kind: str) -> None:
            record("user", prompt)
            before = time.monotonic()
            turn = {"prompt": prompt, "kind": kind}
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

        # Từ đây agent đã nhận yêu cầu. Bị ngắt thì lượt được giữ và tính FAIL, không chạy
        # lại: chạy lại sẽ xoá một kết quả đã quan sát được và mở đường chọn lượt tốt.
        run["interrupted"] = "Lượt bị ngắt sau khi agent đã nhận prompt; không chạy lại."
        save()
        run_cfg = {**cfg, "placeholders": values}
        turns = build_turns(case, cases_doc, run_cfg)
        decisions: list[dict] = []
        for index, prompt in enumerate(turns):
            if prompt is None:
                waited = _wait_watchers(session, max_wait)
                record("wait", waited)
                run["job_wait"] = waited
                # Watcher có thể đưa thẻ kích hoạt khi job xong (ràng buộc chỉ đạt theo điểm CV).
                process("after_job")
                continue
            send(prompt, "scripted")
            decisions = process(f"turn{index + 1}")
        # Thẻ bật/tắt model được xác nhận SAU lượt cuối (kể cả thẻ watcher đưa ra khi job xong trong lúc chờ
        # cuối): người dùng thật sẽ nhắn tiếp để agent làm nốt việc (vd đã bật model thì gọi predict). Câu nhắn
        # cố định, tối đa max_continuations lần, đếm vào lượt chat. Mỗi vòng hoặc dừng, hoặc tăng bộ đếm.
        continuations = 0
        while True:
            if not consent.needs_followup(decisions):
                # Không để job của ca này tranh tài nguyên với ca sau.
                run["final_wait"] = _wait_watchers(session, max_wait)
                decisions = process("final")
                if not consent.needs_followup(decisions):
                    break
            if continuations >= max_continuations:
                break
            continuations += 1
            send(cases_doc["continuation"], "continuation")
            decisions = process(f"continuation{continuations}")
        if "final_wait" not in run:
            # Dừng vì đã hết lượt "tiếp tục": vẫn chờ job và xử lý thẻ lần cuối (không nhắn thêm nữa).
            run["final_wait"] = _wait_watchers(session, max_wait)
            process("final")
        run["continuation_turns"] = continuations
        run["usage"] = dict(session.usage)
        usage_end = _usage_now()
        run["resources"] = {
            "harness_cpu_seconds": usage_end["cpu"] - usage_start["cpu"],
            "harness_wall_seconds": usage_end["wall"] - usage_start["wall"],
            "harness_peak_rss_mb": usage_end["maxrss_mb"],
        }
        handoff = session.team.handoff
        run["handoff"] = {"requirements": handoff.requirements, "configs": handoff.configs, "jobs": handoff.jobs,
                          "imported_datasets": handoff.imported_datasets}
        run["pending_actions_left"] = session.team.actions.pending_public()

        jobs_after = _own_job_ids(harness_api)
        fixture_job = run["fixtures"].get("running_job", {}).get("job_id")
        if jobs_before is None or jobs_after is None:
            run["new_jobs"] = None
            run["errors"].append("Không liệt kê được job để đếm job mới.")
        else:
            run["new_jobs"] = sorted(jobs_after - jobs_before - {fixture_job})
        run["job_snapshots"] = {job_id: _job(harness_api, job_id) for job_id in run["new_jobs"] or []}

        # Dataset tạo trong ca (nhóm S nhập từ database): kiểm số dòng/cột rồi dọn để tài khoản giữ nguyên.
        datasets_after = _datasets(harness_api)
        if datasets_before is None or datasets_after is None:
            run["new_datasets"] = None
            run["errors"].append("Không liệt kê được dataset để đếm dataset mới.")
        else:
            run["new_datasets"] = {d: {"name": datasets_after[d], **_describe_dataset(harness_api, d)}
                                   for d in sorted(set(datasets_after) - set(datasets_before))}
        # Dataset SQL Agent nhập trong phiên (ID thật do backend trả, ghi trong Handoff): không phụ thuộc việc bộ
        # chạy đọc được danh sách dataset hay không.
        if len(handoff.imported_datasets) == 1:
            values["IMPORTED_ID"] = next(iter(handoff.imported_datasets))
        if case.get("db_probe"):
            run["db_probe_after"] = _db_probe(harness_api, case["db_probe"], values)

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
        # Bằng chứng về quá trình train của engine (thời gian, số ứng viên HPO, nguồn điểm) - sau khi job kết thúc.
        run["job_pipelines"] = {job_id: jobinfo.fetch_summary(harness_api, job_id) for job_id in run["new_jobs"] or []}
        # Chỉ xoá dataset mà SQL Agent của CHÍNH phiên này nhập (có trong Handoff) và mới xuất hiện trong ca:
        # không bao giờ đụng dataset có sẵn hay dataset ai đó tải lên cùng lúc.
        imported_now = [d for d in handoff.imported_datasets if datasets_before is not None and d not in datasets_before]
        if cfg.get("cleanup_imported_datasets", True) and imported_now:
            run["dataset_cleanup"] = {d: _delete_dataset(harness_api, d) for d in imported_now}

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
