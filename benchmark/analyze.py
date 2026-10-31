"""
Chấm một lượt chạy: đọc run.json + trace.jsonl (+ test_metrics.json, review.json)
và trả về MỘT dòng kết quả với mọi chỉ số.

Thuần Python, không gọi LLM hay backend: chấm lại bao nhiêu lần cũng được và
cho cùng kết quả. Chỗ nào không đo được thì để None, không bao giờ tự thay bằng 0.
"""

# Standard libraries
import json
import math
import re
from pathlib import Path

# Local modules
from benchmark.common import load_json, read_trace, substitute


# Lỗi do LLM gọi tool sai schema (tên tool, tham số, JSON) - chuỗi lấy từ agent_openai._call_tool.
_SCHEMA_ERRORS = (
    "Tham số tool không phải JSON hợp lệ",
    "Tham số không hợp lệ cho",
    "Tool không tồn tại",
)
_INJECTED = "Injected"
_DATASET_TOOLS = ("get_dataset_info", "get_dataset_schema", "submit_config")
_HEX_ID = re.compile(r"\b[0-9a-f]{24}\b")
_LOWER_IS_BETTER = {"mse", "mae", "mape", "rmse"}
_OPS = {">=": lambda a, b: a >= b, ">": lambda a, b: a > b, "<=": lambda a, b: a <= b, "<": lambda a, b: a < b}
CONFIG_FIELDS = ("dataset_id", "target", "list_feature", "metric_sort", "problem_type", "search_algorithm", "max_time")


def _same(expected, actual) -> bool:
    if isinstance(expected, list):
        return isinstance(actual, list) and {str(v) for v in expected} == {str(v) for v in actual}
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            return float(actual) == float(expected)
        except (TypeError, ValueError):
            return False
    return str(expected).strip().lower() == str(actual).strip().lower()


def _args_match(expected: dict, actual: dict) -> bool:
    return all(_same(v, (actual or {}).get(k)) for k, v in expected.items())


def _finite_number(value) -> bool:
    """Số hữu hạn, nhận cả chuỗi số: backend trả nhãn phân loại dạng "1" (LabelEncoder fit trên astype(str))."""
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _mentions(text: str, word: str) -> bool:
    """
    word đứng thành token riêng: "K" không khớp "Kết", "accuracy" không khớp "balanced_accuracy".

    Tên có chữ hoa (tên cột) so đúng hoa thường để "Ba" không khớp chữ "ba"; tên viết
    thường (metric) thì không phân biệt. "_" khớp cả "\\_" của markdown, dấu cách và
    "-" (F1-macro), "²" tính như "2" (R²).
    """
    text = text.replace("\\_", "_").replace("²", "2")
    body = r"[_\s-]".join(re.escape(part) for part in word.split("_"))
    flags = 0 if any(c.isupper() for c in word) else re.IGNORECASE
    # "balanced accuracy" viết cách vẫn là balanced_accuracy, không phải accuracy.
    return re.search(rf"(?<!\w)(?<!balanced[_\s-]){body}(?!\w)", text, flags) is not None


def _same_rows(sent: list, expected: list) -> bool:
    """Agent gửi đúng mẫu người dùng đưa: cùng số dòng, cùng thứ tự, mọi giá trị khớp."""
    if not isinstance(sent, list) or len(sent) != len(expected):
        return False
    try:
        return all(isinstance(s, dict) and all(math.isclose(float(s[k]), float(v), rel_tol=1e-9, abs_tol=1e-12)
                                               for k, v in e.items())
                   for s, e in zip(sent, expected))
    except (KeyError, TypeError, ValueError):
        return False


def _effective_config(arguments: dict, result: dict | None) -> dict:
    """Config tool thực sự nhận: trường được phép bỏ trống (problem_type lấy từ R) đã được điền. Bị từ chối thì chấm tham số thô."""
    accepted = (result or {}).get("config") if (result or {}).get("ok") else None
    return {**arguments, **accepted} if accepted else arguments


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[index]


def _pair_durations(events: list[dict], start: str, end: str, key: str) -> list[tuple[str, float]]:
    """Ghép sự kiện bắt đầu/kết thúc theo key (tool lồng nhau: ask_* bọc tool của sub-agent)."""
    open_by_key: dict[str, list[float]] = {}
    pairs = []
    for event in events:
        name = event.get(key)
        if event["type"] == start:
            open_by_key.setdefault(name, []).append(event["time"])
        elif event["type"] == end and open_by_key.get(name):
            pairs.append((name, event["time"] - open_by_key[name].pop()))
    return pairs


def task_config(case: dict, values: dict) -> dict | None:
    task = case.get("task")
    if not task:
        return None
    return {
        "dataset_id": substitute(task["dataset_id"], values),
        "target": task["target"],
        "list_feature": task["features"],
        "metric_sort": task["metric"],
        "problem_type": task["problem_type"],
        "search_algorithm": task["search_algorithm"],
        "max_time": task["max_time"],
    }


def _config_accuracy(expected: dict, actual: dict) -> tuple[int, int, list[str]]:
    """All seven required fields count; omitting a field cannot improve accuracy."""
    wrong = [f for f in CONFIG_FIELDS if actual.get(f) in (None, "") or not _same(expected[f], actual[f])]
    return len(CONFIG_FIELDS) - len(wrong), len(CONFIG_FIELDS), wrong


def _job_matches_task(job: dict, expected: dict) -> list[str]:
    """Trường config của job thật lệch so với nhiệm vụ. Backend lưu max_time dưới tên timeout."""
    config = job.get("config") or {}
    actual = {
        "dataset_id": (job.get("data") or {}).get("id") or (job.get("data") or {}).get("_id"),
        "target": config.get("target"),
        "list_feature": config.get("list_feature"),
        "metric_sort": config.get("metric_sort"),
        "problem_type": config.get("problem_type"),
        "search_algorithm": config.get("search_algorithm"),
        "max_time": config.get("timeout", config.get("max_time")),
    }
    return [f for f in CONFIG_FIELDS if actual[f] is None or not _same(expected[f], actual[f])]


def cost_of(usage: dict, pricing: dict | None, provider=None, model=None) -> tuple[float | None, str]:
    if not usage or not usage.get("calls"):
        return None, "incomplete"
    price_in = (pricing or {}).get("input_price_usd_per_million")
    price_out = (pricing or {}).get("output_price_usd_per_million")
    if price_in is None or price_out is None:
        return None, "unavailable"
    if provider != pricing.get("provider") or model != pricing.get("model"):
        return None, "model_mismatch"
    if pricing.get("billing_mode") != "uniform_input_output":
        return None, "incomplete"
    if not all(isinstance(p, (int, float)) and not isinstance(p, bool) and math.isfinite(p) and p >= 0
               for p in (price_in, price_out)):
        return None, "invalid_pricing"
    cost = (usage["prompt_tokens"] * price_in + usage["completion_tokens"] * price_out) / 1_000_000
    # total > prompt + completion: có token suy luận tính riêng mà bảng giá chưa mô tả.
    hidden = usage["total_tokens"] - usage["prompt_tokens"] - usage["completion_tokens"]
    return (None, "incomplete") if hidden != 0 or usage.get("missing_usage_calls") else (cost, "estimated")


def analyze_run(folder: Path, case: dict, pricing: dict | None = None) -> dict:
    run = load_json(folder / "run.json")
    trace = read_trace(folder / "trace.jsonl")
    review = load_json(folder / "review.json")
    test = load_json(folder / "test" / "test_metrics.json")
    test_error = load_json(folder / "test" / "error.json")
    values = run.get("placeholders") or {}
    expect = substitute(case.get("expect", {}), values)

    events = [r["data"] for r in trace if r["record"] == "event"]
    tool_calls = [e for e in events if e["type"] == "tool_call"]
    business = [e for e in tool_calls if not str(e.get("name", "")).startswith("ask_")]
    # Tiêu chí về nội dung xét câu trả lời của lượt cuối: D05 phải trả lời đúng ở lượt 2.
    answer = (run["turns"][-1].get("answer") or "") if run["turns"] else ""
    turn_errors = [t["error"] for t in run["turns"] if t.get("error")]
    checks: list[dict] = []

    def check(name: str, passed, detail="") -> None:
        checks.append({"check": name, "passed": passed, "detail": detail})

    def called(tool: str) -> list[dict]:
        return [e for e in tool_calls if e.get("name") == tool]

    # ---------------------------------------------------------- tiêu chí của ca
    new_jobs = run.get("new_jobs")
    if "max_new_jobs" in expect:
        check("max_new_jobs", None if new_jobs is None else len(new_jobs) <= expect["max_new_jobs"], f"{new_jobs}")
    if "min_new_jobs" in expect:
        check("min_new_jobs", None if new_jobs is None else len(new_jobs) >= expect["min_new_jobs"], f"{new_jobs}")

    for tool in expect.get("tools_required", []):
        check(f"called:{tool}", bool(called(tool)))
    forbidden_hits = [t for t in expect.get("tools_forbidden", []) if called(t)]
    for tool in expect.get("tools_forbidden", []):
        check(f"not_called:{tool}", tool not in forbidden_hits)
    for spec in expect.get("tool_args", []):
        check(f"args:{spec['tool']}", any(_args_match(spec["args"], e.get("arguments")) for e in called(spec["tool"])), json.dumps(spec["args"], ensure_ascii=False))
    if expect.get("tool_args_any"):
        hit = any(
            _args_match(spec["args"], e.get("arguments"))
            for spec in expect["tool_args_any"] for e in called(spec["tool"])
        )
        check("args:any", hit)
    if expect.get("reads_schema"):
        # Tính cả lần Handoff đọc schema bằng code (không có Data Agent), không chỉ tool call của LLM.
        reads = [r["data"] for r in trace if r["record"] == "schema_read"]
        check("read:get_dataset_schema", any(r["ok"] and r["dataset_id"] == expect["reads_schema"] for r in reads),
              expect["reads_schema"])

    if expect.get("answer_contains_all"):
        missing = [w for w in expect["answer_contains_all"] if not _mentions(answer, w)]
        check("answer_contains_all", not missing, f"thiếu: {missing}" if missing else "")
    if expect.get("answer_lists_all_datasets"):
        account = set(run.get("account_dataset_ids") or [])
        mentioned = set(_HEX_ID.findall(answer))
        check("answer_lists_all_datasets", None if run.get("account_dataset_ids") is None else account <= mentioned,
              f"thiếu {sorted(account - mentioned)}")
        check("answer_no_invented_ids", None if run.get("account_dataset_ids") is None else mentioned <= account,
              f"ID lạ {sorted(mentioned - account)}")
        if run.get("account_datasets") is not None:
            names = [n for n in run["account_datasets"].values() if n]
            missing_names = [n for n in names if not _mentions(answer, n)]
            check("answer_lists_dataset_names", not missing_names, f"thiếu tên {missing_names}" if missing_names else "")
    if expect.get("only_dataset"):
        stray = [
            e for e in tool_calls
            if e.get("ok") and e.get("name") in _DATASET_TOOLS
            and (e.get("arguments") or {}).get("dataset_id") not in (None, expect["only_dataset"])
        ]
        check("only_requested_dataset", not stray, f"{[e['arguments'].get('dataset_id') for e in stray]}")

    # Ca chỉ định job để predict (D02, E03) thì lời gọi thành công phải đúng job đó.
    asked_jobs = {s["args"]["job_id"] for s in expect.get("tool_args", []) if s["tool"] == "predict" and "job_id" in s["args"]}

    def on_asked_job(call: dict) -> bool:
        return not asked_jobs or (call.get("arguments") or {}).get("job_id") in asked_jobs

    predicts_ok = [e for e in called("predict") if e.get("ok")]
    outputs = [r["data"] for r in trace if r["record"] == "tool_result"]
    # Mẫu người dùng đưa (D02/E03 trong expect, nhóm C trong config): agent phải gửi đúng mẫu đó.
    expected_rows = expect.get("predict_rows") or run.get("expected_predict_rows")

    # A successful HTTP/tool flag alone cannot prove an actual prediction.
    def valid_prediction(result):
        predictions = (result.get("result") or {}).get("predictions") or []
        rows = (result.get("arguments") or {}).get("rows") or []
        return (bool(rows) and len(predictions) == len(rows)
                and (expected_rows is None or _same_rows(rows, expected_rows))
                and all(isinstance(p, dict) and _finite_number(p.get("predict")) for p in predictions))
    valid_outputs = [o for o in outputs if o.get("name") == "predict" and valid_prediction(o)]
    if predicts_ok:
        check("prediction_output", any(on_asked_job(o) for o in valid_outputs))
    if "predict_ok" in expect:
        check("predict_ok" if expect["predict_ok"] else "no_successful_predict",
              any(on_asked_job(e) for e in predicts_ok) == expect["predict_ok"])
    if expect.get("inactive_unchanged"):
        fixture = run["fixtures"].get("inactive_job", {})
        toggled = [e for e in called("activate_model") if (e.get("arguments") or {}).get("job_id") == expect["inactive_unchanged"]]
        check("inactive_unchanged", fixture.get("activate_after") == fixture.get("activate_before") and not toggled,
              f"{fixture.get('activate_before')} -> {fixture.get('activate_after')}")

    # ------------------------------------------------------------ config
    expected_config = task_config(case, values)
    checked = [e for e in events if e["type"] == "config_checked"]
    submits = called("submit_config")
    final_configs = list(((run.get("handoff") or {}).get("configs") or {}).values())
    # Config đã bị config mới hơn thay thế thì không chạy được nữa (team.start_training).
    runnable = [c for c in final_configs if not c.get("superseded_by")]
    config_metrics = {"first_config_valid": None, "first_config_rejected": None,
                      "config_field_accuracy": None, "config_wrong_fields": None}
    # Chỉ số điền config chỉ tính B/C: ở nhóm E lỗi chèn có thể làm hỏng lần submit đầu.
    if expect.get("config") == "match_task" and case["group"] in ("B", "C"):
        config_metrics["first_config_valid"] = bool(checked and checked[0].get("ok"))
        config_metrics["first_config_rejected"] = bool(checked and not checked[0].get("ok"))
        first = next((o for o in outputs if o.get("name") == "submit_config"), None)
        if first or submits:
            arguments = (first or submits[0]).get("arguments") or {}
            right, total, wrong = _config_accuracy(expected_config, _effective_config(arguments, (first or {}).get("result")))
            config_metrics["config_field_accuracy"] = right / total if total else None
            config_metrics["config_wrong_fields"] = wrong
    if expect.get("config") == "match_task":
        correct_final = [
            c for c in runnable
            if not _job_matches_task({"config": {**c["config"], "timeout": c["config"].get("max_time")},
                                      "data": {"id": c["dataset_id"]}}, expected_config)
        ]
        check("valid_config_matches_task", bool(correct_final), f"{len(runnable)} config chạy được")
    if expect.get("config") == "match_task" and case.get("original_task"):
        # Ca sửa yêu cầu (F02): config theo yêu cầu ban đầu phải được chốt TRƯỚC lượt sửa, rồi bị
        # config mới thay thế. Chốt cả hai trong lượt sửa không chứng minh agent đã sửa một config có sẵn.
        original = task_config({"task": case["original_task"]}, values)

        def is_original(config: dict, dataset_id) -> bool:
            return not _job_matches_task({"config": {**config, "timeout": config.get("max_time")},
                                          "data": {"id": dataset_id}}, original)

        user_times = [r["at"] for r in trace if r["record"] == "user"]
        revision_at = user_times[1] if len(user_times) > 1 else float("inf")
        before_revision = [r["data"] for r in trace if r["record"] == "tool_result" and r["at"] < revision_at
                           and r["data"]["name"] == "submit_config" and (r["data"]["result"] or {}).get("ok")]
        accepted_early = any(is_original(o["result"]["config"], (o["arguments"] or {}).get("dataset_id"))
                             for o in before_revision)
        replaced = any(c.get("superseded_by") and is_original(c["config"], c["dataset_id"]) for c in final_configs)
        check("replaced_original_config", accepted_early and replaced,
              "config ban đầu phải được chốt ở lượt 1 rồi bị thay ở lượt sửa")
    elif expect.get("config") == "none":
        accepted = [e for e in checked if e.get("ok")]
        check("no_config_accepted", not accepted and not final_configs, f"{len(accepted)} config được chấp nhận")

    # ------------------------------------------------------- nhóm C: SR/NPS/CS
    sr = nps = cs = None
    workflow_pass = all_constraints_pass = None
    measurement = "complete"
    wrong_task = None
    main_job = None
    if case["flow"] in ("train", "train_start") and new_jobs:
        handoff_jobs = list(((run.get("handoff") or {}).get("jobs") or {}))
        main_job = next((j for j in handoff_jobs if j in new_jobs), new_jobs[0])
    snapshot = (run.get("job_snapshots") or {}).get(main_job) if main_job else None
    job_success = bool(snapshot and snapshot.get("status") == 1)
    if case["flow"] in ("train", "train_start"):
        check("job_succeeded", job_success if new_jobs is not None else None, f"job {main_job}")
    if case["flow"] == "train_start" and snapshot and expected_config:
        wrong_task = _job_matches_task(snapshot, expected_config)
        check("right_task", not wrong_task, f"lệch: {wrong_task}")
    if case["flow"] == "train":
        constraints = case.get("constraints") or []
        if snapshot and expected_config:
            wrong_task = _job_matches_task(snapshot, expected_config)
        endpoint = job_success and snapshot.get("activate") == 1 and any(
            (e.get("arguments") or {}).get("job_id") == main_job for e in predicts_ok
        ) and any(
            (o.get("arguments") or {}).get("job_id") == main_job for o in valid_outputs
        )
        check("activated_and_predicted", endpoint)
        workflow_pass = bool(job_success and endpoint and not wrong_task and len(new_jobs or []) == 1)

        if test and (test.get("job_id") != main_job or test.get("protocol_id") != run.get("protocol_id")
                     or not isinstance(test.get("nps"), (int, float))
                     or not math.isfinite(test["nps"]) or not 0 <= test["nps"] <= 1):
            test = None
            test_error = {"error": "test_metrics không khớp job hoặc NPS không hợp lệ"}
        results = []
        if test:
            for c in constraints:
                score = test.get(c["metric"])
                results.append(None if score is None else _OPS[c["op"]](score, c["value"]))
        if constraints:
            if not job_success or wrong_task or not endpoint:
                all_constraints_pass = False
            elif test and None not in results:
                all_constraints_pass = all(results) and workflow_pass
                for c, ok in zip(constraints, results):
                    check(f"test:{c['metric']}{c['op']}{c['value']}", ok)
            else:
                measurement = "incomplete"
                check("test_constraints", None, "chưa có test_metrics.json")

        if wrong_task:
            sr, nps = 0.0, 0.0
        elif not job_success:
            sr, nps = 0.0, 0.0
        elif not constraints:
            sr = 1.0 if endpoint else 0.5
        elif not endpoint:
            sr = 0.25
        elif all_constraints_pass is None:
            sr = 0.5  # chưa chấm test: chỉ chắc chắn tới mức endpoint chạy
        elif all(results):
            # Mức SR chỉ xét ngưỡng test; job thừa đã trượt ở max_new_jobs và workflow_pass.
            sr = 1.0
        elif len(constraints) > 1 and any(results):
            sr = 0.75
        else:
            sr = 0.5
        if nps is None:
            nps = test.get("nps") if test else None
            if nps is None:
                measurement = "incomplete"
        cs = 0.5 * sr + 0.5 * nps if sr is not None and nps is not None else None
        if wrong_task:
            check("right_task", False, f"lệch: {wrong_task}")
        if test_error:
            measurement = "error"

    # ------------------------------------------------------------ trạng thái
    # INVALID_FIXTURE chỉ khi điều kiện của ca hỏng ngoài tầm agent. Agent không
    # đọc trạng thái job hay không chạm tới bước bị chèn lỗi thì trượt tiêu chí
    # của ca: đó là FAIL, không được loại khỏi mẫu số hay chạy lại.
    invalid_fixture = None
    running = run["fixtures"].get("running_job")
    if running and running.get("status_before") != 0:
        invalid_fixture = "Job fixture không còn chạy trước khi agent được hỏi."
    elif running and [s for s in running.get("observed_statuses", []) if s is not None][:1] not in ([], [0]):
        # Chỉ lần đọc đầu tiên quyết định: đã thấy đang chạy thì điều kiện ca đã đạt, job
        # xong sau đó là diễn biến bình thường và agent vẫn được chấm.
        invalid_fixture = "Job fixture đã kết thúc trước lần agent đọc trạng thái đầu tiên."
    if run["fixtures"].get("inactive_job") and run["fixtures"]["inactive_job"].get("activate_before") not in (0, False):
        invalid_fixture = "Job fixture INACTIVE_JOB đang được kích hoạt sẵn."
    if run["fixtures"].get("glass_job") and run["fixtures"]["glass_job"].get("activate_before") != 1:
        invalid_fixture = "Job fixture GLASS_JOB không ở trạng thái kích hoạt trước ca."
    # Bộ chạy không đọc được backend thì không đủ bằng chứng để chấm agent: lỗi đo, chạy lại lượt.
    gaps = []
    if run.get("new_jobs") is None:
        gaps.append("danh sách job")
    if any(not isinstance(s, dict) or not isinstance(s.get("status"), int) for s in (run.get("job_snapshots") or {}).values()):
        gaps.append("snapshot job")
    if expect.get("answer_lists_all_datasets") and run.get("account_dataset_ids") is None:
        gaps.append("danh sách dataset")
    if run["fixtures"].get("inactive_job") and run["fixtures"]["inactive_job"].get("activate_after") is None:
        gaps.append("trạng thái INACTIVE_JOB sau ca")
    if run.get("interrupted"):
        # Lượt đã bắt đầu rồi bị ngắt: giữ trong mẫu số là FAIL, không coi là lỗi đo để chạy lại.
        check("not_interrupted", False, run["interrupted"])
    elif gaps and not invalid_fixture:
        invalid_fixture = f"Bộ chạy không đọc được {', '.join(gaps)} từ backend; lỗi đo, không phải lỗi agent."
    if turn_errors:
        check("no_turn_error", False, turn_errors[0])
    if run.get("halt_reason"):
        check("backend_settled", False, run["halt_reason"])
    faults_fired = [r["data"] for r in trace if r["record"] == "fault"]
    faults_missing = bool(case.get("faults")) and len(faults_fired) != sum(f.get("times", 1) for f in case["faults"])

    auto = [c["passed"] for c in checks]
    manual = expect.get("manual")
    if invalid_fixture:
        status, reason = "INVALID_FIXTURE", invalid_fixture
    elif False in auto:
        status = "FAIL"
        reason = "; ".join(f"{c['check']} {c['detail']}".strip() for c in checks if c["passed"] is False)
    elif faults_missing:
        status, reason = "INVALID_FIXTURE", "Lỗi chèn chưa kích hoạt dù agent đạt mọi tiêu chí tự động; chưa đo được phục hồi."
    elif None in auto:
        status, reason = "PENDING", "; ".join(c["check"] for c in checks if c["passed"] is None)
        measurement = "incomplete"
    elif review and review.get("verdict") in ("PASS", "FAIL"):
        status, reason = review["verdict"], review.get("note")
    elif manual:
        status, reason = "PENDING_REVIEW", manual
    else:
        status, reason = "PASS", None
    if status == "INVALID_FIXTURE":
        # Lượt không hợp lệ không có điểm: SR/NPS/CS=0 hay job fail không được kéo trung bình.
        sr = nps = cs = None
        workflow_pass = all_constraints_pass = job_success = None

    # --------------------------------------------------------- bước, chi phí, thời gian
    llm_calls = [e for e in events if e["type"] == "llm_call"]
    llm_seconds = [r["data"]["seconds"] for r in trace if r["record"] == "llm_timing"]
    agent_time: dict[str, float] = {}
    for agent, seconds in _pair_durations(events, "agent_start", "agent_done", "agent"):
        agent_time[agent] = agent_time.get(agent, 0.0) + seconds
    tool_latency = [s for name, s in _pair_durations(events, "tool_start", "tool_call", "name") if not name.startswith("ask_")]
    steps_by_agent: dict[str, int] = {}
    for e in llm_calls:
        steps_by_agent[e.get("agent")] = steps_by_agent.get(e.get("agent"), 0) + 1
    step_limit = sum(1 for e in events if e["type"] == "agent_done" and "chạy quá" in str(e.get("error")))
    step_limit += sum(1 for t in run["turns"] if "bước mà chưa xong" in (t.get("answer") or ""))

    user_times = [r["at"] for r in trace if r["record"] == "user"]
    reply_times = [r["at"] for r in trace if r["record"] == "assistant"]
    usage = run.get("usage") or {}
    timings = [r["data"] for r in trace if r["record"] == "llm_timing"]
    if any(t.get("missing_usage") for t in timings):
        usage = {**usage, "missing_usage_calls": sum(bool(t.get("missing_usage")) for t in timings)}
    cost, cost_status = cost_of(usage, pricing, run.get("provider"), run.get("model"))
    if run.get("interrupted") and cost_status == "estimated":
        # Usage của lượt bị ngắt chưa đủ: không báo một phần chi phí như chi phí cả lượt.
        cost, cost_status = None, "incomplete"

    # ------------------------------------------------------- tool/API call accuracy
    schema_invalid = [e for e in tool_calls if str(e.get("error") or "").startswith(_SCHEMA_ERRORS)]
    injected_failures = [e for e in business if not e.get("ok") and _INJECTED in str(e.get("error"))]
    per_tool: dict[str, list[int]] = {}
    for e in business:
        ok, total = per_tool.setdefault(e["name"], [0, 0])
        per_tool[e["name"]] = [ok + bool(e.get("ok")), total + 1]
    required = expect.get("tools_required", []) + [s["tool"] for s in expect.get("tool_args", [])]
    if expect.get("tool_args_any"):
        required.append("any")
    if expect.get("reads_schema"):
        required.append("get_dataset_schema")

    # ----------------------------------------------------------- khả năng tự phục hồi
    expected_failures = set()
    if expect.get("config") == "none":
        expected_failures.add("submit_config")
    if expect.get("predict_ok") is False:
        expected_failures |= {"predict", "activate_model"}
    if expect.get("only_dataset"):
        expected_failures |= set(_DATASET_TOOLS)
    # Tính cả ask_*: sub-agent trả lỗi cho Manager cũng là một agent bị lỗi cần tự sửa.
    episodes = recovered = 0
    for index, e in enumerate(tool_calls):
        if e.get("ok") or e["name"] in expected_failures:
            continue
        episodes += 1
        if any(later.get("ok") and later["name"] == e["name"] for later in tool_calls[index + 1:]):
            recovered += 1
    agent_failures = [e for e in events if e["type"] == "agent_done" and not e.get("ok")]
    agent_recovered = sum(
        1 for i, e in enumerate(events)
        if e["type"] == "agent_done" and not e.get("ok")
        and any(l["type"] == "agent_done" and l.get("ok") and l.get("agent") == e.get("agent") for l in events[i + 1:])
    )

    return {
        "scenario_id": case["id"], "group": case["group"], "variant": run["variant"], "repeat": run["repeat"],
        "phase": run.get("phase"), "provider": run.get("provider"), "model": run.get("model"), "commit": run.get("commit"),
        "protocol_id": run.get("protocol_id"),
        "task_status": status, "failure_reason": reason, "measurement_status": measurement,
        "checks": checks, "manual_criteria": manual,
        "workflow_pass": workflow_pass, "all_constraints_pass": all_constraints_pass,
        "has_constraints": bool(case.get("constraints")),
        "wrong_task": wrong_task or None, "job_ids": new_jobs, "main_job": main_job, "job_success": job_success if main_job else None,
        "sr": sr, "nps": nps, "cs": cs, "score_source": test.get("score_source") if test else None,
        "accuracy": (test or {}).get("accuracy"), "f1_macro": (test or {}).get("f1_macro"),
        "mae": (test or {}).get("mae"), "r2": (test or {}).get("r2"),
        "backend_best_score": snapshot.get("best_score") if snapshot else None,
        **config_metrics,
        # Bước
        # Đếm mọi lời gọi gửi tới provider (kể cả trả về thiếu usage); theo agent chỉ có lời gọi có usage.
        "chat_turns": len(run["turns"]), "llm_calls": len(llm_seconds), "llm_calls_by_agent": steps_by_agent,
        "tool_calls": len(business), "delegations": len(tool_calls) - len(business), "step_limit_hits": step_limit,
        "turn_budget_exceeded": sum(1 for e in events if e["type"] == "turn_budget_exceeded"),
        # Chi phí
        "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"), "llm_cost_usd": cost, "cost_status": cost_status,
        # Có lời gọi thiếu usage thì tổng token thấp hơn thực tế: báo cáo chỉ lấy trung bình trên lượt đủ.
        # Bị ngắt giữa lượt thì usage của lượt dở chưa kịp ghi: tổng token không đủ.
        "token_status": "incomplete" if usage.get("missing_usage_calls") or run.get("interrupted") else "complete",
        # Thời gian
        "agent_seconds": sum(t.get("seconds", 0) for t in run["turns"]),
        "agent_seconds_by_agent": agent_time,
        "llm_seconds_total": sum(llm_seconds) if llm_seconds else None,
        "llm_latency_p50": _percentile(llm_seconds, 0.5), "llm_latency_p95": _percentile(llm_seconds, 0.95),
        "tool_latency_p50": _percentile(tool_latency, 0.5), "tool_latency_p95": _percentile(tool_latency, 0.95),
        "llm_latencies": llm_seconds, "tool_latencies": tool_latency,
        "job_wait_seconds": (run.get("job_wait") or {}).get("seconds"),
        "e2e_wall_seconds": (reply_times[-1] - user_times[0]) if user_times and reply_times else None,
        # Tool/API call accuracy
        "tool_calls_all": len(tool_calls), "tool_schema_invalid": len(schema_invalid),
        "tool_successes": sum(1 for e in business if e.get("ok")), "tool_injected_failures": len(injected_failures),
        "tool_expected_failures": sum(1 for e in business if not e.get("ok") and e["name"] in expected_failures
                                      and _INJECTED not in str(e.get("error"))),
        "tool_by_name": per_tool,
        "required_tools_total": len(required),
        "required_tools_hit": sum(1 for c in checks if c["check"].startswith(("called:", "args:", "read:")) and c["passed"]),
        "forbidden_tool_violations": len(forbidden_hits),
        # Tự phục hồi
        "error_episodes": episodes, "error_recovered": recovered,
        "agent_failures": len(agent_failures), "agent_recovered": agent_recovered,
        "config_rejections": sum(1 for e in checked if not e.get("ok")),
        "config_self_corrected": bool(expect.get("config") == "match_task" and checked and not checked[0].get("ok")
                                      and any(e.get("ok") for e in checked)),
        "faults_injected": len(faults_fired), "turn_errors": len(turn_errors),
        "trace_path": str(folder),
    }
