"""
Đối chiếu metric và thống kê viết tay (benchmark/metrics.py, stats.py) với sklearn / scipy.

Chạy trong image backend (có sklearn/scipy, không cần mạng):

    docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/repo -w /repo \\
        hautoml-backend-test:local python -I -m pytest -q -p no:cacheprovider benchmark/test_reference_impl.py

Venv của agent không có sklearn: các test ở đây tự bỏ qua khi thiếu.
"""

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

sklearn_metrics = pytest.importorskip("sklearn.metrics")
scipy_stats = pytest.importorskip("scipy.stats")

from benchmark import metrics as M  # noqa: E402
from benchmark import stats as S  # noqa: E402


def _classification_case(seed: int, classes: int, n: int = 60):
    rng = random.Random(seed)
    labels = [float(c) for c in range(1, classes + 1)]
    y_true = [rng.choice(labels) for _ in range(n)]
    for label in labels:  # đủ mọi lớp trong test, như bộ chấm yêu cầu
        y_true[rng.randrange(n)] = label
    y_pred = [t if rng.random() < 0.6 else rng.choice(labels) for t in y_true]
    proba = []
    for t in y_true:
        raw = [rng.random() + (1.5 if c == t and rng.random() < 0.7 else 0) for c in labels]
        total = sum(raw)
        proba.append([r / total for r in raw])
    return y_true, y_pred, proba, labels


@pytest.mark.parametrize("seed,classes", [(0, 2), (1, 3), (2, 6), (3, 2)])
def test_classification_matches_sklearn(seed, classes):
    y_true, y_pred, proba, labels = _classification_case(seed, classes)
    ours = M.classification_metrics(y_true, y_pred, proba, labels)
    assert ours["accuracy"] == pytest.approx(sklearn_metrics.accuracy_score(y_true, y_pred))
    assert ours["balanced_accuracy"] == pytest.approx(sklearn_metrics.balanced_accuracy_score(y_true, y_pred))
    kw = {"labels": sorted(set(y_true)), "zero_division": 0}
    assert ours["precision_macro"] == pytest.approx(sklearn_metrics.precision_score(y_true, y_pred, average="macro", **kw))
    assert ours["recall_macro"] == pytest.approx(sklearn_metrics.recall_score(y_true, y_pred, average="macro", **kw))
    assert ours["f1_macro"] == pytest.approx(sklearn_metrics.f1_score(y_true, y_pred, average="macro", **kw))
    assert ours["f1_weighted"] == pytest.approx(sklearn_metrics.f1_score(y_true, y_pred, average="weighted", **kw))
    expected_cm = sklearn_metrics.confusion_matrix(y_true, y_pred, labels=sorted(set(y_true))).tolist()
    assert ours["confusion_matrix"]["matrix"] == expected_cm
    if classes == 2:
        reference = sklearn_metrics.roc_auc_score(y_true, [p[1] for p in proba])
    else:
        reference = sklearn_metrics.roc_auc_score(y_true, proba, multi_class="ovr", average="macro", labels=labels)
    assert ours["roc_auc"] == pytest.approx(reference)


def test_auc_with_ties_matches_sklearn():
    y_true = [0.0, 0.0, 1.0, 1.0, 1.0, 0.0]
    scores = [0.1, 0.5, 0.5, 0.9, 0.5, 0.3]
    proba = [[1 - s, s] for s in scores]
    assert M.roc_auc(y_true, proba, [0.0, 1.0]) == pytest.approx(sklearn_metrics.roc_auc_score(y_true, scores))


def test_regression_matches_sklearn():
    rng = random.Random(7)
    y_true = [rng.uniform(1, 30) for _ in range(80)]
    y_pred = [t + rng.gauss(0, 3) for t in y_true]
    y_pred = [max(p, 0.01) for p in y_pred]
    ours = M.regression_metrics(y_true, y_pred)
    assert ours["mae"] == pytest.approx(sklearn_metrics.mean_absolute_error(y_true, y_pred))
    assert ours["rmse"] == pytest.approx(math.sqrt(sklearn_metrics.mean_squared_error(y_true, y_pred)))
    assert ours["r2"] == pytest.approx(sklearn_metrics.r2_score(y_true, y_pred))
    assert ours["rmsle"] == pytest.approx(math.sqrt(sklearn_metrics.mean_squared_log_error(y_true, y_pred)))
    assert ours["mape"] == pytest.approx(sklearn_metrics.mean_absolute_percentage_error(y_true, y_pred))


@pytest.mark.parametrize("seed,n", [(0, 6), (1, 12), (2, 20), (3, 40)])
def test_wilcoxon_matches_scipy(seed, n):
    rng = random.Random(seed)
    diffs = [round(rng.gauss(0.2, 1), 1) for _ in range(n)]
    diffs = [d for d in diffs if d != 0] or [0.5]
    ours = S.wilcoxon_signed_rank(diffs)
    method = "exact" if ours["method"] == "exact" and len(set(abs(d) for d in diffs)) == len(diffs) else "approx"
    reference = scipy_stats.wilcoxon(diffs, zero_method="wilcox", correction=method == "approx", method=method)
    assert min(ours["w_plus"], ours["w_minus"]) == pytest.approx(reference.statistic)
    # Có hạng trùng thì scipy không có p chính xác: chỉ so khi không trùng hoặc cùng dùng xấp xỉ.
    if method == "exact" or ours["method"] == "normal":
        assert ours["p_value"] == pytest.approx(reference.pvalue, rel=1e-6 if method == "exact" else 0.05)


def test_t_interval_matches_scipy():
    data = [0.71, 0.75, 0.69, 0.80, 0.77]
    summary = S.describe(data)
    low, high = scipy_stats.t.interval(0.95, len(data) - 1, loc=summary["mean"], scale=scipy_stats.sem(data))
    assert summary["ci_low"] == pytest.approx(low, abs=1e-3) and summary["ci_high"] == pytest.approx(high, abs=1e-3)
    for df in (31, 40, 100):
        assert S.t_critical(df) == pytest.approx(scipy_stats.t.ppf(0.975, df), abs=2e-3)


@pytest.mark.parametrize("method,dataset", [("dummy", "glass"), ("random_forest", "crab"), ("lag_ridge", "electricity")])
def test_baseline_reads_test_only_after_fitting(method, dataset, monkeypatch):
    """Chống rò rỉ: file test chỉ được đọc SAU khi mô hình đã fit (và chọn tham số) xong trên train."""
    from benchmark import baselines
    from benchmark.common import ARTIFACTS
    if not (ARTIFACTS / "datasets" / "manifest.json").exists():
        pytest.skip("Chưa có dữ liệu benchmark.")
    events, read = [], baselines._read
    monkeypatch.setattr(baselines, "_read", lambda path: events.append(Path(path).name) or read(path))
    spec = baselines.dataset_spec(dataset)
    runner = baselines._run_time_series if spec["problem_type"] == "time_series" else baselines._run_tabular
    result = runner(method, spec, 0, 5)
    assert events == [Path(spec["train"]).name, Path(spec["test"]).name]
    assert result["fit_seconds"] >= 0 and result["metrics"]["nps"] is not None
