"""
Kiểm tra bộ benchmark không cần LLM, backend hay job thật.

Backend giả + LLM giả chạy theo kịch bản đi qua đúng đường runner -> analyze ->
scoring -> report, để chắc chắn chỉ số được tính đúng trước khi tốn tiền chạy thật.

    src/backend/.venv/bin/python -m pytest benchmark/test_bench.py
"""

# Standard libraries
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_REPO), str(_REPO / "src" / "backend")]

# Third party libraries
import pytest  # noqa: E402

# Local modules
from agent import providers  # noqa: E402
from agent.api_client import ApiError  # noqa: E402
from agent.chat import ChatSession  # noqa: E402
from benchmark import report, runner, scoring  # noqa: E402
from benchmark.analyze import analyze_run  # noqa: E402
from benchmark.common import CASES_PATH, load_json  # noqa: E402


GLASS = "aaaaaaaaaaaaaaaaaaaaaa01"
OTHER = "aaaaaaaaaaaaaaaaaaaaaa02"
FEATURES = ["RI", "Na", "Mg", "Al", "Si", "K", "Ca", "Ba", "Fe"]


class FakeBackend:
    """Backend dùng chung trạng thái giữa client của bộ chạy và của agent."""

    jobs: dict = {}
    access_token = "test-token"
    user_id = "user-1"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def close(self):
        pass

    def list_datasets(self):
        return [{"_id": GLASS, "dataName": "glass_train"}, {"_id": OTHER, "dataName": "other"}]

    def get_dataset_info(self, dataset_id):
        return {"_id": dataset_id, "dataName": "glass_train"}

    def get_dataset_preview(self, dataset_id, num_rows=50):
        return {"rows": 171, "records": [{**{f: 1.0 for f in FEATURES}, "Type": t} for t in (1, 2, 3)]}

    def get_dataset_features(self, dataset_id, problem_type):
        return {**{f: problem_type == "regression" for f in FEATURES}, "Type": True}

    def list_jobs(self):
        return list(self.jobs.values())

    def start_training(self, dataset_id, config):
        job_id = f"job-{len(self.jobs) + 1:04d}"
        self.jobs[job_id] = {
            "_id": job_id, "user": {"id": "user-1"}, "status": 1, "activate": 0,
            "config": config, "data": {"id": dataset_id, "name": "glass_train"},
            "best_model": "RF", "best_score": 0.7,
            "orther_model_scores": [{"model_name": "RF", "scores": {"f1_macro": 0.7, "accuracy": 0.8}}],
        }
        return {"job_id": job_id}

    def activate_model(self, job_id, activate):
        self.jobs[job_id]["activate"] = 1 if activate else 0
        return {"endpoint_url": "http://model"}

    def predict(self, job_id, rows, timeout=120.0):
        job = self.jobs.get(job_id)
        if job is not None and not job.get("activate"):
            # Như backend thật (inference/service.py): model chưa kích hoạt thì 403.
            raise ApiError(403, "Model is not activated")
        return {"model_name": "RF", "predictions": [1.0 for _ in rows]}


def reply(content="", tool=None, **arguments):
    calls = None
    if tool:
        calls = [SimpleNamespace(
            id=f"call-{tool}", model_extra={},
            function=SimpleNamespace(name=tool, arguments=json.dumps(arguments)),
        )]
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=calls, model_extra={}))],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20, total_tokens=120),
    )


def found(pattern):
    """Bước kịch bản lấy ID (config_id, job_id) từ những gì agent đã thấy."""
    def pick(messages):
        text = json.dumps(messages, ensure_ascii=False, default=str)
        return re.findall(pattern, text)[-1]
    return pick


class ScriptedLLM:
    def __init__(self, steps):
        self.steps = list(steps)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, model, messages, **kwargs):
        step = self.steps.pop(0)
        return step(messages) if callable(step) else step


GOOD_CONFIG = dict(dataset_id=GLASS, target="Type", list_feature=FEATURES, metric_sort="f1_macro",
                   problem_type="classification", search_algorithm="random_search", max_time=300)
SCRIPTS = {
    ("full", "A01"): [
        reply(tool="ask_data_agent", task="Liệt kê dataset"),
        reply(tool="list_my_datasets"),
        reply("Có 2 dataset"),
        reply(f"Bạn có: {GLASS} (glass_train), {OTHER} (other)."),
    ],
    ("full", "B03"): [
        reply(tool="ask_model_agent", task="Tạo config", dataset_id=GLASS),
        reply(tool="submit_config", **{**GOOD_CONFIG, "target": "NotAColumn", "list_feature": ["RI", "Na"]}),
        reply("Target NotAColumn không tồn tại"),
        reply("Không tạo được cấu hình: cột NotAColumn không có trong dataset."),
    ],
    ("no-validate", "B03"): [
        reply(tool="ask_model_agent", task="Tạo config", dataset_id=GLASS),
        reply(tool="submit_config", **{**GOOD_CONFIG, "target": "NotAColumn", "list_feature": ["RI", "Na"]}),
        reply("Đã chốt config"),
        reply("Đã tạo cấu hình."),
    ],
    ("single-agent", "B01"): [
        reply(tool="submit_config", **GOOD_CONFIG),
        reply("Config hợp lệ, chưa train."),
    ],
    ("full", "E01"): [
        # Lỗi chèn rơi vào bước Handoff đọc schema: ask_model_agent trả lỗi, Manager giao lại.
        reply(tool="ask_model_agent", task="Tạo config", dataset_id=GLASS),
        reply(tool="ask_model_agent", task="Tạo config", dataset_id=GLASS),
        reply(tool="submit_config", **GOOD_CONFIG),
        reply("Config hợp lệ"),
        reply("Đã tạo cấu hình hợp lệ, chưa train."),
    ],
    ("full", "E02"): [
        # Agent hỏi lại thay vì train: không chạm tới start_training nên lỗi chèn không kích hoạt.
        reply("Bạn muốn dùng thuật toán tìm kiếm nào?"),
    ],
    ("full", "C01"): [
        # Lượt 1: chốt config rồi ĐỀ NGHỊ train (thẻ xác nhận); người dùng mô phỏng bấm Xác nhận sau lượt.
        reply(tool="ask_model_agent", task="Tạo config", dataset_id=GLASS),
        reply(tool="submit_config", **GOOD_CONFIG),
        reply("Config hợp lệ"),
        reply(tool="ask_operation_agent", task="Chạy config vừa chốt"),
        lambda m: reply(tool="start_training", config_id=found(r"cfg_[0-9a-f]{6}")(m)),
        reply("Đã gửi thẻ xác nhận"),
        reply("Bạn bấm Xác nhận trên thẻ để chạy train."),
        # Lượt 2: đề nghị kích hoạt (thẻ) - chưa predict được vì model chưa bật.
        lambda m: reply(tool="ask_operation_agent", task=f"Kích hoạt và dự đoán job {found(r'job-[0-9]{4}')(m)}"),
        lambda m: reply(tool="activate_model", job_id=found(r"job-[0-9]{4}")(m)),
        reply("Đã gửi thẻ kích hoạt"),
        reply("Job xong, f1_macro 0.7. Bạn bấm Xác nhận trên thẻ để kích hoạt."),
        # Lượt "tiếp tục" sau khi người dùng mô phỏng xác nhận kích hoạt: predict.
        lambda m: reply(tool="ask_operation_agent", task=f"Dự đoán bằng job {found(r'job-[0-9]{4}')(m)}"),
        lambda m: reply(tool="predict", job_id=found(r"job-[0-9]{4}")(m), rows=[{f: 1.0 for f in FEATURES}]),
        reply("Dự đoán 1"),
        reply("Đã kích hoạt và dự đoán: 1."),
    ],
}


@pytest.fixture
def bench(tmp_path, monkeypatch):
    monkeypatch.setattr(providers, "tracing_enabled", lambda: False)
    FakeBackend.jobs = {}
    current = {}

    def make_session(**_kwargs):
        session = ChatSession(api=FakeBackend(), access_token="test-token", verbose=False)
        session._config = SimpleNamespace(model="test-model", name="test")
        session.llm = ScriptedLLM(SCRIPTS[current["key"]])
        return session

    monkeypatch.setattr(runner, "HAutoMLClient", FakeBackend)
    monkeypatch.setattr(scoring, "HAutoMLClient", FakeBackend)
    monkeypatch.setattr(runner, "ChatSession", make_session)

    test_csv = tmp_path / "glass_test.csv"
    test_csv.write_text("RI,Na,Mg,Al,Si,K,Ca,Ba,Fe,Type\n" + "\n".join(
        ",".join(["1.0"] * 9 + [str(t)]) for t in (1, 1, 2, 1)
    ) + "\n")
    cfg = {
        "placeholders": {"GLASS_ID": GLASS, "MISSING_ID": "c" * 24},
        "predict_rows": {"glass": [{f: 1.0 for f in FEATURES}]},
        "test_sets": {"glass": str(test_csv)},
        "max_wait_seconds": 10,
    }
    cases_doc = load_json(CASES_PATH)
    by_id = {c["id"]: c for c in cases_doc["cases"]}

    def run(variant, case_id):
        current["key"] = (variant, case_id)
        folder = runner.run_case(by_id[case_id], cases_doc, cfg, variant, 1, tmp_path / "runs", "official")
        return folder

    return SimpleNamespace(run=run, by_id=by_id, cfg=cfg, cases_doc=cases_doc, root=tmp_path / "runs")


def test_cases_file_is_consistent():
    cases = load_json(CASES_PATH)["cases"]
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)) == 47
    # 33 ca của v4 giữ nguyên để so với đợt trước; nhóm T (v4.1) và S (v5, SQL Agent) thêm riêng.
    assert sum(c["group"] not in ("T", "S") for c in cases) == 33
    assert [c["id"] for c in cases if c["group"] == "T"] == ["T01", "T02", "T03", "T04", "T05", "T06"]
    assert [c["id"] for c in cases if c["group"] == "S"] == [f"S0{i}" for i in range(1, 9)]
    from benchmark import consent
    doc = load_json(CASES_PATH)
    for case in cases:
        assert case["flow"] in ("chat", "train", "train_start")
        policy = consent.policy_for(case, doc)
        # Người dùng mô phỏng chỉ đồng ý train khi prompt yêu cầu train.
        assert (policy["train"] != "reject") == (case["flow"] in ("train", "train_start")), case["id"]
        if case["flow"] in ("train", "train_start") or case["expect"].get("config") == "match_task":
            assert case.get("task"), case["id"]
        if case.get("task", {}).get("problem_type") == "time_series":
            # Backend tìm cột thời gian trong list_feature: phải có đúng cột đó.
            assert case["task"]["time_column"] in case["task"]["features"], case["id"]


def test_lookup_case_passes_and_counts_steps(bench):
    row = analyze_run(bench.run("full", "A01"), bench.by_id["A01"])
    # Tiêu chí tự động đạt; cặp ID–tên cần người chấm đọc lại.
    assert row["task_status"] == "PENDING_REVIEW", row["checks"]
    assert row["llm_calls"] == 4
    assert row["llm_calls_by_agent"] == {"agent-manager": 2, "data-agent": 2}
    assert row["tool_calls"] == 1 and row["delegations"] == 1
    assert row["total_tokens"] == 480
    assert len(row["llm_latencies"]) == 4


def test_guardrail_blocks_bad_config_and_ablation_removes_it(bench):
    folder = bench.run("full", "B03")
    assert analyze_run(folder, bench.by_id["B03"])["task_status"] == "PENDING_REVIEW"
    (folder / "review.json").write_text(json.dumps({"verdict": "PASS", "note": "Đã đối chiếu giải thích lỗi target."}))
    assert analyze_run(folder, bench.by_id["B03"])["task_status"] == "PASS"
    row = analyze_run(bench.run("no-validate", "B03"), bench.by_id["B03"])
    assert row["task_status"] == "FAIL"
    assert "no_config_accepted" in row["failure_reason"]


def test_single_agent_calls_business_tools_directly(bench):
    row = analyze_run(bench.run("single-agent", "B01"), bench.by_id["B01"])
    assert row["task_status"] == "PASS", row["checks"]
    assert row["delegations"] == 0
    assert row["first_config_valid"] is True and row["config_field_accuracy"] == 1.0


def test_injected_fault_is_recovered(bench, monkeypatch):
    folder = bench.run("full", "E01")
    row = analyze_run(folder, bench.by_id["E01"])
    assert row["task_status"] == "PASS", row["checks"]
    assert row["faults_injected"] == 1
    # Nhóm E không vào chỉ số config lần đầu: lỗi chèn có thể làm hỏng lần submit đầu.
    assert row["first_config_valid"] is None
    assert row["error_episodes"] == 1 and row["error_recovered"] == 1


def test_train_case_scores_sr_nps_cs_and_report(bench):
    folder = bench.run("full", "C01")
    row = analyze_run(folder, bench.by_id["C01"])
    # Chưa chấm test: workflow xong nhưng NPS/CS còn thiếu, không bị thay bằng 0.
    assert row["sr"] == 1.0 and row["nps"] is None and row["cs"] is None
    assert row["measurement_status"] == "incomplete"

    scoring.score_all(bench.root, bench.cases_doc, bench.cfg, include_pilot=False)
    metrics = load_json(folder / "test" / "test_metrics.json")
    # Model giả luôn đoán 1: đúng 3/4; F1 = (F1 lớp 1 = 0.857 + F1 lớp 2 = 0) / 2.
    assert metrics["accuracy"] == 0.75
    assert metrics["f1_macro"] == pytest.approx(0.428571, abs=1e-5)

    row = analyze_run(folder, bench.by_id["C01"])
    assert row["task_status"] == "PENDING_REVIEW"
    (folder / "review.json").write_text(json.dumps({"verdict": "PASS", "note": "Câu trả lời khớp tool_result."}))
    row = analyze_run(folder, bench.by_id["C01"])
    assert row["task_status"] == "PASS", row["checks"]
    assert row["cs"] == pytest.approx(0.5 + 0.5 * metrics["f1_macro"])

    bench.run("full", "A01")
    bench.run("full", "B03")
    bench.run("no-validate", "B03")
    path = report.write_report(bench.root, bench.root.parent / "report", bench.cases_doc, None)
    text = path.read_text(encoding="utf-8")
    for heading in ("Task success rate", "SR, NPS, CS", "Số vòng lặp", "Chi phí và độ trễ",
                    "Tool/API call accuracy", "tự phục hồi", "Ablation"):
        assert heading in text, heading
    assert "no-validate" in text
    assert (bench.root.parent / "report" / "results.csv").read_text().count("\n") == 5


def test_f1_macro_matches_definition():
    assert scoring.f1_macro([1, 1, 2, 2], [1, 1, 2, 2]) == 1.0
    assert scoring.f1_macro([1, 2], [1, 1]) == pytest.approx((2 / 3 + 0) / 2)


def test_api_fault_raises_once():
    from benchmark import variants

    FakeBackend.jobs = {}
    api = FakeBackend()
    log = []
    variants.inject_api_faults(api, lambda kind, data: log.append(data), [{"kind": "api", "method": "list_jobs"}])
    with pytest.raises(ApiError):
        api.list_jobs()
    assert api.list_jobs() == [] and len(log) == 1


def test_manual_pass_cannot_override_missing_test(bench):
    folder = bench.run("full", "C01")
    case = {**bench.by_id["C01"], "constraints": [{"metric": "f1_macro", "op": ">=", "value": 0.5}]}
    (folder / "review.json").write_text(json.dumps({"verdict": "PASS"}))
    row = analyze_run(folder, case)
    assert row["task_status"] == "PENDING"
    assert row["all_constraints_pass"] is None and row["cs"] is None


def test_empty_prediction_is_not_working_endpoint(bench):
    folder = bench.run("full", "C01")
    path = folder / "trace.jsonl"
    trace = [json.loads(line) for line in path.read_text().splitlines()]
    for record in trace:
        if record["record"] == "tool_result" and record["data"]["name"] == "predict":
            record["data"]["result"]["predictions"] = []
    path.write_text("\n".join(json.dumps(r) for r in trace) + "\n")
    row = analyze_run(folder, bench.by_id["C01"])
    assert row["task_status"] == "FAIL"
    assert row["workflow_pass"] is False and row["sr"] == 0.5


def test_missing_fault_is_invalid_fixture(bench):
    folder = bench.run("full", "A01")
    case = {**bench.by_id["A01"], "faults": [{"kind": "api", "method": "predict", "times": 1}]}
    assert analyze_run(folder, case)["task_status"] == "INVALID_FIXTURE"


def test_running_fixture_must_be_running_at_agent_read(bench):
    folder = bench.run("full", "A01")
    path = folder / "run.json"
    run = load_json(path)
    run["fixtures"] = {"running_job": {"status_before": 0, "observed_statuses": [1]}}
    path.write_text(json.dumps(run))
    assert analyze_run(folder, bench.by_id["A01"])["task_status"] == "INVALID_FIXTURE"


def test_constraint_denominator_includes_failed_and_unmeasured_jobs():
    rows = [
        {"has_constraints": True, "task_status": "PASS", "all_constraints_pass": True, "workflow_pass": True},
        {"has_constraints": True, "task_status": "FAIL", "all_constraints_pass": False, "workflow_pass": False},
        {"has_constraints": True, "task_status": "PENDING", "all_constraints_pass": None, "workflow_pass": True},
        {"has_constraints": False, "task_status": "PASS", "all_constraints_pass": None, "workflow_pass": True},
    ]
    assert report.constraint_rate(rows) == "1/3 (33.3%); chưa đo: 1"


def test_config_omissions_and_missing_job_metadata_are_wrong():
    from benchmark.analyze import _config_accuracy, _job_matches_task
    assert _config_accuracy(GOOD_CONFIG, {"target": "Type"})[:2] == (1, 7)
    assert set(_job_matches_task({}, GOOD_CONFIG)) == set(GOOD_CONFIG)


def test_cost_requires_matching_model_and_complete_accounting():
    from benchmark.analyze import cost_of
    usage = {"calls": 1, "prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
    pricing = {"provider": "test", "model": "m", "input_price_usd_per_million": 2,
               "output_price_usd_per_million": 10, "billing_mode": "uniform_input_output"}
    cost, status = cost_of(usage, pricing, "test", "m")
    assert cost == pytest.approx(0.0004) and status == "estimated"
    assert cost_of(usage, pricing, "test", "other") == (None, "model_mismatch")
    assert cost_of({**usage, "total_tokens": 140}, pricing, "test", "m") == (None, "incomplete")
    assert cost_of({**usage, "missing_usage_calls": 1}, pricing, "test", "m") == (None, "incomplete")
    assert cost_of(usage, {**pricing, "input_price_usd_per_million": -1}, "test", "m") == (None, "invalid_pricing")


@pytest.mark.parametrize("truth,prediction", [([], []), ([1], []), ([1], [float("nan")]), ([float("inf")], [1])])
def test_metrics_reject_invalid_predictions(truth, prediction):
    with pytest.raises(ValueError):
        scoring.compute_metrics("regression", truth, prediction)


def test_cached_test_cannot_be_reused_after_data_change(bench):
    folder = bench.run("full", "C01")
    scoring.score_all(bench.root, bench.cases_doc, bench.cfg, include_pilot=False)
    path = Path(bench.cfg["test_sets"]["glass"])
    path.write_text(path.read_text() + ",".join(["2"] * 9 + ["1"]) + "\n")
    with pytest.raises(ValueError, match="khác dữ liệu"):
        scoring.score_run(FakeBackend(), folder, bench.by_id["C01"], bench.cfg)


def test_active_jobs_block_next_run(monkeypatch):
    monkeypatch.setattr(runner.tools, "list_my_jobs", lambda _: {"ok": True, "jobs": [{"job_id": "busy", "status": 0}]})
    monkeypatch.setattr(runner, "_job", lambda *_: {"status": 0})
    with pytest.raises(RuntimeError, match="chưa kết thúc"):
        runner.assert_idle(object())
    assert runner.settle_jobs(object(), ["busy"], 0) == {"busy": 0}


def test_reauthentication_retries_only_401(monkeypatch):
    from benchmark.auth import install_reauthentication
    monkeypatch.setenv("AGENT_USER", "fixture-user")
    monkeypatch.setenv("AGENT_PASSWORD", "fixture-password")

    class Client:
        def __init__(self, status):
            self.calls = self.logins = 0
            self.status = status

        def _send(self, method, path, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise ApiError(self.status, "fixture")
            return {"ok": True}

        def login(self, user, password):
            self.logins += 1

    client = Client(401)
    install_reauthentication(client)
    assert client._send("GET", "/jobs") == {"ok": True}
    assert (client.calls, client.logins) == (2, 1)
    client = Client(503)
    install_reauthentication(client)
    with pytest.raises(ApiError):
        client._send("POST", "/jobs")
    assert (client.calls, client.logins) == (1, 0)


def test_group_split_keeps_conflicting_labels_together(tmp_path, monkeypatch):
    import csv
    from benchmark import prepare_data
    monkeypatch.setattr(prepare_data, "OUT_DIR", tmp_path)
    rows = [{"x": i, "y": i % 2} for i in range(30)] + [{"x": 3, "y": 0}, {"x": 3, "y": 1}]
    meta = prepare_data.export("fixture", rows, "y", stratify=True)
    before = [(tmp_path / f"fixture_{split}.csv").read_bytes() for split in ("train", "test")]
    prepare_data.export("fixture", rows, "y", stratify=True)
    assert before == [(tmp_path / f"fixture_{split}.csv").read_bytes() for split in ("train", "test")]
    groups = []
    for split in ("train", "test"):
        with (tmp_path / f"fixture_{split}.csv").open() as f:
            data = list(csv.DictReader(f))
        groups.append({float(r["x"]) for r in data})
        assert {float(r["y"]) for r in data} == {0, 1}
    assert not groups[0] & groups[1]
    assert meta["n_train"] + meta["n_test"] == len(rows)
    assert meta["n_conflicting_target_groups"] == 1


def test_protocol_counts_immutability_and_completion(tmp_path, monkeypatch):
    from benchmark import protocol
    from benchmark.common import BENCH_DIR
    cfg = load_json(BENCH_DIR / "config.example.json")
    cases = load_json(CASES_PATH)
    monkeypatch.setattr(protocol, "check_data", lambda *_: {})
    monkeypatch.setattr(protocol, "check_ts_data", lambda *_: {})
    monkeypatch.setattr(protocol, "source_hashes", lambda: {"agent.py": "first"})
    monkeypatch.setattr(protocol, "provider_settings", lambda _cfg: {"name": "test", "model": "m"})
    assert len(protocol.snapshot(cfg, cases, None, "pilot")["plan"]) == 47
    # (33 ca v4 + 6 ca T + 8 ca S) x 5 lần + 13 ca ablation x 5 biến thể x 3 lần.
    assert len(protocol.snapshot(cfg, cases, None, "official")["plan"]) == 430
    cfg["ablation"]["enabled"] = False
    assert len(protocol.plan(cfg, cases)) == 235
    cfg["ablation"]["enabled"] = True
    payload = protocol.snapshot(cfg, cases, None, "official")
    locked = protocol.freeze(tmp_path, payload)
    assert protocol.freeze(tmp_path, payload) == locked
    with pytest.raises(ValueError, match="Chưa đủ"):
        protocol.require_complete(tmp_path, locked)
    monkeypatch.setattr(protocol, "source_hashes", lambda: {"agent.py": "changed"})
    with pytest.raises(ValueError, match="đã thay đổi"):
        protocol.verify_current(tmp_path, cfg, cases, None, "official")
    altered = json.loads((tmp_path / "protocol.json").read_text())
    altered["payload"]["phase"] = "pilot"
    (tmp_path / "protocol.json").write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="hợp lệ"):
        protocol.read_lock(tmp_path)


def test_retry_invalid_preserves_original_and_does_not_retry_pass(bench, monkeypatch):
    folder = bench.run("full", "A01")
    path = folder / "run.json"
    run = load_json(path)
    run["fixtures"] = {"running_job": {"status_before": 1}}
    path.write_text(json.dumps(run))
    bench.cfg["_retry_invalid"] = True
    assert bench.run("full", "A01") == folder
    archived = list(folder.parent.glob("A01_r01.invalid-*/run.json"))
    assert len(archived) == 1
    assert load_json(archived[0])["fixtures"] == run["fixtures"]
    assert bench.run("full", "A01") is None
    assert len(report.build_rows(bench.root, bench.cases_doc, None)) == 1


def test_scoring_gate_rejects_invalid_fixture_before_test_is_seen(bench):
    from benchmark.protocol import require_complete
    folder = bench.run("full", "A01")
    path = folder / "run.json"
    run = load_json(path)
    run["fixtures"] = {"running_job": {"status_before": 1}}
    path.write_text(json.dumps(run))
    locked = {"protocol_id": None, "payload": {"cases": bench.cases_doc, "plan": [["full", "A01", 1]]}}
    with pytest.raises(ValueError, match="INVALID_FIXTURE"):
        require_complete(bench.root, locked)


def test_alternative_tool_requirement_has_own_denominator(bench):
    folder = bench.run("full", "A01")
    case = {**bench.by_id["A01"], "expect": {"tool_args_any": [{"tool": "list_my_datasets", "args": {}}]}}
    row = analyze_run(folder, case)
    assert row["required_tools_total"] == row["required_tools_hit"] == 1


def test_train_start_requires_actual_job_to_match_task(bench):
    folder = bench.run("full", "C01")
    path = folder / "run.json"
    run = load_json(path)
    next(iter(run["job_snapshots"].values()))["data"]["id"] = OTHER
    path.write_text(json.dumps(run))
    case = {**bench.by_id["C01"], "flow": "train_start"}
    row = analyze_run(folder, case)
    assert row["task_status"] == "FAIL" and "dataset_id" in row["wrong_task"]


def test_string_class_labels_are_valid_predictions(bench, monkeypatch):
    # Backend thật trả nhãn phân loại dạng chuỗi vì LabelEncoder fit trên astype(str).
    monkeypatch.setattr(FakeBackend, "predict", lambda self, job_id, rows, timeout=120.0: {
        "model_name": "RF", "predictions": ["1" for _ in rows]})
    folder = bench.run("full", "C01")
    row = analyze_run(folder, bench.by_id["C01"])
    assert row["task_status"] == "PENDING_REVIEW", row["checks"]
    assert row["sr"] == 1.0 and row["workflow_pass"] is True
    scoring.score_all(bench.root, bench.cases_doc, bench.cfg, include_pilot=False)
    assert load_json(folder / "test" / "test_metrics.json")["accuracy"] == 0.75


def test_agent_that_never_acts_fails_instead_of_invalid_fixture(bench):
    row = analyze_run(bench.run("full", "E02"), bench.by_id["E02"])
    assert row["task_status"] == "FAIL" and row["faults_injected"] == 0
    # D06: job vẫn chạy nhưng agent không đọc trạng thái.
    folder = bench.run("full", "A01")
    path = folder / "run.json"
    run = load_json(path)
    run["fixtures"] = {"running_job": {"status_before": 0, "observed_statuses": []}}
    path.write_text(json.dumps(run))
    assert analyze_run(folder, bench.by_id["D06"])["task_status"] == "FAIL"


def test_answer_terms_match_whole_tokens():
    from benchmark.analyze import _mentions
    assert _mentions("RI, Na, Mg, Al, Si, K, Ca, Ba, Fe và Type", "K")
    assert not _mentions("Kết quả có 10 cột", "K")
    assert not _mentions("balanced_accuracy", "accuracy")
    assert _mentions("- Accuracy: 0.8", "accuracy")
    # Tên cột có chữ hoa so đúng hoa thường; cách viết metric phổ biến vẫn được nhận.
    assert not _mentions("Dataset có ba cột số", "Ba")
    for text in ("F1-macro", "f1\\_macro", "f1 macro", "F1 (macro)"):
        assert _mentions(text, "f1_macro"), text
    assert _mentions("R² = 0.91", "r2") and _mentions("balanced accuracy", "balanced_accuracy")
    assert not _mentions("balanced accuracy, f1 macro", "accuracy")


def test_metric_name_variants():
    """Cách agent viết tên metric cho người đọc vẫn được nhận (D01: "Precision (macro)" từng bị chấm trượt)."""
    from benchmark.analyze import _mentions
    for text in ("- Precision (macro): **0.7823**", "| **Precision** (macro) | 0.78 |", "precision_macro / precision_weighted",
                 "Precision: 0.7823 (macro)", "Các chỉ số macro: precision 0.78, recall 0.73, F1 0.74",
                 "Macro precision = 0.78", "macro-averaged precision 0.78", "Precision-score (macro avg)"):
        assert _mentions(text, "precision_macro"), text
    for text in ("F1-score (macro avg): 0.74", "Macro-F1 = 0.74", "F1‑macro", "macro F1-score 0.74", "`f1_macro`"):
        assert _mentions(text, "f1_macro"), text
    assert _mentions("Mean Absolute Error (MAE): 3.5", "mae") and _mentions("Mean absolute error 3.5", "mae")
    assert _mentions("R-squared 0.91", "r2") and _mentions("R^2 = 0.91", "r2")
    # Kiểu trung bình khác, metric khác hay chữ macro thuộc metric khác thì không tính.
    for text in ("F1 (weighted): 0.77", "F1: 0.74", "precision macro 0.78, f1_weighted 0.77"):
        assert not _mentions(text, "f1_macro"), text
    assert not _mentions("f1 macro precision weighted", "precision_macro")
    assert not _mentions("Mean absolute percentage error 0.1", "mae") and not _mentions("RMSE 4.2", "mse")


def test_harness_read_failure_is_invalid_not_agent_failure(bench):
    folder = bench.run("full", "C01")
    path = folder / "run.json"
    run = load_json(path)
    job_id = run["new_jobs"][0]
    for broken in ({**run, "new_jobs": None},
                   {**run, "job_snapshots": {job_id: {"ok": False, "status_code": 503, "error": "down"}}}):
        path.write_text(json.dumps(broken))
        row = analyze_run(folder, bench.by_id["C01"])
        assert row["task_status"] == "INVALID_FIXTURE", row["failure_reason"]
        # Không có điểm, để không kéo trung bình SR/NPS/CS và tỷ lệ job thành công.
        assert row["sr"] is None and row["cs"] is None and row["job_success"] is None


def test_fixture_jobs_are_reset_before_each_case(bench, monkeypatch):
    # Lượt trước bật nhầm INACTIVE_JOB và tắt GLASS_JOB: bộ chạy phải trả về đúng trạng thái trước khi đo.
    for job_id, active in (("job-inactive", 1), ("job-glass", 0)):
        FakeBackend.jobs[job_id] = {"_id": job_id, "user": {"id": "user-1"}, "status": 1, "activate": active,
                                    "config": {"list_feature": FEATURES, "target": "Type"}, "data": {"id": GLASS}}
    bench.cfg["placeholders"].update({"INACTIVE_JOB": "job-inactive", "GLASS_JOB": "job-glass"})
    monkeypatch.setitem(SCRIPTS, ("full", "D04"), [reply("Model chưa được kích hoạt nên không dự đoán được.")])
    monkeypatch.setitem(SCRIPTS, ("full", "D01"), [reply("Không đọc được.")])
    d04 = load_json(bench.run("full", "D04") / "run.json")["fixtures"]["inactive_job"]
    d01 = load_json(bench.run("full", "D01") / "run.json")["fixtures"]["glass_job"]
    assert d04["activate_before"] == 0 and d04["activate_after"] == 0
    assert d01["activate_before"] == 1


def test_superseded_config_does_not_count(bench, monkeypatch):
    monkeypatch.setitem(SCRIPTS, ("full", "B01"), [
        reply(tool="ask_model_agent", task="Tạo config", dataset_id=GLASS),
        reply(tool="submit_config", **GOOD_CONFIG),
        # Config thứ hai hợp lệ nhưng sai metric thay thế config đúng.
        reply(tool="submit_config", **{**GOOD_CONFIG, "metric_sort": "accuracy"}),
        reply("Đã chốt config"),
        reply("Đã tạo cấu hình."),
    ])
    row = analyze_run(bench.run("full", "B01"), bench.by_id["B01"])
    assert row["task_status"] == "FAIL" and "valid_config_matches_task" in row["failure_reason"]
    assert row["first_config_valid"] is True and row["config_field_accuracy"] == 1.0


def test_extra_job_does_not_lower_sr_tier(bench):
    folder = bench.run("full", "C01")
    scoring.score_all(bench.root, bench.cases_doc, bench.cfg, include_pilot=False)
    path = folder / "run.json"
    run = load_json(path)
    run["new_jobs"] = run["new_jobs"] + ["job-extra"]
    run["job_snapshots"]["job-extra"] = {"status": 1, "activate": 0}
    path.write_text(json.dumps(run))
    case = {**bench.by_id["C01"], "constraints": [{"metric": "accuracy", "op": ">=", "value": 0.5}]}
    row = analyze_run(folder, case)
    assert row["task_status"] == "FAIL" and row["all_constraints_pass"] is False
    assert row["sr"] == 1.0


def test_subagent_llm_fault_skips_manager_calls():
    from agent.events import EventBus
    from benchmark import variants
    session = SimpleNamespace(events=EventBus(), llm=SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: reply("ok")))))
    log = []
    variants.instrument_llm(session, lambda kind, data: log.append(kind), [{"kind": "llm", "target": "subagent", "times": 1}])
    create = session.llm.chat.completions.create
    create()  # Manager: không chèn dù là lời gọi thứ 2
    create()
    session.events.emit("agent_start", agent="model-agent")
    with pytest.raises(RuntimeError, match="Injected"):
        create()
    create()  # lỗi chỉ chèn một lần
    session.events.emit("agent_done", agent="model-agent", ok=True)
    assert log.count("fault") == 1


def test_no_verify_does_not_claim_user_set_no_constraints():
    from contextlib import ExitStack
    from benchmark import variants
    FakeBackend.jobs = {}
    session = ChatSession(api=FakeBackend(), access_token="test-token", verbose=False)
    with ExitStack() as stack:
        variants.apply_variant(session, "no-verify", stack)
        session.watcher._on_finish({"job_id": "job-1", "status": 1, "best_model": "RF",
                                    "metric_sort": "f1_macro", "best_score": 0.7})
    assert "không đặt ràng buộc" not in session.pending_events[-1]
    assert "kiểm định ràng buộc bị tắt" in session.pending_events[-1]


def test_answer_checks_use_last_turn(bench):
    folder = bench.run("full", "A01")
    path = folder / "run.json"
    run = load_json(path)
    run["turns"] = [{"prompt": "1", "answer": "f1_macro 0.7, recall_macro 0.6"}, {"prompt": "2", "answer": "Không rõ"}]
    path.write_text(json.dumps(run))
    checks = {c["check"]: c["passed"] for c in analyze_run(folder, bench.by_id["D05"])["checks"]}
    assert checks["answer_contains_all"] is False


def test_successful_predict_must_be_on_asked_job(bench):
    folder = bench.run("full", "C01")  # dự đoán thành công trên job mới, không phải GLASS_JOB
    checks = {c["check"]: c["passed"] for c in analyze_run(folder, bench.by_id["D02"])["checks"]}
    assert checks["predict_ok"] is False and checks["prediction_output"] is False


def test_report_rejects_copied_run_folder(bench):
    import shutil
    folder = bench.run("full", "A01")
    shutil.copytree(folder, folder.with_name("A01_r01.bak"))
    with pytest.raises(ValueError, match="bản sao"):
        report.build_rows(bench.root, bench.cases_doc, None)


def test_lock_ignores_dot_cache_directories():
    from benchmark.protocol import source_hashes
    assert not any("/." in path for path in source_hashes())


def test_schema_read_through_handoff_counts_without_data_agent(bench, monkeypatch):
    # Không có Data Agent: Model Agent nhận schema do Handoff đọc bằng code, không có tool call của LLM.
    answer = "Dataset có 10 cột: RI, Na, Mg, Al, Si, K, Ca, Ba, Fe, Type; Type là target phân loại."
    monkeypatch.setitem(SCRIPTS, ("no-data-agent", "A02"), [
        reply(tool="ask_model_agent", task="Phân tích cột", dataset_id=GLASS), reply(answer), reply(answer)])
    row = analyze_run(bench.run("no-data-agent", "A02"), bench.by_id["A02"])
    assert row["task_status"] == "PENDING_REVIEW", row["checks"]
    assert row["required_tools_hit"] == row["required_tools_total"] == 1


def test_prediction_must_use_rows_the_user_gave(bench):
    folder = bench.run("full", "C01")
    path = folder / "trace.jsonl"
    trace = [json.loads(line) for line in path.read_text().splitlines()]
    for record in trace:
        if record["record"] == "tool_result" and record["data"]["name"] == "predict":
            record["data"]["arguments"]["rows"] = [{f: 0.0 for f in FEATURES}]
    path.write_text("\n".join(json.dumps(r) for r in trace) + "\n")
    row = analyze_run(folder, bench.by_id["C01"])
    assert row["task_status"] == "FAIL" and "activated_and_predicted" in row["failure_reason"]


def test_running_fixture_seen_running_first_is_valid(bench):
    folder = bench.run("full", "A01")
    path = folder / "run.json"
    run = load_json(path)
    run["fixtures"] = {"running_job": {"status_before": 0, "observed_statuses": [0, 1]}}
    path.write_text(json.dumps(run))
    assert analyze_run(folder, bench.by_id["D06"])["task_status"] != "INVALID_FIXTURE"


def test_interrupted_run_is_kept_as_fail_and_not_rerun(bench, monkeypatch):
    def interrupt(_messages):
        raise KeyboardInterrupt
    monkeypatch.setitem(SCRIPTS, ("full", "A01"), [interrupt])
    with pytest.raises(KeyboardInterrupt):
        bench.run("full", "A01")
    folder = bench.root / "full" / "A01_r01"
    row = analyze_run(folder, bench.by_id["A01"])
    assert row["task_status"] == "FAIL" and "not_interrupted" in row["failure_reason"]
    assert row["token_status"] == "incomplete"
    from benchmark.protocol import require_complete
    locked = {"protocol_id": None, "payload": {"cases": bench.cases_doc, "plan": [["full", "A01", 1]]}}
    with pytest.raises(ValueError, match="chưa xác nhận job"):
        require_complete(bench.root, locked)
    bench.cfg["_retry_invalid"] = True
    assert bench.run("full", "A01") is None  # giữ nguyên, chỉ xác nhận job đã dừng
    assert load_json(folder / "run.json")["settle_verified"] is True
    require_complete(bench.root, locked)
    assert analyze_run(folder, bench.by_id["A01"])["task_status"] == "FAIL"


def test_truncated_last_trace_line_is_ignored(tmp_path):
    from benchmark.common import read_trace
    path = tmp_path / "trace.jsonl"
    path.write_text('{"record": "user", "at": 1, "data": "x"}\n{"record": "ev')
    assert len(read_trace(path)) == 1
    # Bị cắt giữa một ký tự UTF-8 nhiều byte.
    path.write_bytes(b'{"record": "user", "at": 1, "data": "x"}\n{"data": "K' + "ế".encode()[:2])
    assert len(read_trace(path)) == 1


def test_original_config_must_exist_before_the_revision_turn(bench, monkeypatch):
    revised = {**GOOD_CONFIG, "list_feature": FEATURES[:7], "metric_sort": "accuracy"}
    monkeypatch.setitem(SCRIPTS, ("full", "F02"), [
        reply("Bạn muốn làm gì?"),
        reply(tool="ask_model_agent", task="Tạo config", dataset_id=GLASS),
        reply(tool="submit_config", **GOOD_CONFIG), reply(tool="submit_config", **revised),
        reply("Đã chốt"), reply("Đã tạo cấu hình.")])
    row = analyze_run(bench.run("full", "F02"), bench.by_id["F02"])
    assert row["task_status"] == "FAIL" and "replaced_original_config" in row["failure_reason"]


def test_interrupted_run_reports_no_partial_cost(bench, monkeypatch):
    def interrupt(_messages):
        raise KeyboardInterrupt
    turn1 = [reply(tool="ask_model_agent", task="Tạo config", dataset_id=GLASS),
             reply(tool="submit_config", **GOOD_CONFIG), reply("Config hợp lệ"), reply("Đã tạo cấu hình.")]
    monkeypatch.setitem(SCRIPTS, ("full", "F02"), turn1 + [interrupt])
    with pytest.raises(KeyboardInterrupt):
        bench.run("full", "F02")
    pricing = {"provider": "test", "model": "test-model", "input_price_usd_per_million": 1,
               "output_price_usd_per_million": 1, "billing_mode": "uniform_input_output"}
    row = analyze_run(bench.root / "full" / "F02_r01", bench.by_id["F02"], pricing)
    assert row["total_tokens"] == 480 and row["llm_cost_usd"] is None and row["cost_status"] == "incomplete"


def test_revision_requires_an_original_config_to_replace(bench, monkeypatch):
    revised = {**GOOD_CONFIG, "list_feature": FEATURES[:7], "metric_sort": "accuracy"}
    monkeypatch.setitem(SCRIPTS, ("full", "F02"), [
        reply("Bạn muốn feature nào?"),
        reply(tool="ask_model_agent", task="Tạo config", dataset_id=GLASS),
        reply(tool="submit_config", **revised), reply("Đã chốt"), reply("Đã tạo cấu hình.")])
    row = analyze_run(bench.run("full", "F02"), bench.by_id["F02"])
    assert row["task_status"] == "FAIL" and "replaced_original_config" in row["failure_reason"]


def test_missing_usage_still_counts_call_but_marks_tokens_incomplete(bench, monkeypatch):
    no_usage = reply(tool="list_my_datasets")
    no_usage.usage = None
    monkeypatch.setitem(SCRIPTS, ("full", "A01"), [
        reply(tool="ask_data_agent", task="Liệt kê dataset"), no_usage, reply("Có 2 dataset"),
        reply(f"Bạn có: {GLASS} (glass_train), {OTHER} (other).")])
    row = analyze_run(bench.run("full", "A01"), bench.by_id["A01"])
    assert row["llm_calls"] == 4 and row["token_status"] == "incomplete"


def test_dataset_names_are_required_in_listing(bench, monkeypatch):
    monkeypatch.setitem(SCRIPTS, ("full", "A01"), [
        reply(tool="ask_data_agent", task="Liệt kê dataset"), reply(tool="list_my_datasets"),
        reply("Có 2 dataset"), reply(f"ID: {GLASS}, {OTHER}.")])
    row = analyze_run(bench.run("full", "A01"), bench.by_id["A01"])
    assert row["task_status"] == "FAIL" and "answer_lists_dataset_names" in row["failure_reason"]


def test_revised_request_must_replace_old_config(bench, monkeypatch):
    revised = {**GOOD_CONFIG, "list_feature": FEATURES[:7], "metric_sort": "accuracy"}
    turn1 = [reply(tool="ask_model_agent", task="Tạo config", dataset_id=GLASS),
             reply(tool="submit_config", **GOOD_CONFIG), reply("Config hợp lệ"), reply("Đã tạo cấu hình.")]
    monkeypatch.setitem(SCRIPTS, ("full", "F02"), turn1 + [
        reply(tool="ask_model_agent", task="Sửa config", dataset_id=GLASS),
        reply(tool="submit_config", **revised), reply("Đã sửa"), reply("Đã cập nhật cấu hình.")])
    assert analyze_run(bench.run("full", "F02"), bench.by_id["F02"])["task_status"] == "PASS"
    # Agent không chốt lại config: config cũ (f1_macro, 9 feature) không khớp yêu cầu mới.
    FakeBackend.jobs = {}
    monkeypatch.setitem(SCRIPTS, ("single-agent", "F02"), [
        reply(tool="submit_config", **GOOD_CONFIG), reply("Đã tạo."), reply("Đã cập nhật.")])
    row = analyze_run(bench.run("single-agent", "F02"), bench.by_id["F02"])
    assert row["task_status"] == "FAIL" and "valid_config_matches_task" in row["failure_reason"]


def test_single_agent_gets_the_full_step_budget_and_restores_it():
    from contextlib import ExitStack
    from agent import chat as chat_module
    from benchmark import variants
    FakeBackend.jobs = {}
    session = ChatSession(api=FakeBackend(), access_token="test-token", verbose=False)
    before = chat_module.MAX_STEPS
    with ExitStack() as stack:
        variants.apply_variant(session, "single-agent", stack)
        # Một agent làm việc của Manager và 4 sub-agent nghiệp vụ (Data, Model, Operation, SQL).
        assert chat_module.MAX_STEPS == 12 + 4 * 8
    assert chat_module.MAX_STEPS == before


def test_plan_interleaves_full_and_ablation_deterministically():
    from benchmark import protocol
    from benchmark.common import BENCH_DIR
    cfg = load_json(BENCH_DIR / "config.example.json")
    cases = load_json(CASES_PATH)
    plan = protocol.plan(cfg, cases)
    assert plan == protocol.plan(cfg, cases)
    first_block = [x for x in plan if x[2] == 1]
    assert plan[:len(first_block)] == first_block  # theo khối lần lặp
    assert {x[0] for x in first_block[:20]} != {"full"}  # full và ablation xen kẽ


def test_provider_settings_never_include_api_key(monkeypatch):
    from agent import providers
    from benchmark import protocol
    monkeypatch.setattr(providers, "resolve", lambda *_: SimpleNamespace(
        name="fpt", kind="openai", api_key="secret", model="m", base_url="https://llm", endpoint=None, api_version=None))
    settings = protocol.provider_settings({"provider": "fpt", "model": "m"})
    assert settings["base_url"] == "https://llm" and "api_key" not in settings


# ------------------------------------------------------------- nhóm T (time series)

def _hours(start: str, n: int) -> list[str]:
    from datetime import datetime, timedelta
    first = datetime.fromisoformat(start)
    return [(first + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(n)]


@pytest.fixture
def ts_data(tmp_path, monkeypatch):
    """Dữ liệu nhóm T thu nhỏ (cùng định dạng manifest_ts) trong thư mục tạm."""
    import hashlib
    from benchmark import prepare_ts

    directory = tmp_path / "timeseries"
    directory.mkdir()
    datasets, hashes = {}, {}
    for name, target in (("electricity", "load_kwh"), ("weather", "co2_ppm")):
        stamps = _hours("2014-09-01 00:00:00", 200 + 96)
        values = [10.0 + (i % 24) for i in range(len(stamps))]
        files = {}
        for split, part in (("train", slice(0, 200)), ("test", slice(200, None))):
            filename = f"{name}_{split}.csv"
            text = f"date,{target}\n" + "".join(f"{t},{v}\n" for t, v in zip(stamps[part], values[part]))
            (directory / filename).write_text(text, encoding="utf-8")
            hashes[filename] = hashlib.sha256(text.encode()).hexdigest()
            files[split] = filename
        datasets[name] = {"time_column": "date", "target": target, "n_train": 200, "n_test": 96, "files": files}
    manifest = directory / "manifest_ts.json"
    manifest.write_text(json.dumps({"split_version": prepare_ts.SPLIT_VERSION, "datasets": datasets, "sha256": hashes}))
    monkeypatch.setattr(prepare_ts, "TS_DIR", directory)
    monkeypatch.setattr(prepare_ts, "MANIFEST", manifest)
    cfg = {"test_sets": {name: str(directory / meta["files"]["test"]) for name, meta in datasets.items()}}
    return SimpleNamespace(dir=directory, cfg=cfg)


def test_time_series_metrics_follow_automl_agent():
    import math
    metrics = scoring.compute_metrics("time_series", [1.0, 3.0], [1.0, 1.0])
    assert metrics["rmse"] == pytest.approx(math.sqrt(2))
    assert metrics["mae"] == pytest.approx(1.0)
    rmsle = math.sqrt((math.log(2) - math.log(4)) ** 2 / 2)
    assert metrics["rmsle"] == pytest.approx(rmsle)
    assert metrics["nps"] == pytest.approx(1 / (1 + rmsle))
    assert metrics["mape"] == pytest.approx(1 / 3)
    # Dự báo <= -1 cho chuỗi dương: lỗi của mô hình - NPS = 0 (không loại lượt khỏi trung bình).
    bad = scoring.compute_metrics("time_series", [1.0, 3.0], [1.0, -2.0])
    assert bad["nps"] == 0.0 and bad["rmsle"] is None and bad["rmsle_undefined"] is True


def test_naive_baselines_use_only_the_training_history():
    history = [float(i % 24) for i in range(24 * 7)] + [100.0] * 24     # ngày cuối bất thường
    truth = [float(i % 24) for i in range(96)]
    result = scoring.naive_baselines(history, truth)
    assert result["naive_last_week_rmse"] == pytest.approx(scoring._rmse(truth, history[-168:][:96]))
    assert result["naive_last_day_rmse"] > result["naive_last_week_rmse"]
    assert set(result) == {"naive_last_day_rmse", "naive_last_day_rmsle", "naive_last_week_rmse", "naive_last_week_rmsle"}


def test_timestamp_rows_match_by_instant():
    from benchmark.analyze import _same_rows
    expected = [{"date": "2014-09-27 00:00:00"}, {"date": "2014-09-27 01:00:00"}]
    assert _same_rows([{"date": "2014-09-27T00:00:00"}, {"date": "2014-09-27 01:00:00"}], expected)
    # Backend đọc mốc bằng pandas.to_datetime: dạng gạch chéo cùng thời điểm cũng là đúng mẫu.
    assert _same_rows([{"date": "2014/09/27 00:00:00"}, {"date": "2014/09/27 01:00"}], expected)
    assert not _same_rows([{"date": "2014-09-27 00:00:00"}, {"date": "2014-09-27 02:00:00"}], expected)
    assert not _same_rows([{"date": "2014-09-27 00:00:00"}], expected)


def test_time_series_test_rows_keep_the_timestamp(tmp_path):
    path = tmp_path / "t.csv"
    path.write_text("date,load_kwh\n2014-09-27 00:00:00,84.5\n")
    x, y = scoring._read_test(path, "load_kwh", "date")
    assert x == [{"date": "2014-09-27 00:00:00"}] and y == [84.5]


def test_time_series_data_check_catches_tampering(ts_data):
    from benchmark import protocol
    assert protocol.check_ts_data(ts_data.cfg)["split_version"] == "time-holdout-v1"
    with pytest.raises(ValueError, match="không trỏ"):
        protocol.check_ts_data({"test_sets": {**ts_data.cfg["test_sets"], "weather": ts_data.cfg["test_sets"]["electricity"]}})
    path = ts_data.dir / "weather_test.csv"
    path.write_text(path.read_text().replace("10.0", "11.0", 1))
    with pytest.raises(ValueError, match="Hash"):
        protocol.check_ts_data(ts_data.cfg)


def test_time_series_case_is_scored_on_the_96_test_steps(ts_data, tmp_path, monkeypatch):
    case = {c["id"]: c for c in load_json(CASES_PATH)["cases"]}["T01"]
    job_id = "job-ts01"
    job = {
        "_id": job_id, "user": {"id": "user-1"}, "status": 1, "activate": 1, "data": {"id": "e" * 24},
        "config": {"problem_type": "time_series", "target": "load_kwh", "list_feature": ["date"], "metric_sort": "rmse",
                   "search_algorithm": "random_search", "timeout": 300},
    }
    FakeBackend.jobs = {job_id: job}
    seen = []

    def predict(self, job_id, rows, timeout=120.0):
        seen.append([r["date"] for r in rows])
        return {"model_name": "RF", "predictions": [20.0 for _ in rows]}

    monkeypatch.setattr(FakeBackend, "predict", predict)
    folder = tmp_path / "full" / "T01_r01"
    folder.mkdir(parents=True)
    run = {"case_id": "T01", "group": "T", "variant": "full", "repeat": 1, "phase": "official", "protocol_id": "p",
           "turns": [], "fixtures": {}, "errors": [], "placeholders": {"ELEC_ID": "e" * 24},
           "new_jobs": [job_id], "handoff": {"jobs": {job_id: "cfg"}}, "job_snapshots": {job_id: job}}
    (folder / "run.json").write_text(json.dumps(run))
    assert scoring.score_run(FakeBackend(), folder, case, ts_data.cfg) == "đã chấm"
    # Đúng 96 mốc liền sau train, theo lô <= 50, mốc giữ nguyên dạng chuỗi.
    assert [len(b) for b in seen] == [50, 46] and seen[0][0] == "2014-09-09 08:00:00"
    metrics = load_json(folder / "test" / "test_metrics.json")
    truth = [10.0 + (i % 24) for i in range(200, 296)]
    assert metrics["rmse"] == pytest.approx(scoring._rmse(truth, [20.0] * 96))
    assert metrics["nps"] == pytest.approx(1 / (1 + metrics["rmsle"]))
    assert metrics["naive_last_day_rmse"] == pytest.approx(0.0)      # chuỗi giả lặp đúng chu kỳ 24 giờ
    row = analyze_run(folder, case)
    assert row["rmse"] == metrics["rmse"] and row["nps"] == metrics["nps"]
    text = report.render([row], load_json(CASES_PATH), None)
    assert "## 3b. Nhóm T" in text and "T01" in text


def test_threshold_rule_uses_only_training_windows():
    from benchmark import prepare_ts
    # Chuỗi lặp đúng chu kỳ tuần: baseline tuần trước khớp tuyệt đối trên mọi cửa sổ.
    weekly = [float(i % 168) for i in range(168 * 8)]
    assert prepare_ts.calibrate_threshold(weekly)["rmse_threshold"] == 0.0
    # Ngưỡng ca T02/T04 trùng với quy tắc ghi trong cases.json.
    cases = {c["id"]: c for c in load_json(CASES_PATH)["cases"]}
    assert cases["T02"]["constraints"][0]["value"] == 9.0 and cases["T04"]["constraints"][0]["value"] == 16.4
    assert "96 giờ" in cases["T02"]["turns"][0] and "96 giờ" in cases["T04"]["turns"][0]
