"""Kiểm dữ liệu 6 dataset mới (prepare_extra)."""

# Third-party
import pandas as pd
from pathlib import Path

# Local modules
from benchmark import prepare_extra


def _frame() -> pd.DataFrame:
    rows = []
    for i in range(200):
        label = "abc"[i % 3]
        rows.append({"f1": str(i // 2), "f2": "?" if i % 5 == 0 else "4.0", "y": label})
    # dòng trùng feature (cặp i, i+1 cùng f1 nhưng khác nhãn/f2 có thể khác); thêm trùng hẳn
    rows += [dict(rows[0]), dict(rows[1])]
    return pd.DataFrame(rows[:200])


def _keys(df):
    return set(df[["f1", "f2"]].itertuples(index=False, name=None))


def test_split_has_no_feature_overlap_and_all_classes():
    df = _frame()
    df = pd.concat([df, df.iloc[:6]], ignore_index=True).iloc[:200]
    train, test = prepare_extra.split_frame(df, "y")
    assert not (_keys(train) & _keys(test))
    assert set(train["y"]) == set(test["y"]) == {"a", "b", "c"}
    assert 0.1 <= len(test) / len(df) <= 0.3
    assert len(train) + len(test) == len(df)


def test_split_is_deterministic():
    df = _frame()
    a = prepare_extra.split_frame(df, "y")
    b = prepare_extra.split_frame(df, "y")
    assert a[0].equals(b[0]) and a[1].equals(b[1])


def test_values_kept_as_strings(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text("f1,f2,y\n" + "".join(f"{i},{'?' if i % 2 else '4.0'},{i % 2}\n" for i in range(60)))
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    train, test = prepare_extra.split_frame(df, "y")
    both = pd.concat([train, test])
    assert set(both["f2"]) == {"4.0", "?"}


def test_cv_threshold_rounds_down_to_005(monkeypatch):
    df = _frame()
    for score, expected in ((0.8734, 0.80), (0.85, 0.80)):
        monkeypatch.setattr(prepare_extra, "_cv_score", lambda *a, s=score: s)
        assert prepare_extra.cv_threshold(df, "y", "f1_macro") == expected


# ---- check_extra_data ----
import json  # noqa: E402
import shutil  # noqa: E402

import pytest  # noqa: E402

from benchmark import protocol  # noqa: E402


@pytest.fixture
def extra_env(tmp_path, monkeypatch):
    """Bản sao datasets/extra + raw trong thư mục tạm, trỏ prepare_extra vào đó."""
    src = prepare_extra.EXTRA_DIR
    _require_extra(raw=True)
    extra, raw = tmp_path / "extra", tmp_path / "raw"
    shutil.copytree(src, extra)
    raw.mkdir()
    manifest = json.loads((extra / "manifest_extra.json").read_text())
    for meta in manifest["datasets"].values():
        shutil.copy(prepare_extra.RAW_DIR / meta["raw_file"], raw / meta["raw_file"])
    monkeypatch.setattr(prepare_extra, "EXTRA_DIR", extra)
    monkeypatch.setattr(prepare_extra, "MANIFEST", extra / "manifest_extra.json")
    monkeypatch.setattr(prepare_extra, "RAW_DIR", raw)
    return extra, raw


def test_check_extra_data_ok_and_test_set_optional(extra_env):
    assert protocol.check_extra_data()["split_version"] == "feature-group-v1"
    assert protocol.check_extra_data({"test_sets": {}})
    extra, _ = extra_env
    cfg = {"test_sets": {"adult": str((extra / "adult_test.csv").relative_to(protocol.REPO))
                         if extra.is_relative_to(protocol.REPO) else str(extra / "adult_test.csv")}}
    assert protocol.check_extra_data(cfg)


def test_check_extra_data_missing_manifest_message(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare_extra, "MANIFEST", tmp_path / "none.json")
    with pytest.raises(ValueError) as exc:
        protocol.check_extra_data()
    assert "bench.py prepare-extra" in str(exc.value) and "rsync" in str(exc.value)


def test_check_extra_data_detects_hash_change(extra_env):
    extra, _ = extra_env
    path = extra / "adult_train.csv"
    data = bytearray(path.read_bytes())
    data[-3] ^= 1
    path.write_bytes(bytes(data))
    with pytest.raises(ValueError, match="Hash không khớp"):
        protocol.check_extra_data()


def test_check_extra_data_detects_raw_change(extra_env):
    _, raw = extra_env
    with (raw / "adult.csv").open("ab") as f:
        f.write(b"x")
    with pytest.raises(ValueError, match="File gốc thay đổi"):
        protocol.check_extra_data()


def test_check_extra_data_test_set_path(extra_env):
    with pytest.raises(ValueError, match="test_sets.adult"):
        protocol.check_extra_data({"test_sets": {"adult": "benchmark_artifacts/datasets/extra/adult_train.csv"}})


# ----------------------------------------------------------------------------- bộ chấm: cột chữ, nhãn chữ

def _write_csv(tmp_path, text):
    path = tmp_path / "t.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_read_test_keeps_text_features(tmp_path):
    from benchmark import scoring
    path = _write_csv(tmp_path, "age,workclass,income\n39,Private,<=50K\n50,?,>50K\n")
    x, _ = scoring._read_test(path, "income", problem_type="classification")
    assert x[0] == {"age": 39.0, "workclass": "Private"}
    assert x[1]["workclass"] == "?"


def test_read_test_string_labels_for_classification(tmp_path):
    from benchmark import scoring
    path = _write_csv(tmp_path, 'age,income\n39,<=50K\n50," >50K "\n')
    _, y = scoring._read_test(path, "income", problem_type="classification")
    assert y == ["<=50K", ">50K"]


def test_read_test_numeric_labels_unchanged_for_regression(tmp_path):
    from benchmark import scoring
    path = _write_csv(tmp_path, "a,y\n1,2.5\n3,4\n")
    _, y = scoring._read_test(path, "y")
    assert y == [2.5, 4.0] and all(isinstance(v, float) for v in y)


def test_metrics_classification_with_string_labels():
    from benchmark import metrics
    assert metrics.compute("classification", ["a", "b"], ["a", "a"])["accuracy"] == 0.5


def test_prediction_labels_compared_as_strings():
    from benchmark import metrics
    result = metrics.compute("classification", ["4.0", "1.0", " 2 "], [4.0, 1, "2"])
    assert result["accuracy"] == 1.0 and result["f1_macro"] == 1.0
    assert metrics.normalize_label("4.0") == metrics.normalize_label(4) == 4.0
    assert metrics.normalize_label(" >50K ") == ">50K"


# ----------------------------------------------------------------------------- kiểm tự động mới của ca G
# Dùng lại backend giả + LLM theo kịch bản của test_bench: chạy C01 thật qua runner rồi sửa run.json/trace
# để dựng từng tình huống của G02/G03/G05/G07/G08 (mọi trường giữ đúng dạng runner ghi ra).

import copy  # noqa: E402
import json  # noqa: E402

from benchmark.test_bench import FEATURES, bench  # noqa: E402,F401 - fixture dùng chung


def _c01(bench, **case_keys):
    folder = bench.run("full", "C01")
    case = copy.deepcopy(bench.by_id["C01"])
    expect = case_keys.pop("expect", {})
    case.update(case_keys)
    case["expect"].update(expect)
    return folder, case


def _edit_run(folder, change):
    path = folder / "run.json"
    run = json.loads(path.read_text())
    change(run)
    path.write_text(json.dumps(run))


def _drop_predicts(folder):
    """Bỏ mọi lời gọi/kết quả predict khỏi trace: agent không predict."""
    path = folder / "trace.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    keep = [r for r in records if not (isinstance(r.get("data"), dict) and r["data"].get("name") == "predict")]
    assert len(keep) < len(records)
    path.write_text("".join(json.dumps(r) + "\n" for r in keep))


def _checks(row):
    return {c["check"]: c["passed"] for c in row["checks"]}


def _set_features(run, features):
    job = run["new_jobs"][0]
    run["job_snapshots"][job]["config"]["list_feature"] = features
    for config in run["handoff"]["configs"].values():
        config["config"]["list_feature"] = features


def test_old_case_has_no_new_checks(bench):
    from benchmark.analyze import analyze_run
    folder = bench.run("full", "C01")
    row = analyze_run(folder, bench.by_id["C01"])
    names = set(_checks(row))
    assert not names & {"features_exclude", "auto_activated", "stays_inactive", "requirement_constraints"}
    assert "activated_and_predicted" in names and row["has_constraints"] is False


def test_features_free_ignores_feature_list_everywhere(bench):
    from benchmark.analyze import analyze_run, task_config, _job_matches_task
    folder, case = _c01(bench)
    _edit_run(folder, lambda run: _set_features(run, FEATURES[:5]))
    strict = analyze_run(folder, case)
    assert _checks(strict)["valid_config_matches_task"] is False
    assert strict["wrong_task"] == ["list_feature"] and strict["workflow_pass"] is False

    free = {**copy.deepcopy(case), "features_free": True}
    del free["task"]["features"]  # ca tự chọn cột không cần khai báo feature
    row = analyze_run(folder, free)
    assert _checks(row)["valid_config_matches_task"] is True
    assert row["wrong_task"] is None and row["workflow_pass"] is True and row["sr"] == 1.0
    # Cùng đáp án dùng cho bộ chấm test (scoring) và người dùng mô phỏng (thẻ train).
    expected = task_config(free, {"GLASS_ID": "x"})
    assert expected["list_feature"] is None
    assert _job_matches_task({"config": {"target": "Type", "list_feature": ["RI"], "metric_sort": "f1_macro",
                                         "problem_type": "classification", "search_algorithm": "random_search",
                                         "timeout": 86400}, "data": {"id": "x"}}, expected) == []
    from benchmark import consent
    card = {"dataset_id": "x", "target": "Type", "problem_type": "classification", "metric_sort": "f1_macro",
            "search_algorithm": "random_search", "max_time": 86400, "features": ["RI"], "feature_count": 1}
    assert consent.card_mismatch(card, expected) == []
    assert consent.card_mismatch({**card, "target": "Na"}, expected) == ["target"]


def test_features_exclude(bench):
    from benchmark.analyze import analyze_run
    folder, case = _c01(bench, features_free=True, expect={"features_exclude": ["PlayerID"]})
    row = analyze_run(folder, case)
    assert _checks(row)["features_exclude"] is True and row["task_status"] != "FAIL"

    _edit_run(folder, lambda run: _set_features(run, FEATURES + ["PlayerID"]))
    row = analyze_run(folder, case)
    assert _checks(row)["features_exclude"] is False and row["task_status"] == "FAIL"
    assert "PlayerID" in row["failure_reason"]

    # Chỉ job dính cột cấm (config đã bị thay) vẫn trượt.
    def only_job(run):
        _set_features(run, FEATURES)
        run["job_snapshots"][run["new_jobs"][0]]["config"]["list_feature"] = FEATURES + ["playerid"]
    _edit_run(folder, only_job)
    assert _checks(analyze_run(folder, case))["features_exclude"] is False


def test_features_exclude_without_config_or_job_passes(bench):
    from benchmark.analyze import analyze_run
    folder = bench.run("full", "A01")
    case = copy.deepcopy(bench.by_id["A01"])
    case["expect"]["features_exclude"] = ["StudentID"]
    assert _checks(analyze_run(folder, case))["features_exclude"] is True


def _set_source(source):
    def change(run):
        job = run["new_jobs"][0]
        run.setdefault("job_pipelines", {})
        if source is None:
            run["job_pipelines"][job] = {"error": "không đọc được pipeline"}
        else:
            run["job_pipelines"][job] = {"status": "succeeded", "score_source": source}
    return change


def test_auto_activated(bench):
    from benchmark.analyze import analyze_run
    folder, case = _c01(bench, expect={"auto_activated": True})
    _edit_run(folder, _set_source("holdout"))
    # C01 bật model qua thẻ kích hoạt: không phải tự kích hoạt.
    row = analyze_run(folder, case)
    assert _checks(row)["auto_activated"] is False and row["task_status"] == "FAIL"

    # Hold-out + tự bật (không có thẻ kích hoạt): đạt.
    _edit_run(folder, lambda run: run.update(consent=[d for d in run["consent"] if d["kind"] != "activate"]))
    assert _checks(analyze_run(folder, case))["auto_activated"] is True

    # Tự bật nhưng điểm chọn model là CV: không phải nhánh hold-out.
    _edit_run(folder, _set_source("cv"))
    assert _checks(analyze_run(folder, case))["auto_activated"] is False

    # Không đọc được nguồn điểm: chưa đo, không phải FAIL.
    _edit_run(folder, _set_source(None))
    row = analyze_run(folder, case)
    assert _checks(row)["auto_activated"] is None and row["task_status"] != "FAIL"
    _edit_run(folder, lambda run: run.pop("job_pipelines"))
    assert _checks(analyze_run(folder, case))["auto_activated"] is None

    # Model không bật: trượt dù nguồn điểm chưa rõ.
    _edit_run(folder, lambda run: run["job_snapshots"][run["new_jobs"][0]].update(activate=0))
    assert _checks(analyze_run(folder, case))["auto_activated"] is False


def _write_test_metrics(folder, nps=0.6):
    run = json.loads((folder / "run.json").read_text())
    (folder / "test").mkdir(exist_ok=True)
    (folder / "test" / "test_metrics.json").write_text(json.dumps({
        "job_id": run["new_jobs"][0], "protocol_id": run.get("protocol_id"), "nps": nps,
        "f1_macro": nps, "accuracy": 0.7, "score_source": "test", "activated_by_scorer": True}))


def test_stays_inactive(bench):
    from benchmark.analyze import analyze_run
    folder, case = _c01(bench, constraints=[{"metric": "f1_macro", "op": ">=", "value": 0.99}],
                        expect={"endpoint": "inactive"})
    # Agent vẫn bật và predict dù ngưỡng không đạt: trượt.
    row = analyze_run(folder, case)
    checks = _checks(row)
    assert checks["stays_inactive"] is False and "activated_and_predicted" not in checks
    assert row["workflow_pass"] is False and row["task_status"] == "FAIL"

    # Đúng: job xong, không bật, không predict; bộ chấm đã đo model trên test (tự bật tạm).
    _edit_run(folder, lambda run: run["job_snapshots"][run["new_jobs"][0]].update(activate=0))
    _drop_predicts(folder)
    _write_test_metrics(folder, nps=0.6)
    row = analyze_run(folder, case)
    checks = _checks(row)
    assert checks["stays_inactive"] is True and checks["job_succeeded"] is True
    assert not any(name.startswith("test") for name in checks)  # ngưỡng 0.99 không chấm như ràng buộc cần đạt
    assert row["workflow_pass"] is True and row["sr"] == 1.0 and row["nps"] == 0.6 and row["cs"] == 0.8
    assert row["has_constraints"] is False and row["all_constraints_pass"] is None
    assert row["task_status"] != "FAIL" and row["measurement_status"] == "complete"

    # Chưa chấm test: không lỗi, NPS còn thiếu.
    (folder / "test" / "test_metrics.json").unlink()
    row = analyze_run(folder, case)
    assert row["sr"] == 1.0 and row["nps"] is None and row["measurement_status"] == "incomplete"


def _set_requirements(constraints):
    def change(run):
        run["handoff"]["requirements"] = {"problem": {"type": "classification", "target": "Type",
                                                      "metric": "accuracy", "constraints": constraints}}
    return change


def test_requirement_constraints_without_requirements(bench):
    from benchmark.analyze import NO_PROMPT_AGENT_VARIANTS, analyze_run
    from benchmark.variants import VARIANTS
    folder, case = _c01(bench, expect={"requirement_constraints": [{"metric": "accuracy", "op": ">=", "value": 0.9}]})
    # Kịch bản không gọi Prompt Agent nên không có R.
    assert json.loads((folder / "run.json").read_text())["handoff"]["requirements"] is None
    # Biến thể có Prompt Agent (full): thiếu R là lỗi của agent, không phải chưa đo.
    row = analyze_run(folder, case)
    assert _checks(row)["requirement_constraints"] is False and row["task_status"] == "FAIL"
    # Biến thể không có Prompt Agent: bỏ hẳn tiêu chí (không vào checks, không làm PENDING/FAIL).
    assert set(NO_PROMPT_AGENT_VARIANTS) == {"single-agent", "no-prompt-agent"} <= set(VARIANTS)
    baseline = analyze_run(folder, _c01(bench)[1])
    for variant in NO_PROMPT_AGENT_VARIANTS:
        _edit_run(folder, lambda run, v=variant: run.update(variant=v))
        row = analyze_run(folder, case)
        assert "requirement_constraints" not in _checks(row), variant
        assert row["task_status"] == baseline["task_status"] and row["failure_reason"] == baseline["failure_reason"]
        # Kể cả khi có R (không nên xảy ra), biến thể này vẫn không chấm tiêu chí.
        _edit_run(folder, _set_requirements([{"metric": "accuracy", "op": ">=", "value": 90}]))
        assert "requirement_constraints" not in _checks(analyze_run(folder, case)), variant
        _edit_run(folder, lambda run: run["handoff"].update(requirements=None))


def test_requirement_constraints(bench):
    from benchmark.analyze import analyze_run
    folder, case = _c01(bench, expect={"requirement_constraints": [{"metric": "accuracy", "op": ">=", "value": 0.9}]})
    cases = [
        ([{"metric": "accuracy", "op": ">=", "value": 0.9}], True),
        ([{"metric": "Accuracy", "op": ">=", "value": 0.90000000001}, {"metric": "f1_macro", "op": ">=", "value": 0.5}], True),
        ([{"metric": "accuracy", "op": ">=", "value": 90}], False),  # chưa đổi % sang tỉ lệ
        ([{"metric": "accuracy", "op": ">=", "value": 0.9}, {"metric": "accuracy", "op": ">=", "value": 90}], False),
        ([{"metric": "accuracy", "op": ">", "value": 0.9}], False),
        ([], False),
    ]
    for constraints, expected in cases:
        _edit_run(folder, _set_requirements(constraints))
        assert _checks(analyze_run(folder, case))["requirement_constraints"] is expected, constraints


def _set_predictions(folder, value):
    """Thay nhãn trong mọi kết quả predict của trace (backend trả nhãn gốc: "<=50K", "n", "High"...)."""
    path = folder / "trace.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    hits = 0
    for r in records:
        data = r.get("data")
        if isinstance(data, dict) and data.get("name") == "predict" and (data.get("result") or {}).get("predictions"):
            for p in data["result"]["predictions"]:
                p["predict"] = value
                hits += 1
    assert hits
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


def test_text_label_predictions_valid_for_classification(bench):
    from benchmark.analyze import analyze_run
    folder, case = _c01(bench)
    base = analyze_run(folder, case)
    assert _checks(base)["prediction_output"] is True and _checks(base)["activated_and_predicted"] is True
    # Nhãn chữ của adult / wilt / gaming là dự đoán hợp lệ ở bài phân loại.
    for label in ("<=50K", ">50K", "n", "w", "High", " Medium "):
        _set_predictions(folder, label)
        row = analyze_run(folder, case)
        checks = _checks(row)
        assert checks["prediction_output"] is True and checks["activated_and_predicted"] is True, label
        assert (row["workflow_pass"], row["sr"], row["task_status"]) == (base["workflow_pass"], base["sr"], base["task_status"])
    # Nhãn số cũ (glass "1", 2, 2.0) vẫn hợp lệ như trước.
    for label in ("1", 2, 2.0):
        _set_predictions(folder, label)
        assert _checks(analyze_run(folder, case))["prediction_output"] is True, label
    # Rỗng / không phải giá trị vô hướng / bool / NaN: không phải dự đoán.
    for bad in ("", "   ", None, True, [1], {"a": 1}, float("nan")):
        _set_predictions(folder, bad)
        row = analyze_run(folder, case)
        assert _checks(row)["prediction_output"] is False and _checks(row)["activated_and_predicted"] is False, bad
        assert row["task_status"] == "FAIL"
    # Hồi quy (và ca không có task) vẫn đòi số hữu hạn.
    regression = copy.deepcopy(case)
    regression["task"]["problem_type"] = "regression"
    _set_predictions(folder, "n")
    assert _checks(analyze_run(folder, regression))["prediction_output"] is False
    _set_predictions(folder, "1.5")
    assert _checks(analyze_run(folder, regression))["prediction_output"] is True


def test_snapshot_locks_extra_manifest(tmp_path, monkeypatch):
    """Lock khoá cả manifest_extra: đổi split/ngưỡng nhóm G sau khi khoá thì verify_current từ chối."""
    from benchmark.common import BENCH_DIR, load_json
    cfg = load_json(BENCH_DIR / "config.example.json")
    manifest = {"split_version": "feature-group-v1", "thresholds": {"adult_f1_macro": 0.8}}
    seen = []
    monkeypatch.setattr(protocol, "check_data", lambda *_: {})
    monkeypatch.setattr(protocol, "check_ts_data", lambda *_: {})
    monkeypatch.setattr(protocol, "check_extra_data", lambda c=None: seen.append(c) or copy.deepcopy(manifest))
    monkeypatch.setattr(protocol, "source_hashes", lambda: {"agent.py": "same"})
    monkeypatch.setattr(protocol, "provider_settings", lambda _cfg: {"name": "test", "model": "m"})
    payload = protocol.snapshot(cfg, _cases_doc(), None, "pilot")
    assert payload["manifest_extra"] == manifest and seen[-1] is cfg  # kiểm cả test_sets của config
    protocol.freeze(tmp_path, payload)
    protocol.verify_current(tmp_path, cfg, _cases_doc(), None, "pilot")
    manifest["thresholds"]["adult_f1_macro"] = 0.75
    with pytest.raises(ValueError, match="đã thay đổi"):
        protocol.verify_current(tmp_path, cfg, _cases_doc(), None, "pilot")


def test_check_extra_data_requires_all_split_hashes(extra_env):
    extra, _ = extra_env
    path = extra / "manifest_extra.json"
    manifest = json.loads(path.read_text())
    assert len(manifest["sha256"]) == 12
    del manifest["sha256"]["wilt_test.csv"]
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="wilt_test.csv"):
        protocol.check_extra_data()


def test_check_extra_data_missing_manifest_mentions_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare_extra, "MANIFEST", tmp_path / "none.json")
    with pytest.raises(ValueError) as exc:
        protocol.check_extra_data()
    assert "benchmark_artifacts/datasets/extra/" in str(exc.value) and "benchmark_artifacts/raw/" in str(exc.value)


# ---- Task 5: setup-account, config, predict_rows ----
def _require_extra(raw: bool = False):
    """Test đọc dữ liệu thật: bỏ qua (skip) khi máy chưa có datasets/extra (hoặc file gốc trong raw/)."""
    files = [prepare_extra.MANIFEST] + [prepare_extra.EXTRA_DIR / f"{key}_{split}.csv"
                                         for key in prepare_extra.SPECS for split in ("train", "test")]
    if not all(p.is_file() for p in files):
        pytest.skip("chưa có benchmark_artifacts/datasets/extra")
    if raw and not all((prepare_extra.RAW_DIR / spec["raw"]).is_file() for spec in prepare_extra.SPECS.values()):
        pytest.skip("chưa có file gốc trong benchmark_artifacts/raw")


def test_setup_account_lists_extra_datasets():
    from benchmark.common import ARTIFACTS
    from benchmark.setup_account import DATASET_FILES
    for key in prepare_extra.SPECS:
        relative, name = DATASET_FILES[f"{key.upper()}_ID"]
        assert relative == f"datasets/extra/{key}_train.csv" and name == f"{key}_train"
    _require_extra()
    for key in prepare_extra.SPECS:
        assert (ARTIFACTS / DATASET_FILES[f"{key.upper()}_ID"][0]).is_file()


def test_predict_rows_are_first_test_row_without_target():
    """Như ca bảng cũ (glass/shopping/concrete/crab): 1 dòng, là dòng đầu phần test, bỏ cột target."""
    import csv
    _require_extra()
    for key, spec in prepare_extra.SPECS.items():
        rows = prepare_extra.predict_rows(key)
        assert len(rows) == 1, key
        features = load_manifest_features(key)
        assert spec["target"] not in rows[0] and list(rows[0]) == features
        with (prepare_extra.EXTRA_DIR / f"{key}_test.csv").open(newline="", encoding="utf-8") as f:
            first = next(csv.DictReader(f))
        from benchmark.scoring import _feature_value
        assert rows[0] == {k: _feature_value(v) for k, v in first.items() if k != spec["target"]}, key


def load_manifest_features(key):
    from benchmark.common import load_json
    return load_json(prepare_extra.MANIFEST)["datasets"][key]["features"]


def test_config_example_has_extra_test_sets():
    from benchmark.common import ARTIFACTS, load_json
    cfg = load_json(Path(__file__).parent / "config.example.json")
    for key in prepare_extra.SPECS:
        assert f"{key.upper()}_ID" in cfg["placeholders"]
        assert cfg["test_sets"][key] == f"benchmark_artifacts/datasets/extra/{key}_test.csv"
        assert len(cfg["predict_rows"][key]) == 1, key
    # Ca bảng cũ cũng dùng đúng 1 dòng.
    assert all(len(cfg["predict_rows"][key]) == 1 for key in ("glass", "shopping", "concrete", "crab"))
    _require_extra()
    local = load_json(ARTIFACTS / "bench_config.json")
    for key in prepare_extra.SPECS:
        assert cfg["predict_rows"][key] == prepare_extra.predict_rows(key), key
        if local:
            assert local["predict_rows"][key] == prepare_extra.predict_rows(key), key


# ---- Task 6: 12 ca nhóm G, ablation, báo cáo ----
G_IDS = [f"G{i:02d}" for i in range(1, 13)]
G_ABLATION = ["G03", "G05", "G06", "G07", "G08", "G10"]


def _cases_doc():
    from benchmark.common import CASES_PATH, load_json
    return load_json(CASES_PATH)


def _g_cases():
    return {c["id"]: c for c in _cases_doc()["cases"] if c["group"] == "G"}


def _manifest():
    from benchmark.common import load_json
    _require_extra()
    return load_json(prepare_extra.MANIFEST)


def test_group_g_cases_valid():
    from benchmark.test_bench import validate_case
    doc = _cases_doc()
    assert doc["version"] == "hautoml-bench-v6"
    cases = _g_cases()
    assert list(cases) == G_IDS
    datasets = set(prepare_extra.SPECS)
    for case_id, case in cases.items():
        validate_case(case, doc)
        assert case["title"] and case["turns"] and case["expect"].get("manual"), case_id
        if case["flow"] == "train":
            task = case["task"]
            assert task["dataset"] in datasets and task["dataset_id"] == f"<{task['dataset'].upper()}_ID>"
            assert task["problem_type"] == "classification"
            assert task["target"] == _manifest()["datasets"][task["dataset"]]["target"]
            assert set(task["features"]) <= set(_manifest()["datasets"][task["dataset"]]["features"])
            assert (task["search_algorithm"], task["max_time"]) == ("random_search", 86400)
            assert case["expect"]["config"] == "match_task"
            assert (case["expect"]["min_new_jobs"], case["expect"]["max_new_jobs"]) == (1, 1)
            assert task["dataset_id"] in case["turns"][0] and len(case["turns"]) == 1
        else:
            assert case["expect"]["max_new_jobs"] == 0 and "start_training" in case["expect"]["tools_forbidden"]
            assert "consent" not in case  # chat: mặc định từ chối mọi thẻ
    # Ca train dùng mọi cột còn lại (trừ G08 tự chọn cột): đáp án = mọi feature trong manifest.
    for case_id in ("G01", "G02", "G03", "G04", "G07", "G09", "G12"):
        task = cases[case_id]["task"]
        assert task["features"] == _manifest()["datasets"][task["dataset"]]["features"], case_id


def test_group_g_case_details():
    cases = _g_cases()
    manifest = _manifest()["datasets"]
    # G03: ngưỡng không đạt được -> model phải ở trạng thái tắt, không predict; không vào nhóm "có ràng buộc".
    g03 = cases["G03"]
    assert "f1_macro >= 0.99" in g03["turns"][0]
    assert g03["expect"]["endpoint"] == "inactive" and g03["expect"]["predict_ok"] is False
    assert g03["consent"]["activate"] == "reject"
    # G02: tự kích hoạt theo điểm hold-out, không cần (và không chấp nhận) thẻ kích hoạt.
    g02 = cases["G02"]
    assert g02["expect"]["auto_activated"] is True
    assert g02["consent"] == {"train": "confirm_auto", "activate": "reject", "auto_activate": "confirm"}
    # G04: không liệt kê 500 cột trong câu lệnh.
    g04 = cases["G04"]
    assert "toàn bộ 500 cột còn lại" in g04["turns"][0] and "V1," not in g04["turns"][0]
    assert len(g04["task"]["features"]) == 500
    # G05/G08: agent tự chọn cột, cột ID không được dùng.
    g05, g08 = cases["G05"], cases["G08"]
    assert g05["features_free"] is True and g05["expect"]["features_exclude"] == ["StudentID"]
    assert g05["flow"] == "chat" and "GPA" in g05["expect"]["manual"]
    assert g08["features_free"] is True and g08["expect"]["features_exclude"] == ["PlayerID"]
    assert g08["task"]["features"] == [f for f in manifest["gaming"]["features"] if f != "PlayerID"]
    # G06: hỏi lại target, không tạo config.
    assert cases["G06"]["expect"]["config"] == "none" and "GradeClass" in cases["G06"]["expect"]["manual"]
    # G07: "90%" phải được chuẩn hoá thành 0.9 trong R; ngưỡng kiểm trên test.
    g07 = cases["G07"]
    assert "accuracy tối thiểu 90%" in g07["turns"][0]
    assert g07["constraints"] == g07["expect"]["requirement_constraints"] == [{"metric": "accuracy", "op": ">=", "value": 0.9}]
    # G10/G11: cấu hình sai loại bài toán / metric -> từ chối, không tạo config.
    for case_id in ("G10", "G11"):
        assert cases[case_id]["expect"]["config"] == "none", case_id
    assert "regression" in cases["G10"]["turns"][0] and "mae" in cases["G10"]["turns"][0]
    assert "classification" in cases["G11"]["turns"][0] and "mae" in cases["G11"]["turns"][0]
    # G12: người dùng chốt mọi cột, kể cả GPA và StudentID.
    g12 = cases["G12"]
    assert {"GPA", "StudentID"} <= set(g12["task"]["features"]) and "GradeClass" not in g12["task"]["features"]
    assert "GPA" in g12["expect"]["manual"] and "StudentID" in g12["expect"]["manual"]


def test_group_g_thresholds_match_manifest():
    cases = _g_cases()
    thresholds = _manifest()["thresholds"]
    for case_id, key in (("G02", "adult_f1_macro"), ("G09", "wilt_f1_macro")):
        value = thresholds[key]
        assert cases[case_id]["constraints"] == [{"metric": "f1_macro", "op": ">=", "value": value}], case_id
        assert f"f1_macro >= {value:.2f}" in cases[case_id]["turns"][0], case_id


def test_ablation_includes_targeted_g_cases():
    from benchmark.common import ARTIFACTS, load_json
    old = ["A02", "B01", "B03", "B04", "B05", "C01", "C03", "C05", "C07", "C08", "F01", "F03", "S05"]
    paths = [Path(__file__).parent / "config.example.json", ARTIFACTS / "bench_config.json"]
    for path in [p for p in paths if p.is_file()]:
        assert load_json(path)["ablation"]["cases"] == old + G_ABLATION, path


def test_plan_counts():
    from benchmark.common import load_json
    cfg = load_json(Path(__file__).parent / "config.example.json")
    plan = protocol.plan(cfg, _cases_doc())
    assert sum(x[0] == "full" for x in plan) == 295
    assert sum(x[0] != "full" for x in plan) == 285
    assert {x[1] for x in plan if x[0] != "full"} >= set(G_ABLATION)


def test_preflight_has_no_error_for_g_cases():
    """Ca G đủ placeholder / predict_rows / test_sets trong config mẫu (khi điền ID)."""
    from benchmark.common import load_json
    cfg = load_json(Path(__file__).parent / "config.example.json")
    cfg["placeholders"] = {k: "x" * 24 for k in cfg["placeholders"]}
    errors, _ = protocol.preflight(cfg, _cases_doc(), G_IDS)
    relevant = [e for e in errors if any(w in e for w in ("placeholders", "predict_rows", "test_sets", "ablation", "mã ca"))]
    assert not relevant


def test_report_group_g_label_and_constraint_buckets():
    from benchmark import report
    assert report.GROUP_TITLES["G"] == "Dataset mở rộng" and "G" in report._ADDED_GROUPS
    # Bucket "Có ràng buộc" theo has_constraints của dòng đã phân tích: ca giữ model tắt (G03, endpoint
    # inactive) có constraints trong cases.json nhưng chấm theo thang không ràng buộc.
    rows = [
        {"scenario_id": "C01", "has_constraints": False},
        {"scenario_id": "C05", "has_constraints": True},
        {"scenario_id": "G03", "has_constraints": False},
    ]
    free, bound = report._constraint_buckets(rows)
    assert [r["scenario_id"] for r in free] == ["C01", "G03"]
    assert [r["scenario_id"] for r in bound] == ["C05"]


def _edit_predict_rows(folder, change):
    """Sửa mẫu agent gửi trong mọi bản ghi predict (tool_call + tool_result) của trace."""
    path = folder / "trace.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    hits = 0
    for r in records:
        data = r.get("data")
        if isinstance(data, dict) and data.get("name") == "predict" and (data.get("arguments") or {}).get("rows"):
            data["arguments"]["rows"] = [change(dict(row)) for row in data["arguments"]["rows"]]
            hits += 1
    assert hits
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


def test_features_free_predict_rows_compared_on_job_features(bench):
    """G08: agent bỏ cột ID khỏi mẫu trước khi predict (model không dùng cột đó) thì vẫn là dự đoán đúng mẫu."""
    from benchmark.analyze import analyze_run
    folder, case = _c01(bench)
    kept = [f for f in FEATURES if f != "Fe"]
    _edit_run(folder, lambda run: _set_features(run, kept))

    def drop_fe(row):
        row.pop("Fe", None)
        return row
    _edit_predict_rows(folder, drop_fe)
    # Ca thường: thiếu cột so với mẫu người dùng -> không phải dự đoán đúng mẫu (hành vi cũ giữ nguyên).
    strict = analyze_run(folder, {**case, "task": {**case["task"], "features": kept}})
    assert _checks(strict)["prediction_output"] is False
    free = {**copy.deepcopy(case), "features_free": True}
    row = analyze_run(folder, free)
    assert _checks(row)["prediction_output"] is True and row["workflow_pass"] is True
    # Vẫn so giá trị trên các cột model dùng: agent đổi giá trị thì trượt.
    _edit_predict_rows(folder, lambda r: {**r, "RI": 99.0})
    assert _checks(analyze_run(folder, free))["prediction_output"] is False


def test_g06_g02_manual_wording():
    cases = _g_cases()
    assert "GPA – hồi quy, GradeClass – phân loại" in cases["G06"]["expect"]["manual"]
    assert "Kiểm tự động" in cases["G02"]["expect"]["manual"] and "hold-out" in cases["G02"]["expect"]["manual"]


def test_extra_manifest_keeps_raw_column_order():
    """wilt có target `class` ở cột đầu (G09): file chia giữ đúng thứ tự cột gốc."""
    import csv
    _require_extra(raw=True)
    manifest = _manifest()["datasets"]
    for key, meta in manifest.items():
        with (prepare_extra.RAW_DIR / meta["raw_file"]).open(newline="", encoding="utf-8") as f:
            raw_header = next(csv.reader(f))
        assert meta["columns"] == raw_header, key
        assert meta["features"] == [c for c in raw_header if c != meta["target"]], key
        for split in ("train", "test"):
            with (prepare_extra.EXTRA_DIR / f"{key}_{split}.csv").open(newline="", encoding="utf-8") as f:
                assert next(csv.reader(f)) == raw_header, (key, split)
    assert manifest["wilt"]["columns"][0] == "class"
    rows = prepare_extra.predict_rows("wilt")
    assert all("class" not in r and list(r) == manifest["wilt"]["features"] for r in rows)


# ------------------------------------------------------------------------------ baseline (Task 7)

def test_baselines_load_extra_dataset():
    from benchmark import baselines

    _require_extra(raw=True)  # dataset_spec chạy check_extra_data (băm cả file gốc)
    spec = baselines.dataset_spec("wilt")
    assert spec["problem_type"] == "classification" and spec["target"] == "class"
    train, test = pd.read_csv(spec["train"]), pd.read_csv(spec["test"])
    assert list(train.columns)[0] == "class" and spec["target"] not in spec["features"]
    assert train["class"].map(type).eq(str).all() and set(test["class"]) <= set(train["class"])
    assert set(spec["features"]) <= set(train.columns)


def _adult_like(n: int = 50) -> pd.DataFrame:
    return pd.DataFrame({
        "age": [20 + i for i in range(n)],
        "workclass": [["Private", "?", "State-gov", "Self-emp"][i % 4] for i in range(n)],
        "education": ["Bachelors" if i % 3 else "HS-grad" for i in range(n)],
        "income": ["<=50K" if i % 2 else ">50K" for i in range(n)],
    })


def test_baseline_pipeline_handles_text_columns():
    from benchmark import baselines

    df = _adult_like()
    x, y = df[["age", "workclass", "education"]], df["income"]
    for method in ("random_forest", "linear", "xgboost"):
        model = baselines._build(method, "classification", 0, x=x).fit(x, y)
        unseen = x.iloc[:3].assign(workclass="Never-worked")      # giá trị lạ ở test không làm lỗi
        assert set(model.predict(unseen)) <= {"<=50K", ">50K"}
    # Dữ liệu chỉ có cột số: không bọc thêm, mô hình cũ giữ nguyên.
    numeric = x[["age"]]
    assert type(baselines._build("random_forest", "classification", 0, x=numeric)).__name__ == "RandomForestClassifier"


def test_baseline_cv_score_keeps_text_labels():
    from benchmark import baselines

    df = _adult_like(60)
    x, y = df[["age", "workclass", "education"]], df["income"]
    score = baselines._cv_score(lambda: baselines._build("random_forest", "classification", 0, x=x), x, y,
                                "classification", 0)
    assert 0.0 <= score <= 1.0


def test_engine_oracle_covers_new_datasets():
    from benchmark import engine_baseline
    from benchmark.common import load_json
    from benchmark.common import REPO

    tasks = engine_baseline.oracle_tasks(load_json(REPO / "benchmark" / "cases.json"))
    assert {k: tasks[k]["case_id"] for k in ("adult", "madelon", "digits", "gaming", "wilt")} == {
        "adult": "G01", "madelon": "G04", "digits": "G07", "gaming": "G08", "wilt": "G09"}
    student = tasks["student"]
    assert "StudentID" not in student["features"] and "GPA" not in student["features"]
    assert student["target"] == "GradeClass" and student["problem_type"] == "classification"
    assert "PlayerID" not in tasks["gaming"]["features"]
    assert tasks["glass"]["case_id"] == "C01"       # dataset cũ không đổi


def test_engine_predict_test_keeps_text_labels(tmp_path, monkeypatch):
    from benchmark import engine_baseline

    test_csv = tmp_path / "t.csv"
    test_csv.write_text("age,workclass,income\n30,?,<=50K\n40,Private,>50K\n", encoding="utf-8")
    monkeypatch.setattr(engine_baseline.tools, "predict", lambda api, job, batch: {
        "ok": True, "predictions": [{"predict": "<=50K"}, {"predict": " >50K "}]})
    task = {"problem_type": "classification", "target": "income"}
    y_true, y_pred, _ = engine_baseline._predict_test(object(), "job", task, test_csv)
    assert y_true == ["<=50K", ">50K"] and y_pred == ["<=50K", ">50K"]
    # Nhãn số: "4.0" và 4 cùng về một dạng; hồi quy vẫn là float.
    monkeypatch.setattr(engine_baseline.tools, "predict", lambda api, job, batch: {
        "ok": True, "predictions": [{"predict": "1"}, {"predict": 2.0}]})
    test_csv.write_text("a,y\n1,1.0\n2,2\n", encoding="utf-8")
    assert engine_baseline._predict_test(object(), "j", {"problem_type": "classification", "target": "y"}, test_csv)[1] == [1.0, 2.0]
    assert engine_baseline._predict_test(object(), "j", {"problem_type": "regression", "target": "y"}, test_csv)[1] == [1.0, 2.0]


def test_config_metrics_for_group_g(bench):
    """Ca train nhóm G có số điền config (config_field_accuracy, first_config_valid); ca chat G vẫn None."""
    from benchmark.analyze import analyze_run
    folder, case = _c01(bench)
    old = analyze_run(folder, case)
    assert old["config_field_accuracy"] == 1.0 and old["first_config_valid"] is True
    g_train = {**copy.deepcopy(case), "group": "G"}
    row = analyze_run(folder, g_train)
    assert (row["config_field_accuracy"], row["first_config_valid"]) == (1.0, True)
    # Tự chọn cột (G08): so 6 trường, vẫn có số.
    free = {**copy.deepcopy(g_train), "features_free": True}
    assert analyze_run(folder, free)["config_field_accuracy"] == 1.0
    # Ca chat G (config "none" như G06/G10/G11, hoặc không có đáp án như G05): không tính.
    for expect in ({"config": "none", "max_new_jobs": 0}, {"max_new_jobs": 0}):
        chat = {**copy.deepcopy(g_train), "flow": "chat", "expect": expect}
        chat.pop("task", None)
        row = analyze_run(folder, chat)
        assert row["config_field_accuracy"] is None and row["first_config_valid"] is None
