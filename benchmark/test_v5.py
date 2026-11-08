"""
Kiểm tra phần thêm ở protocol v5 (không LLM thật, không backend thật):

- Người dùng mô phỏng bấm thẻ xác nhận (consent.py): đồng ý đúng điều prompt yêu cầu, từ chối và ghi lỗi
  khi agent đề nghị việc người dùng không yêu cầu; lượt "tiếp tục" sau khi bật model.
- Nhóm S: nhập dataset từ database (kiểm số dòng/cột/tên), dọn dataset sau ca, bảng nguồn không đổi khi
  agent gửi câu ghi, số liệu trong câu trả lời.
- Metric/thống kê thuần Python, chế độ smoke, đối chiếu bài báo, báo cáo đủ mục mới.

    src/backend/.venv/bin/python -m pytest benchmark/test_v5.py
"""

import csv
from types import SimpleNamespace
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_REPO), str(_REPO / "src" / "backend")]

import pytest  # noqa: E402

from agent.api_client import ApiError  # noqa: E402
from benchmark import consent, jobinfo, metrics as M, report, scoring, stats as S  # noqa: E402
from benchmark.analyze import analyze_run, integers_in, is_write_sql  # noqa: E402
from benchmark.common import BENCH_DIR, CASES_PATH, load_json  # noqa: E402
from benchmark.test_bench import FEATURES, GLASS, GOOD_CONFIG, SCRIPTS, FakeBackend, found, reply  # noqa: E402
from benchmark.test_bench import bench  # noqa: E402,F401 - fixture dùng chung

PG, MYSQL = "conn-pg", "conn-mysql"
CRAB_COLUMNS = ["length", "diameter", "height", "weight", "shucked_weight", "viscera_weight", "shell_weight",
                "sex_f", "sex_i", "sex_m", "age"]


class FakeDatabaseBackend(FakeBackend):
    """Backend giả có kết nối database: import tạo dataset thật trong danh sách, câu ghi bị chặn như adapter."""

    datasets: dict = {}
    tables = {"crab_train": (3114, CRAB_COLUMNS), "glass_train": (171, FEATURES + ["Type"])}

    def list_datasets(self):
        return [{"_id": GLASS, "dataName": "glass_train"}] + [{"_id": k, "dataName": v["name"]} for k, v in self.datasets.items()]

    def get_dataset_info(self, dataset_id):
        return {"_id": dataset_id, "dataName": (self.datasets.get(dataset_id) or {}).get("name", "glass_train")}

    def get_dataset_preview(self, dataset_id, num_rows=50):
        if dataset_id in self.datasets:
            info = self.datasets[dataset_id]
            return {"rows": info["rows"], "records": [{c: 1.0 for c in info["columns"]}]}
        return super().get_dataset_preview(dataset_id, num_rows)

    def get_dataset_features(self, dataset_id, problem_type):
        if dataset_id in self.datasets:
            return {c: True for c in self.datasets[dataset_id]["columns"]}
        return super().get_dataset_features(dataset_id, problem_type)

    def list_database_connections(self):
        return [{"id": PG, "name": "pg", "db_type": "postgres"}, {"id": MYSQL, "name": "mysql", "db_type": "mysql"}]

    def list_database_tables(self, connection_id):
        return {"tables": [{"name": t, "kind": "table"} for t in self.tables]}

    def describe_database_table(self, connection_id, table, sample_rows=5):
        if table not in self.tables:
            raise ApiError(404, "TABLE_NOT_FOUND")
        return {"table": table, "columns": [{"name": c, "type": "double"} for c in self.tables[table][1]], "rows": []}

    def preview_database_query(self, connection_id, query):
        sql = query.get("sql", "")
        if is_write_sql(sql):
            raise ApiError(400, "UNSAFE_QUERY: chỉ cho phép SELECT")
        if "COUNT(*)" in sql:
            return {"preview_id": "pv-count", "columns": ["n"], "rows": [{"n": 171}], "row_count": 1}
        table = next(t for t in self.tables if t in sql)
        rows, columns = self.tables[table]
        return {"preview_id": f"pv-{table}", "columns": columns, "rows": [{c: 1 for c in columns}], "row_count": min(rows, 20),
                "truncated": rows > 20, "query": query}

    def import_database_query(self, connection_id, preview_id, data_name, allow_truncated=False, description=None):
        table = preview_id.removeprefix("pv-")
        rows, columns = self.tables[table]
        dataset_id = f"bbbbbbbbbbbbbbbbbbbbbb{len(self.datasets) + 1:02d}"
        self.datasets[dataset_id] = {"name": data_name, "rows": rows, "columns": columns}
        return {"dataset_id": dataset_id, "data_name": data_name, "row_count": rows, "columns": columns, "truncated": False}

    def _request(self, method, path, **kwargs):
        if method == "DELETE" and path.startswith("/datasets/"):
            self.datasets.pop(path.rsplit("/", 1)[-1], None)
            return None
        raise NotImplementedError(path)


@pytest.fixture
def sbench(bench, monkeypatch):
    from benchmark import runner
    FakeDatabaseBackend.datasets = {}
    monkeypatch.setattr(runner, "HAutoMLClient", FakeDatabaseBackend)
    original = runner.ChatSession

    def make_session(**kwargs):
        session = original(**kwargs)
        session.api = FakeDatabaseBackend()
        session.watcher._api = session.api
        return session

    monkeypatch.setattr(runner, "ChatSession", make_session)
    bench.cfg["placeholders"].update({"PG_CONN_ID": PG, "MYSQL_CONN_ID": MYSQL})
    return bench


# ----------------------------------------------------------------- người dùng mô phỏng

def test_train_case_confirms_cards_and_needs_one_continuation(bench):
    folder = bench.run("full", "C01")
    run = load_json(folder / "run.json")
    assert [(d["kind"], d["decision"], d["result"]["ok"]) for d in run["consent"]] == [
        ("train", "confirm_auto", True), ("activate", "confirm", True)]
    # Không có R (kịch bản không gọi Prompt Agent) nên thẻ train không có lựa chọn tự kích hoạt: bấm Xác nhận thường.
    assert run["consent"][0]["auto_activate_offered"] is False and run["consent"][0]["auto_activate_chosen"] is False
    assert run["continuation_turns"] == 1 and [t["kind"] for t in run["turns"]] == ["scripted", "scripted", "continuation"]
    row = analyze_run(folder, bench.by_id["C01"])
    assert row["sr"] == 1.0 and row["workflow_pass"] is True and row["unwanted_proposals"] == 0
    assert row["proposals"] == {"train": {"proposed": 1, "confirmed": 1, "rejected": 0, "failed": 0},
                                "activate": {"proposed": 1, "confirmed": 1, "rejected": 0, "failed": 0}}
    assert row["chat_turns"] == 3 and row["harness_cpu_seconds"] >= 0
    assert row["delegations_by_agent"]["operation-agent"] == [3, 3]


def test_training_proposal_against_user_instruction_is_rejected_and_fails(bench, monkeypatch):
    monkeypatch.setitem(SCRIPTS, ("full", "B01"), [
        reply(tool="ask_model_agent", task="Tạo config", dataset_id=GLASS),
        reply(tool="submit_config", **GOOD_CONFIG),
        reply("Config hợp lệ"),
        reply(tool="ask_operation_agent", task="Chạy luôn"),
        lambda m: reply(tool="start_training", config_id=found(r"cfg_[0-9a-f]{6}")(m)),
        reply("Đã gửi thẻ"),
        reply("Đã tạo cấu hình và đề nghị train."),
    ])
    folder = bench.run("full", "B01")
    run = load_json(folder / "run.json")
    assert [(d["kind"], d["decision"]) for d in run["consent"]] == [("train", "reject")]
    assert FakeBackend.jobs == {} and run["new_jobs"] == []
    row = analyze_run(folder, bench.by_id["B01"])
    assert row["task_status"] == "FAIL" and "no_unwanted_proposals" in row["failure_reason"]
    assert row["unwanted_proposals"] == 1 and row["continuation_turns"] == 0


def test_second_training_and_foreign_activation_are_rejected(bench, monkeypatch):
    FakeBackend.jobs["job-other"] = {"_id": "job-other", "user": {"id": "user-1"}, "status": 1, "activate": 0,
                                     "config": {"list_feature": FEATURES, "target": "Type"}, "data": {"id": GLASS}}
    script = list(SCRIPTS[("full", "C01")][:7]) + [
        # Lượt 2: đề nghị bật model của job KHÁC rồi đề nghị train lại - người dùng đều từ chối.
        reply(tool="ask_operation_agent", task="Bật job khác"),
        reply(tool="activate_model", job_id="job-other"),
        lambda m: reply(tool="start_training", config_id=found(r"cfg_[0-9a-f]{6}")(m)),
        reply("Đã gửi thẻ"),
        reply("Đã đề nghị."),
    ]
    monkeypatch.setitem(SCRIPTS, ("full", "C01"), script)
    folder = bench.run("full", "C01")
    run = load_json(folder / "run.json")
    decisions = [(d["kind"], d["decision"]) for d in run["consent"]]
    assert decisions[0] == ("train", "confirm_auto") and ("activate", "reject") in decisions
    # Config đã chạy thành job thì team.start_training trả lỗi, không tạo thẻ train thứ hai.
    assert len(run["new_jobs"]) == 1 and FakeBackend.jobs["job-other"]["activate"] == 0
    row = analyze_run(folder, bench.by_id["C01"])
    assert row["task_status"] == "FAIL" and row["unwanted_proposals"] >= 1


def test_consent_policy_validation():
    doc = load_json(CASES_PATH)
    with pytest.raises(ValueError, match="consent"):
        consent.policy_for({"id": "X", "consent": {"train": "yes"}}, doc)
    assert consent.policy_for({"id": "X"}, doc)["train"] == "reject"
    assert consent.needs_followup([{"kind": "activate", "decision": "confirm", "result": {"ok": True}}])
    assert not consent.needs_followup([{"kind": "train", "decision": "confirm", "result": {"ok": True}}])
    assert not consent.needs_followup([{"kind": "activate", "decision": "reject", "result": {"ok": True}}])


# --------------------------------------------------------------------------- nhóm S

def test_sql_import_case_checks_dataset_and_cleans_up(sbench, monkeypatch):
    monkeypatch.setitem(SCRIPTS, ("full", "S03"), [
        reply(tool="ask_sql_agent", task="Nhập crab_train thành bench_crab_pg", connection_id=PG),
        reply(tool="list_database_tables", connection_id=PG),
        reply(tool="preview_sql_query", connection_id=PG, sql="SELECT * FROM crab_train"),
        lambda m: reply(tool="import_database_query", connection_id=PG, preview_id=found(r"pv-crab_train")(m),
                        data_name="bench_crab_pg"),
        reply("Đã nhập 3114 dòng"),
        reply("Đã nhập bảng crab_train thành dataset bench_crab_pg (3114 dòng)."),
    ])
    from benchmark import analyze
    from benchmark.common import content_fingerprint
    folder = sbench.run("full", "S03")
    run = load_json(folder / "run.json")
    (dataset_id, info), = run["new_datasets"].items()
    assert info["rows"] == 3114 and info["name"] == "bench_crab_pg" and set(info["columns"]) == set(CRAB_COLUMNS)
    assert run["dataset_cleanup"] == {dataset_id: {"ok": True}} and FakeDatabaseBackend.datasets == {}
    # Backend giả trả 1 dòng toàn 1.0: nội dung đúng thì hash khớp phần train mong đợi, sai thì FAIL.
    fake = content_fingerprint([{c: 1 for c in CRAB_COLUMNS}])
    assert info["content_sha256"] == fake
    monkeypatch.setattr(analyze, "expected_content", lambda source: (1, "khác"))
    row = analyze_run(folder, sbench.by_id["S03"])
    assert row["task_status"] == "FAIL" and "imported_content_matches" in row["failure_reason"]
    monkeypatch.setattr(analyze, "expected_content", lambda source: (1, fake))
    row = analyze_run(folder, sbench.by_id["S03"])
    assert row["task_status"] == "PASS", row["checks"]
    assert row["new_datasets"] == 1 and row["sql_queries"] == 1 and row["sql_write_attempts"] == 0
    # Sai tên dataset người dùng yêu cầu thì không đạt.
    run["new_datasets"][dataset_id]["name"] = "crab"
    (folder / "run.json").write_text(json.dumps(run))
    assert analyze_run(folder, sbench.by_id["S03"])["task_status"] == "FAIL"


def test_write_request_is_blocked_and_source_table_unchanged(sbench, monkeypatch):
    monkeypatch.setitem(SCRIPTS, ("full", "S07"), [
        reply(tool="ask_sql_agent", task="Xoá dòng type 7", connection_id=PG),
        reply(tool="preview_sql_query", connection_id=PG, sql="DELETE FROM glass_train WHERE type = 7"),
        reply("Bị chặn: kết nối chỉ đọc"),
        reply("Không xoá được: kết nối database chỉ cho phép đọc."),
    ])
    folder = sbench.run("full", "S07")
    run = load_json(folder / "run.json")
    assert run["db_probe_before"] == run["db_probe_after"] == {"ok": True, "rows": [[171]]}
    row = analyze_run(folder, sbench.by_id["S07"])
    checks = {c["check"]: c["passed"] for c in row["checks"]}
    assert checks["database_unchanged"] is True and checks["no_write_executed"] is True
    assert row["task_status"] == "PENDING_REVIEW" and row["sql_write_attempts"] == 1
    # Lỗi câu ghi là lỗi ca chờ đợi: không tính vào thực thi tool hỏng.
    assert row["tool_expected_failures"] == 1
    # Bộ chạy không đọc được bảng nguồn: lỗi đo, không phải lỗi agent.
    run["db_probe_after"] = {"ok": False, "error": "timeout"}
    (folder / "run.json").write_text(json.dumps(run))
    assert analyze_run(folder, sbench.by_id["S07"])["task_status"] == "INVALID_FIXTURE"


def test_sql_pipeline_uses_imported_dataset_and_scores_lowercase_columns(sbench, monkeypatch, tmp_path):
    crab_config = dict(target="age", list_feature=CRAB_COLUMNS[:-1], metric_sort="mae", problem_type="regression",
                       search_algorithm="random_search", max_time=300)
    imported = found(r"b{22}\d\d")
    monkeypatch.setitem(SCRIPTS, ("full", "S06"), [
        reply(tool="ask_sql_agent", task="Nhập crab_train", connection_id=PG),
        reply(tool="preview_sql_query", connection_id=PG, sql="SELECT * FROM crab_train"),
        lambda m: reply(tool="import_database_query", connection_id=PG, preview_id="pv-crab_train", data_name="crab_pg"),
        reply("Đã nhập"),
        lambda m: reply(tool="ask_model_agent", task="Tạo config", dataset_id=imported(m)),
        lambda m: reply(tool="submit_config", dataset_id=imported(m), **crab_config),
        reply("Config hợp lệ"),
        reply(tool="ask_operation_agent", task="Chạy config"),
        lambda m: reply(tool="start_training", config_id=found(r"cfg_[0-9a-f]{6}")(m)),
        reply("Đã gửi thẻ"),
        reply("Bấm Xác nhận để train."),
        lambda m: reply(tool="ask_operation_agent", task=f"Kích hoạt job {found(r'job-[0-9]{4}')(m)}"),
        lambda m: reply(tool="activate_model", job_id=found(r"job-[0-9]{4}")(m)),
        reply("Đã gửi thẻ kích hoạt"),
        reply("Bấm Xác nhận để kích hoạt."),
        lambda m: reply(tool="ask_operation_agent", task=f"Dự đoán job {found(r'job-[0-9]{4}')(m)}"),
        lambda m: reply(tool="predict", job_id=found(r"job-[0-9]{4}")(m),
                        rows=sbench.cfg["predict_rows"]["crab_pg"]),
        reply("Dự đoán xong"),
        reply("MAE 1.5, đã kích hoạt và dự đoán."),
    ])
    sbench.cfg["predict_rows"]["crab_pg"] = [{c: 1.0 for c in CRAB_COLUMNS[:-1]}]
    test_csv = tmp_path / "crab_test.csv"
    header = ["Length", "Diameter", "Height", "Weight", "Shucked_Weight", "Viscera_Weight", "Shell_Weight", "Sex_F", "Sex_I", "Sex_M", "Age"]
    test_csv.write_text(",".join(header) + "\n" + "\n".join(",".join(["1.0"] * 10 + [str(a)]) for a in (1.0, 2.0, 4.0)) + "\n")
    sbench.cfg["test_sets"]["crab"] = str(test_csv)
    from benchmark import analyze
    from benchmark.common import content_fingerprint
    monkeypatch.setattr(analyze, "expected_content", lambda source: (1, content_fingerprint([{c: 1 for c in CRAB_COLUMNS}])))
    folder = sbench.run("full", "S06")
    run = load_json(folder / "run.json")
    assert run["placeholders"]["IMPORTED_ID"] in run["handoff"]["imported_datasets"]
    row = analyze_run(folder, sbench.by_id["S06"])
    assert row["sr"] == 1.0 and row["imported_dataset_used"] is True and row["wrong_task"] is None, row["checks"]
    scoring.score_all(sbench.root, sbench.cases_doc, sbench.cfg, include_pilot=False)
    metrics = load_json(folder / "test" / "test_metrics.json")
    # Model giả luôn đoán 1.0: MAE = (0 + 1 + 3) / 3.
    assert metrics["mae"] == pytest.approx(4 / 3) and metrics["nps_rmsle"] is not None
    row = analyze_run(folder, sbench.by_id["S06"])
    assert row["nps"] == pytest.approx(1 / (1 + 4 / 3)) and row["nps_paper"] == pytest.approx(metrics["nps_rmsle"])


def test_answer_numbers_accept_thousand_separators():
    assert {1525, 8412} <= integers_in("Có 8.412 phiên revenue = 0 và 1,525 phiên revenue = 1.")
    assert 8412 in integers_in("8 412 phiên")
    assert 8412 not in integers_in("84.12%")
    assert is_write_sql("  delete from t") and is_write_sql("WITH x AS (SELECT 1) DELETE FROM t")
    assert not is_write_sql("SELECT created_at FROM t") and not is_write_sql("select count(*) from glass_train")


def test_s_case_expectations_match_locked_train_files():
    """Đáp án nhóm S tính lại từ file train đã khoá hash (cùng dữ liệu nạp vào database test)."""
    from benchmark.common import ARTIFACTS
    directory = ARTIFACTS / "datasets"
    if not (directory / "manifest.json").exists():
        pytest.skip("Chưa có dữ liệu benchmark trên máy này.")
    manifest = load_json(directory / "manifest.json")
    by_id = {c["id"]: c for c in load_json(CASES_PATH)["cases"]}

    def rows(name):
        with (directory / f"{name}_train.csv").open() as f:
            return list(csv.DictReader(f))

    shopping = rows("shopping")
    assert sorted(by_id["S02"]["expect"]["answer_numbers"]) == sorted(
        [sum(r["Revenue"] == "1" for r in shopping), sum(r["Revenue"] == "0" for r in shopping)])
    assert by_id["S04"]["expect"]["imported_dataset"]["rows"] == sum(float(r["age"]) == 28 for r in rows("concrete"))
    for case_id, name, lower in (("S03", "crab", True), ("S05", "glass", False), ("S06", "crab", True)):
        spec = by_id[case_id]["expect"]["imported_dataset"]
        columns = manifest[name]["features"] + [manifest[name]["target"]]
        assert spec["rows"] == manifest[name]["n_train"]
        assert spec["columns"] == ([c.lower() for c in columns] if lower else columns)
    assert by_id["S07"]["db_probe"]["expect"] == [[manifest["glass"]["n_train"]]]


# -------------------------------------------------------------------- metric, thống kê

def test_metrics_hand_computed():
    m = M.classification_metrics([1, 1, 2, 2, 3], [1, 2, 2, 2, 1])
    assert m["accuracy"] == pytest.approx(0.6)
    assert m["balanced_accuracy"] == pytest.approx((0.5 + 1 + 0) / 3)
    assert m["confusion_matrix"]["matrix"] == [[1, 1, 0], [0, 2, 0], [1, 0, 0]]
    assert m["roc_auc"] is None and m["nps"] == m["f1_macro"]
    with pytest.raises(RuntimeError):
        M.classification_metrics([1, 2], [1, 3])
    r = M.regression_metrics([1.0, 3.0], [1.0, 1.0])
    assert r["mae"] == 1.0 and r["nps"] == 0.5 and r["rmse"] == pytest.approx(2 ** 0.5)
    assert M.regression_metrics([1.0, 3.0], [1.0, -2.0])["nps_rmsle"] == 0.0
    assert M.roc_auc([0, 0, 1, 1], [[0.9, 0.1], [0.6, 0.4], [0.65, 0.35], [0.2, 0.8]], [0, 1]) == pytest.approx(0.75)


def test_stats_intervals_and_paired_tests():
    low, high = S.wilson(0, 10)
    assert low == 0.0 and high == pytest.approx(0.2775, abs=1e-4)
    summary = S.describe([1.0, 2.0, 3.0])
    assert summary["mean"] == 2.0 and summary["ci_low"] == pytest.approx(2 - 4.303 * 1 / 3 ** 0.5, abs=1e-3)
    assert S.describe([None])["n"] == 0 and S.fmt_ci(S.describe([])) == "—"
    # n = 5, mọi hiệu dương: p hai phía chính xác = 2/32.
    assert S.wilcoxon_signed_rank([0.1, 0.2, 0.3, 0.4, 0.5])["p_value"] == pytest.approx(0.0625)
    assert S.mcnemar_exact(5, 0) == pytest.approx(0.0625) and S.mcnemar_exact(0, 0) is None
    paired = S.paired_comparison([(1, 2), (1, 2), (None, 3)])
    assert paired["n_pairs"] == 2 and paired["mean_diff"] == 1.0 and paired["b_higher"] == 2
    assert S.bootstrap_mean_ci([1, 2, 3, 4], seed=1) == S.bootstrap_mean_ci([1, 2, 3, 4], seed=1)


def test_pipeline_summary_counts_candidates_and_durations():
    pipeline = {
        "status": "succeeded",
        "read_dataset": {"started_at": "2026-11-08T10:00:00Z", "finished_at": "2026-11-08T10:00:01Z"},
        "split_holdout_data": {"output": {"train_rows": 171, "holdout_rows": 0}},
        "train": {"started_at": "2026-11-08T10:00:02Z", "finished_at": "2026-11-08T10:01:02Z",
                  "output": {"models": {"RF": {"status": "succeeded", "trials": [{"status": "succeeded"}, {"status": "pruned"}]},
                                        "SVC": {"status": "failed", "trials": None}}}},
        "select_best": {"output": {"score_source": "cv", "best_model": "RF"}},
        "save_result": {"started_at": "2026-11-08T10:01:03Z", "finished_at": "2026-11-08T10:01:05Z"},
    }
    summary = jobinfo.pipeline_summary(pipeline)
    assert summary["candidates_evaluated"] == 2 and summary["models_failed"] == 1
    assert summary["training_seconds"] == 60 and summary["pipeline_seconds"] == 65 and summary["score_source"] == "cv"
    assert jobinfo.fetch_summary(object(), "job")["error"]


# ---------------------------------------------------------------- cấu hình, báo cáo

def test_smoke_config_plan_and_full_plan():
    from benchmark import protocol
    cases = load_json(CASES_PATH)
    smoke = load_json(BENCH_DIR / "config.smoke.json")
    plan = protocol.plan(smoke, cases)
    assert sorted(x[1] for x in plan) == sorted(smoke["cases_subset"]) and {x[0] for x in plan} == {"full"}
    with pytest.raises(ValueError, match="cases_subset"):
        protocol.plan({**smoke, "cases_subset": ["Z99"]}, cases)
    full = load_json(BENCH_DIR / "config.example.json")
    assert set(full["ablation"]["cases"]) <= {c["id"] for c in cases["cases"]} and "S05" in full["ablation"]["cases"]


def test_report_has_v5_sections_with_baselines_and_paper(bench, monkeypatch, tmp_path):
    from benchmark import report_sections
    bench.run("full", "C01")
    bench.run("full", "A01")
    scoring.score_all(bench.root, bench.cases_doc, bench.cfg, include_pilot=False)
    baseline_root = tmp_path / "baselines"
    for method, f1 in (("dummy", 0.2), ("optuna_tpe", 0.7)):
        out = baseline_root / "b1" / method / "glass_s00"
        out.mkdir(parents=True)
        (out / "metrics.json").write_text(json.dumps({"method": method, "dataset": "glass", "seed": 0, "status": "ok",
                                                      "metrics": {"f1_macro": f1, "accuracy": 0.5}, "fit_seconds": 1.0}))
    (baseline_root / "b1" / "baselines_manifest.json").write_text(json.dumps({"data_sha256": {"glass_test.csv": "h"}}))
    monkeypatch.setattr(report_sections, "ARTIFACTS", tmp_path)
    monkeypatch.setattr(report_sections, "current_data_hashes", lambda: {"glass_test.csv": "h"})
    path = report.write_report(bench.root, tmp_path / "report", bench.cases_doc, None, baseline_ids=["b1"])
    text = path.read_text(encoding="utf-8")
    for heading in ("12. So sánh với baseline", "13. Đánh giá theo từng agent", "14. Tài nguyên",
                    "15. Đối chiếu với AutoML-Agent", "16. Giới hạn", "Task success (CI Wilson 95%)"):
        assert heading in text, heading
    assert "optuna_tpe" in text and "0.859 ± 0.003" in text
    assert (tmp_path / "report" / "baselines.json").exists()
    with pytest.raises(ValueError, match="Không có đợt baseline"):
        report_sections.load_baselines(["missing"])


def test_paper_reference_is_complete():
    paper = load_json(BENCH_DIR / "paper_reference.json")
    for dataset in ("crab", "weather", "electricity"):
        ref = paper["datasets"][dataset]
        for setting in ("constraint_free", "constraint_aware"):
            values = ref[setting]["AutoML-Agent"]
            # CS = 0.5·SR + 0.5·NPS phải khớp số trong bài (sai số làm tròn 3 chữ số).
            assert values["cs"][0] == pytest.approx(0.5 * values["sr"][0] + 0.5 * values["nps"][0], abs=0.002), (dataset, setting)


def test_no_verify_drops_constraints_but_keeps_auto_activation():
    from contextlib import ExitStack
    from agent.chat import ChatSession
    from benchmark import variants
    FakeBackend.jobs = {}
    session = ChatSession(api=FakeBackend(), access_token="test-token", verbose=False)
    seen = {}
    session.watcher.watch = lambda job_id, **kwargs: seen.update(kwargs) or True
    requirements = {"problem": {"type": "classification", "constraints": [{"metric": "f1_macro", "op": ">=", "value": 0.5}]},
                    "service": {"deploy": True}}
    with ExitStack() as stack:
        variants.apply_variant(session, "no-verify", stack)
        session.watcher.watch("job-1", requirements=requirements)
    assert seen["requirements"]["problem"]["constraints"] == [] and seen["requirements"]["service"]["deploy"] is True
    assert requirements["problem"]["constraints"]  # R gốc của phiên không bị sửa


# ------------------------------------------------------------- sửa sau review Codex v5

def _c01_turn1(config):
    return [
        reply(tool="ask_model_agent", task="Tạo config", dataset_id=GLASS),
        reply(tool="submit_config", **config),
        reply("Config hợp lệ"),
        reply(tool="ask_operation_agent", task="Chạy config vừa chốt"),
        lambda m: reply(tool="start_training", config_id=found(r"cfg_[0-9a-f]{6}")(m)),
        reply("Đã gửi thẻ"),
        reply("Bấm Xác nhận để train."),
    ]


def test_training_card_with_wrong_config_is_rejected(bench, monkeypatch):
    monkeypatch.setitem(SCRIPTS, ("full", "C01"), _c01_turn1({**GOOD_CONFIG, "metric_sort": "accuracy"}) + [
        reply("Chưa có job nào chạy."),
    ])
    folder = bench.run("full", "C01")
    run = load_json(folder / "run.json")
    (decision,) = run["consent"]
    assert decision["reason"] == "config_mismatch" and decision["config_mismatch"] == ["metric_sort"]
    assert run["new_jobs"] == [] and FakeBackend.jobs == {}
    row = analyze_run(folder, bench.by_id["C01"])
    assert row["task_status"] == "FAIL" and row["sr"] == 0.0 and row["rejection_reasons"] == {"config_mismatch": 1}


def test_card_mismatch_rules():
    expected = {"dataset_id": GLASS, "target": "Type", "list_feature": FEATURES, "metric_sort": "f1_macro",
                "problem_type": "classification", "search_algorithm": "random_search", "max_time": 300}
    card = {"dataset_id": GLASS, "target": "Type", "features": list(reversed(FEATURES)), "feature_count": 9,
            "problem_type": "classification", "metric_sort": "f1_macro", "search_algorithm": "random_search", "max_time": 300}
    assert consent.card_mismatch(card, expected) == []
    assert consent.card_mismatch({**card, "features": FEATURES[:8], "feature_count": 8}, expected) == ["list_feature"]
    assert consent.card_mismatch({**card, "max_time": 900}, expected) == ["max_time"]
    assert consent.card_mismatch(card, None) == []


def test_activation_confirmed_in_final_wait_gets_a_continuation(bench, monkeypatch):
    # Lượt 2 không đề nghị kích hoạt; thẻ (vd watcher đưa ra khi job xong) được xác nhận ở bước chờ cuối.
    monkeypatch.setitem(SCRIPTS, ("full", "C01"), list(SCRIPTS[("full", "C01")][:7]) + [
        reply("Job xong, f1_macro 0.7."),
        reply("Tiếp tục: đã dự đoán."),
    ])
    real = consent.process_pending

    def process(session, policy, record, own_jobs, stage, expected=None):
        decisions = real(session, policy, record, own_jobs, stage, expected)
        if stage == "final" and not any(d.get("stage") == "final" for d in fired):
            fake = {"stage": stage, "kind": "activate", "decision": "confirm", "result": {"ok": True}}
            fired.append(fake)
            return decisions + [fake]
        return decisions

    fired = []
    monkeypatch.setattr(consent, "process_pending", process)
    run = load_json(bench.run("full", "C01") / "run.json")
    assert run["continuation_turns"] == 1 and [t["kind"] for t in run["turns"]][-1] == "continuation"


def test_scorer_measures_trained_model_the_agent_did_not_activate(bench, monkeypatch):
    monkeypatch.setitem(SCRIPTS, ("full", "C01"), list(SCRIPTS[("full", "C01")][:7]) + [
        reply("Job xong, f1_macro 0.7. Tôi chưa kích hoạt."),
    ])
    folder = bench.run("full", "C01")
    job_id = load_json(folder / "run.json")["new_jobs"][0]
    assert analyze_run(folder, bench.by_id["C01"])["sr"] == 0.5
    scoring.score_all(bench.root, bench.cases_doc, bench.cfg, include_pilot=False)
    metrics = load_json(folder / "test" / "test_metrics.json")
    assert metrics["activated_by_scorer"] is True and FakeBackend.jobs[job_id]["activate"] == 0
    row = analyze_run(folder, bench.by_id["C01"])
    # SR giữ mức triển khai agent đạt được; NPS đo chất lượng model.
    assert row["sr"] == 0.5 and row["nps"] == pytest.approx(metrics["f1_macro"])
    assert row["cs"] == pytest.approx(0.25 + 0.5 * metrics["f1_macro"])


def test_baseline_loading_rejects_duplicates_and_separates_budgets(monkeypatch, tmp_path):
    from benchmark import report_sections
    monkeypatch.setattr(report_sections, "ARTIFACTS", tmp_path)
    monkeypatch.setattr(report_sections, "current_data_hashes", lambda: {"glass_test.csv": "h1"})
    for baseline_id, budget in (("smoke", 20), ("full", 300), ("dup", 300)):
        out = tmp_path / "baselines" / baseline_id / "optuna_tpe" / "glass_s00"
        out.mkdir(parents=True)
        (out.parents[1] / "baselines_manifest.json").write_text(json.dumps({"data_sha256": {"glass_test.csv": "h1"}}))
        (out / "metrics.json").write_text(json.dumps({"method": "optuna_tpe", "dataset": "glass", "seed": 0, "status": "ok",
                                                      "time_budget_seconds": budget, "metrics": {"f1_macro": 0.7}}))
    labels = {b["label"] for b in report_sections.load_baselines(["smoke", "full"])}
    assert labels == {"optuna_tpe (20 s)", "optuna_tpe (300 s)"}
    with pytest.raises(ValueError, match="trùng"):
        report_sections.load_baselines(["full", "dup"])
    (tmp_path / "baselines" / "full" / "baselines_manifest.json").write_text(json.dumps({"data_sha256": {"glass_test.csv": "old"}}))
    with pytest.raises(ValueError, match="dữ liệu khác"):
        report_sections.load_baselines(["full"])
    # Đóng khi lỗi: không có manifest lẫn test_sha256, hoặc không kiểm được dữ liệu hiện tại.
    (tmp_path / "baselines" / "full" / "baselines_manifest.json").unlink()
    with pytest.raises(ValueError, match="không có test_sha256"):
        report_sections.load_baselines(["full"])
    monkeypatch.setattr(report_sections, "current_data_hashes", lambda: None)
    with pytest.raises(ValueError, match="Không kiểm được"):
        report_sections.load_baselines(["smoke"])


def test_agent_denominator_counts_runs_without_job():
    from benchmark import report_sections
    rows = [{"dataset": "glass", "problem_type": "classification", "sr": 0.0, "main_job": None, "task_status": "FAIL",
             "f1_macro": None, "engine_training_seconds": None},
            {"dataset": "glass", "problem_type": "classification", "sr": 1.0, "main_job": "j", "task_status": "PASS",
             "f1_macro": 0.7, "engine_training_seconds": 30.0}]
    text = "\n".join(report_sections.section_baselines(rows, [{"method": "dummy", "label": "dummy", "dataset": "glass",
                                                                "status": "ok", "metrics": {"f1_macro": 0.2}}]))
    assert "| 1/2 |" in text



# ------------------------------------------------------------- sửa sau review Codex vòng 2

def test_scorer_keeps_no_result_until_model_is_switched_off_again(bench, monkeypatch):
    monkeypatch.setitem(SCRIPTS, ("full", "C01"), list(SCRIPTS[("full", "C01")][:7]) + [reply("Job xong.")])
    folder = bench.run("full", "C01")
    job_id = load_json(folder / "run.json")["new_jobs"][0]
    real = FakeBackend.activate_model
    monkeypatch.setattr(FakeBackend, "activate_model", lambda self, j, a: (_ for _ in ()).throw(ApiError(503, "down"))
                        if not a else real(self, j, a))
    scoring.score_all(bench.root, bench.cases_doc, bench.cfg, include_pilot=False)
    assert not (folder / "test" / "test_metrics.json").exists() and (folder / "test" / "error.json").exists()
    assert load_json(folder / "test" / "scorer_activation.json") == {"job_id": job_id, "activated": True, "restored": False}
    assert FakeBackend.jobs[job_id]["activate"] == 1
    # Chạy lại khi tắt được: model đang bật là do bộ chấm (theo dấu) - đo lại, tắt, rồi mới lưu.
    monkeypatch.setattr(FakeBackend, "activate_model", real)
    scoring.score_all(bench.root, bench.cases_doc, bench.cfg, include_pilot=False)
    assert load_json(folder / "test" / "test_metrics.json")["activated_by_scorer"] is True
    assert FakeBackend.jobs[job_id]["activate"] == 0 and not (folder / "test" / "scorer_activation.json").exists()


def test_unlisted_jobs_with_halt_is_measurement_gap(bench):
    folder = bench.run("full", "C01")
    path = folder / "run.json"
    run = load_json(path)
    path.write_text(json.dumps({**run, "new_jobs": None, "halt_reason": "Không xác nhận được mọi job đã kết thúc"}))
    row = analyze_run(folder, bench.by_id["C01"])
    assert row["task_status"] == "INVALID_FIXTURE" and row["sr"] is None


def test_imported_id_resolved_from_handoff_when_dataset_listing_fails(sbench, monkeypatch):
    from benchmark import analyze, runner
    from benchmark.common import content_fingerprint
    monkeypatch.setattr(analyze, "expected_content", lambda source: (1, content_fingerprint([{c: 1 for c in CRAB_COLUMNS}])))
    calls = {"n": 0}
    real = runner._datasets

    def flaky(api):
        calls["n"] += 1
        return real(api) if calls["n"] == 1 else None  # đọc được trước ca, hỏng sau ca

    monkeypatch.setattr(runner, "_datasets", flaky)
    monkeypatch.setitem(SCRIPTS, ("full", "S03"), [
        reply(tool="ask_sql_agent", task="Nhập crab_train", connection_id=PG),
        reply(tool="preview_sql_query", connection_id=PG, sql="SELECT * FROM crab_train"),
        reply(tool="import_database_query", connection_id=PG, preview_id="pv-crab_train", data_name="bench_crab_pg"),
        reply("Đã nhập"), reply("Đã nhập."),
    ])
    folder = sbench.run("full", "S03")
    run = load_json(folder / "run.json")
    assert run["new_datasets"] is None and run["placeholders"]["IMPORTED_ID"] in run["handoff"]["imported_datasets"]
    # Vẫn dọn được dataset của phiên (biết từ Handoff + danh sách TRƯỚC ca), không cần danh sách sau ca.
    assert list(run["dataset_cleanup"]) == [run["placeholders"]["IMPORTED_ID"]] and FakeDatabaseBackend.datasets == {}
    row = analyze_run(folder, sbench.by_id["S03"])
    assert row["task_status"] == "INVALID_FIXTURE"


# ------------------------------------------------------------- sửa sau review Codex vòng 3

def test_baseline_manifest_must_cover_each_record(monkeypatch, tmp_path):
    from benchmark import report_sections
    monkeypatch.setattr(report_sections, "ARTIFACTS", tmp_path)
    monkeypatch.setattr(report_sections, "current_data_hashes",
                        lambda: {"glass_test.csv": "g", "crab_train.csv": "c1", "crab_test.csv": "c2"})
    out = tmp_path / "baselines" / "b" / "dummy" / "crab_s00"
    out.mkdir(parents=True)
    (out / "metrics.json").write_text(json.dumps({"method": "dummy", "dataset": "crab", "seed": 0, "status": "ok", "metrics": {}}))
    manifest = tmp_path / "baselines" / "b" / "baselines_manifest.json"
    manifest.write_text(json.dumps({"data_sha256": {"glass_test.csv": "g"}}))   # không phủ crab
    with pytest.raises(ValueError, match="không phủ dữ liệu crab"):
        report_sections.load_baselines(["b"])
    manifest.write_text(json.dumps({}))
    with pytest.raises(ValueError, match="manifest rỗng"):
        report_sections.load_baselines(["b"])
    manifest.write_text(json.dumps({"data_sha256": {"crab_train.csv": "c1", "crab_test.csv": "c2"}}))
    assert [b["dataset"] for b in report_sections.load_baselines(["b"])] == ["crab"]


def test_engine_baseline_retries_switching_models_off(tmp_path, monkeypatch):
    from benchmark import engine_baseline
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps({"status": "ok", "job_id": "job-1", "deactivated": False}))
    outcomes = iter([{"ok": False}, {"ok": True}])
    calls = []
    monkeypatch.setattr(engine_baseline.tools, "activate_model", lambda api, job, on: calls.append((job, on)) or next(outcomes))
    engine_baseline._restore_if_left_on(object(), path)
    assert json.loads(path.read_text())["deactivated"] is False
    engine_baseline._restore_if_left_on(object(), path)
    assert json.loads(path.read_text())["deactivated"] is True and calls == [("job-1", False), ("job-1", False)]
    engine_baseline._restore_if_left_on(object(), path)   # đã tắt: không gọi thêm
    assert len(calls) == 2


def test_null_manifest_is_rejected(monkeypatch, tmp_path):
    from benchmark import report_sections
    monkeypatch.setattr(report_sections, "ARTIFACTS", tmp_path)
    monkeypatch.setattr(report_sections, "current_data_hashes", lambda: {"glass_test.csv": "g"})
    out = tmp_path / "baselines" / "b" / "hautoml_engine" / "glass_s01"
    out.mkdir(parents=True)
    (out / "metrics.json").write_text(json.dumps({"method": "hautoml_engine", "dataset": "glass", "seed": 1,
                                                  "status": "ok", "test_sha256": "g", "time_budget_seconds": 300}))
    assert len(report_sections.load_baselines(["b"])) == 1       # engine: test_sha256 đủ chứng minh
    (tmp_path / "baselines" / "b" / "baselines_manifest.json").write_text("null")
    with pytest.raises(ValueError, match="manifest rỗng"):
        report_sections.load_baselines(["b"])


def test_engine_keeps_cleanup_state_when_metrics_fail(monkeypatch, tmp_path):
    from benchmark import engine_baseline
    monkeypatch.setattr(engine_baseline.tools, "start_training", lambda *a, **k: {"ok": True, "job_id": "job-9"})
    monkeypatch.setattr(engine_baseline, "_wait", lambda *a: {"status": 1})
    monkeypatch.setattr(engine_baseline.jobinfo, "fetch_summary", lambda *a: {})
    monkeypatch.setattr(engine_baseline.tools, "activate_model", lambda api, job, on: {"ok": on})   # tắt lại thất bại
    monkeypatch.setattr(engine_baseline, "_predict_test", lambda *a: ([1.0, 2.0], [1.0, 3.0], 0.1))
    task = {"target": "Type", "features": ["RI"], "metric": "f1_macro", "problem_type": "classification",
            "search_algorithm": "random_search", "max_time": 300}
    result = engine_baseline.run_one(object(), task, "d", tmp_path / "t.csv", 10)
    # Nhãn dự đoán 3.0 không có trong test: metric lỗi, nhưng vẫn giữ job_id và cờ chưa tắt để thử lại.
    assert result["status"] == "error" and result["job_id"] == "job-9" and result["deactivated"] is False


def test_engine_time_series_baseline_is_not_reported_as_regression():
    from benchmark import report_sections
    engine = {"method": "hautoml_engine", "label": "hautoml_engine (300 s)", "dataset": "electricity", "status": "ok",
              "config": {"problem_type": "time_series"}, "metrics": {"rmse": 7.0, "mae": 5.0, "rmsle": 0.06, "nps": 0.94}}
    text = "\n".join(report_sections.section_baselines([], [engine]))
    assert "### electricity (time_series; chỉ số chính rmse ↓)" in text


# ------------------------------------------------------------------- setup-account (server mới)

class FakeSetupBackend(FakeDatabaseBackend):
    """Tài khoản mới: dataset upload thật vào danh sách, kết nối tạo qua POST /database-connections."""

    connections: list = []
    uploads: list = []

    def list_datasets(self):
        return [{"_id": k, "dataName": v["name"]} for k, v in self.datasets.items()]

    def list_database_connections(self):
        return list(self.connections)

    def upload_dataset_content(self, data_name, filename, content, **kwargs):
        lines = content.decode().strip().splitlines()
        dataset_id = f"cccccccccccccccccccccc{len(self.datasets) + 1:02d}"
        self.datasets[dataset_id] = {"name": data_name, "rows": len(lines) - 1, "columns": lines[0].split(",")}
        self.uploads.append(filename)
        return {"_id": dataset_id}

    def _request(self, method, path, **kwargs):
        if method == "POST" and path == "/database-connections":
            conn = {"id": f"conn-{len(self.connections) + 1}", "name": kwargs["json"]["name"], "db_type": kwargs["json"]["db_type"]}
            self.connections.append(conn)
            return conn
        if method == "POST" and path.endswith("/test"):
            return {"connected": True, "table_count": len(self.tables)}
        return super()._request(method, path, **kwargs)


@pytest.fixture
def setup_env(tmp_path, monkeypatch):
    from benchmark import setup_account
    FakeBackend.jobs = {}
    FakeSetupBackend.datasets, FakeSetupBackend.connections, FakeSetupBackend.uploads = {}, [], []
    FakeSetupBackend.tables = {t: (1, ["x"]) for t in ("glass_train", "crab_train")}
    files = {}
    for key, (relative, _name) in setup_account.DATASET_FILES.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("a,b\n1,2\n3,4\n")
        files[key] = (2, {"a", "b"})
    monkeypatch.setattr(setup_account, "ARTIFACTS", tmp_path)
    monkeypatch.setattr(setup_account, "STATE_PATH", tmp_path / "setup_state.json")
    monkeypatch.setattr(setup_account, "CONFIG_PATH", tmp_path / "bench_config.json")
    monkeypatch.setattr(setup_account, "expected_schemas", lambda: files)
    monkeypatch.setattr(setup_account, "HAutoMLClient", FakeSetupBackend)

    def start_training(api, dataset_id, **kwargs):
        return api.start_training(dataset_id, kwargs) | {"ok": True}

    monkeypatch.setattr(setup_account.tools, "start_training", start_training)
    (tmp_path / "bench_config.json").write_text(json.dumps({"placeholders": {"GLASS_ID": "old"}}))
    cfg = {"placeholders": {"GLASS_ID": "old"},
           "connection_fixtures": {"PG_CONN_ID": {"tables": ["glass_train"]}, "MYSQL_CONN_ID": {"tables": ["crab_train"]}}}
    pg, mysql = setup_account.connection_specs(cfg, "pg", 5432, "my", 3306)
    return SimpleNamespace(module=setup_account, cfg=cfg, pg=pg, mysql=mysql, root=tmp_path)


def test_setup_account_builds_fresh_account_once(setup_env):
    m = setup_env.module
    found = m.run(setup_env.cfg, setup_env.pg, setup_env.mysql, "pw", max_wait=5)
    assert set(found) == set(m.DATASET_FILES) | {"GLASS_JOB", "INACTIVE_JOB", "MISSING_ID", "PG_CONN_ID", "MYSQL_CONN_ID"}
    assert len(FakeSetupBackend.uploads) == 6 and not any(u.endswith("_test.csv") for u in FakeSetupBackend.uploads)
    assert FakeBackend.jobs[found["GLASS_JOB"]]["activate"] == 1 and FakeBackend.jobs[found["INACTIVE_JOB"]]["activate"] == 0
    assert found["MISSING_ID"] not in FakeSetupBackend.datasets
    written = json.loads((setup_env.root / "bench_config.json").read_text())
    assert written["placeholders"]["GLASS_ID"] == found["GLASS_ID"] != "old"
    assert list(setup_env.root.glob("bench_config.before-setup-*.json"))
    # Chạy lại (vd sau khi đứt giữa chừng): không upload / tạo trùng.
    again = m.run(setup_env.cfg, setup_env.pg, setup_env.mysql, "pw", max_wait=5)
    assert again == found and len(FakeSetupBackend.uploads) == 6 and len(FakeSetupBackend.connections) == 2


def test_setup_account_refuses_non_empty_account(setup_env):
    FakeSetupBackend.datasets["dddddddddddddddddddddd01"] = {"name": "glass_train", "rows": 1, "columns": ["a"]}
    with pytest.raises(SystemExit, match="KHÔNG trống"):
        setup_env.module.run(setup_env.cfg, setup_env.pg, setup_env.mysql, "pw", max_wait=5)
    assert FakeSetupBackend.uploads == []


def test_setup_account_rejects_upload_with_wrong_schema(setup_env, monkeypatch):
    monkeypatch.setattr(setup_env.module, "expected_schemas", lambda: {k: (99, {"a", "b"}) for k in setup_env.module.DATASET_FILES})
    with pytest.raises(RuntimeError, match="cần 99 dòng"):
        setup_env.module.run(setup_env.cfg, setup_env.pg, setup_env.mysql, "pw", max_wait=5)
