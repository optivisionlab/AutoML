"""
Baseline ngoài agent, chạy offline trên CÙNG split train/test đã khoá trong manifest.

Mục đích: đặt kết quả của agent HAutoML cạnh các cách giải không dùng LLM, trên cùng dữ liệu, cùng
metric, cùng máy - để biết agent hơn/kém cái gì và tốn thêm bao nhiêu.

Nhóm baseline (không coi chúng tương đương chức năng với agent):
- Naive: `dummy` (lớp phổ biến / trung bình), time series `naive_last_day`, `naive_last_week`.
- Mô hình cố định, không tối ưu: `linear` (LogisticRegression / Ridge có chuẩn hoá), `random_forest`, `xgboost`;
  time series `lag_ridge`, `lag_gbr` (đặc trưng trễ 1,2,3,24,48,168 + giờ/thứ, dự báo đệ quy 96 bước).
- Tối ưu tự động có ngân sách thời gian: `optuna_tpe` (TPE trên RF / XGBoost / tuyến tính, CV 5 fold CHỈ trên
  train, cùng metric chọn model với ca agent, cùng ngân sách `--budget` giây như max_time của agent).
- Tuỳ chọn, chỉ chạy khi đã cài: `flaml`, `autogluon` (AutoML-Agent dùng AutoGluon làm baseline). Chưa cài
  thì ghi status "unavailable" - không tự cài, không giả kết quả.
- `hautoml_engine` (engine HAutoML gọi thẳng với config đúng, không LLM) nằm ở engine_baseline.py.

Chống rò rỉ: test chỉ được đọc SAU khi model đã fit xong, chỉ để chấm; mọi tiền xử lý / chọn siêu tham số
nằm trong Pipeline / CV trên train. Mỗi (method, dataset, seed) chạy trong tiến trình con riêng: lỗi hay
quá giờ của một lượt không làm hỏng lượt khác, và đo được CPU / RAM đỉnh của riêng lượt đó.

Chạy (image backend có sklearn/xgboost/optuna đúng phiên bản của engine; không cần mạng):

    docker run --rm --network none --user "$(id -u):$(id -g)" -v "$PWD":/repo -w /repo \\
        hautoml-backend-test:local python -I benchmark/baselines.py --mode smoke

Kết quả: benchmark_artifacts/baselines/<id>/<method>/<dataset>_s<seed>/{metrics.json,predictions.csv}
và baselines_manifest.json (môi trường, hash dữ liệu/code, ngân sách). Không ghi đè kết quả đã có.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import multiprocessing
import os
import platform
import resource
import sys
import time
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from benchmark import metrics as M  # noqa: E402
from benchmark.common import ARTIFACTS, load_json  # noqa: E402

TABULAR = ("glass", "shopping", "concrete", "crab")
TIME_SERIES = ("electricity", "weather")
TABULAR_METHODS = ("dummy", "linear", "random_forest", "xgboost", "optuna_tpe", "flaml", "autogluon")
TS_METHODS = ("naive_last_day", "naive_last_week", "lag_ridge", "lag_gbr")
# Metric chọn model của ca agent tương ứng (C01-C03, C09, T01/T03): baseline tối ưu đúng metric đó.
SELECTION_METRIC = {"classification": "f1_macro", "regression": "mae", "time_series": "rmse"}
MODES = {
    "smoke": {"seeds": [0], "budget": 20, "methods": None},
    "full": {"seeds": [0, 1, 2, 3, 4], "budget": 300, "methods": None},
}
HORIZON = 96
LAGS = (1, 2, 3, 24, 48, 168)


# ----------------------------------------------------------------------------- dữ liệu

def dataset_spec(name: str) -> dict:
    """Đường dẫn + target + feature của split đã khoá; kiểm hash trước khi dùng."""
    from benchmark import protocol

    if name in TABULAR:
        manifest = protocol.check_data()
        meta = manifest[name]
        directory = ARTIFACTS / "datasets"
        return {"name": name, "problem_type": "classification" if name in ("glass", "shopping") else "regression",
                "train": directory / f"{name}_train.csv", "test": directory / f"{name}_test.csv",
                "target": meta["target"], "features": meta["features"]}
    if name in TIME_SERIES:
        from benchmark.prepare_ts import MANIFEST, TS_DIR
        protocol.check_ts_data()
        meta = load_json(MANIFEST)["datasets"][name]
        return {"name": name, "problem_type": "time_series", "train": TS_DIR / meta["files"]["train"],
                "test": TS_DIR / meta["files"]["test"], "target": meta["target"], "time_column": meta["time_column"]}
    raise ValueError(f"Dataset không có: {name}")


def _read(path: Path):
    import pandas as pd
    return pd.read_csv(path)


# --------------------------------------------------------------------------- mô hình bảng

def _estimator(method: str, problem_type: str, seed: int, params: dict | None = None):
    from sklearn.dummy import DummyClassifier, DummyRegressor
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    params = params or {}
    classify = problem_type == "classification"
    if method == "dummy":
        return DummyClassifier(strategy="prior") if classify else DummyRegressor(strategy="mean")
    if method == "linear":
        model = (LogisticRegression(max_iter=5000, random_state=seed, **params) if classify
                 else Ridge(**params))
        return make_pipeline(StandardScaler(), model)
    if method == "random_forest":
        cls = RandomForestClassifier if classify else RandomForestRegressor
        return cls(**{"n_estimators": 300, **params}, random_state=seed, n_jobs=1)
    if method == "xgboost":
        from xgboost import XGBClassifier, XGBRegressor
        cls = XGBClassifier if classify else XGBRegressor
        return cls(**params, random_state=seed, n_jobs=1, verbosity=0)
    raise ValueError(method)


class _Encoded:
    """Bọc mô hình cần nhãn 0..k-1 (XGBoost): mã hoá nhãn khi fit, giải mã khi predict."""

    def __init__(self, model) -> None:
        from sklearn.preprocessing import LabelEncoder
        self.model, self.encoder = model, LabelEncoder()

    def fit(self, x, y):
        self.model.fit(x, self.encoder.fit_transform(y))
        self.classes_ = self.encoder.classes_
        return self

    def predict(self, x):
        return self.encoder.inverse_transform(self.model.predict(x).astype(int))

    def predict_proba(self, x):
        return self.model.predict_proba(x)


def _build(method: str, problem_type: str, seed: int, params: dict | None = None):
    model = _estimator(method, problem_type, seed, params)
    return _Encoded(model) if method == "xgboost" and problem_type == "classification" else model


def _cv_score(model_factory, x, y, problem_type: str, seed: int) -> float:
    """Điểm CV 5 fold trên TRAIN theo metric chọn model (cao hơn = tốt hơn: MAE đổi dấu)."""
    from sklearn.model_selection import KFold, StratifiedKFold

    if problem_type == "classification":
        counts = y.value_counts()
        splits = max(2, min(5, int(counts.min())))
        folds = StratifiedKFold(n_splits=splits, shuffle=True, random_state=seed)
    else:
        folds = KFold(n_splits=5, shuffle=True, random_state=seed)
    scores = []
    for train_idx, valid_idx in folds.split(x, y):
        model = model_factory()
        model.fit(x.iloc[train_idx], y.iloc[train_idx])
        pred = model.predict(x.iloc[valid_idx])
        truth = [float(v) for v in y.iloc[valid_idx]]
        pred = [float(v) for v in pred]
        if problem_type == "classification":
            scores.append(M.f1_macro(truth, pred))
        else:
            scores.append(-sum(abs(a - b) for a, b in zip(truth, pred)) / len(truth))
    return sum(scores) / len(scores)


def _optuna_search(x, y, problem_type: str, seed: int, budget: float) -> tuple[object, dict]:
    """TPE trên 3 họ mô hình; dừng theo thời gian (timeout = budget giây) - tương tự max_time của agent."""
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    classify = problem_type == "classification"

    def suggest(trial) -> tuple[str, dict]:
        family = trial.suggest_categorical("family", ["random_forest", "xgboost", "linear"])
        if family == "random_forest":
            return family, {"n_estimators": trial.suggest_int("rf_n_estimators", 100, 500, step=50),
                            "max_depth": trial.suggest_int("rf_max_depth", 3, 30),
                            "min_samples_leaf": trial.suggest_int("rf_min_samples_leaf", 1, 10),
                            "max_features": trial.suggest_categorical("rf_max_features", ["sqrt", "log2", 1.0])}
        if family == "xgboost":
            return family, {"n_estimators": trial.suggest_int("xgb_n_estimators", 100, 600, step=50),
                            "max_depth": trial.suggest_int("xgb_max_depth", 2, 10),
                            "learning_rate": trial.suggest_float("xgb_learning_rate", 0.01, 0.3, log=True),
                            "subsample": trial.suggest_float("xgb_subsample", 0.5, 1.0),
                            "colsample_bytree": trial.suggest_float("xgb_colsample_bytree", 0.5, 1.0),
                            "reg_lambda": trial.suggest_float("xgb_reg_lambda", 1e-3, 10.0, log=True)}
        key = "C" if classify else "alpha"
        return family, {key: trial.suggest_float(f"linear_{key}", 1e-3, 1e3, log=True)}

    def objective(trial) -> float:
        family, params = suggest(trial)
        return _cv_score(lambda: _build(family, problem_type, seed, params), x, y, problem_type, seed)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed))
    started = time.monotonic()
    study.optimize(objective, timeout=budget, n_trials=10_000, catch=(ValueError,))
    trial = study.best_trial
    family, params = suggest(optuna.trial.FixedTrial(trial.params))
    model = _build(family, problem_type, seed, params).fit(x, y)
    return model, {"family": family, "params": params, "cv_score": trial.value, "n_trials": len(study.trials),
                   "search_seconds": time.monotonic() - started}


def _run_tabular(method: str, spec: dict, seed: int, budget: float) -> dict:
    train, info = _read(spec["train"]), {}
    x, y = train[spec["features"]], train[spec["target"]]
    problem_type = spec["problem_type"]
    started = time.monotonic()
    if method == "optuna_tpe":
        model, info = _optuna_search(x, y, problem_type, seed, budget)
    elif method == "flaml":
        from flaml import AutoML
        model = AutoML()
        metric = "macro_f1" if problem_type == "classification" else "mae"
        model.fit(x, y, task=problem_type, metric=metric, time_budget=budget, seed=seed, n_jobs=1, verbose=0)
        info = {"best_estimator": model.best_estimator}
    elif method == "autogluon":
        import tempfile
        from autogluon.tabular import TabularPredictor
        metric = "f1_macro" if problem_type == "classification" else "mean_absolute_error"
        model = TabularPredictor(label=spec["target"], eval_metric=metric, path=tempfile.mkdtemp(), verbosity=0)
        model.fit(train, time_limit=budget, presets="medium_quality")
        info = {"note": "AutoGluon không nhận seed toàn cục; lặp lại chỉ đo biến thiên tự nhiên."}
    else:
        model = _build(method, problem_type, seed).fit(x, y)
    fit_seconds = time.monotonic() - started

    # Chỉ từ đây mới đọc test - để chấm.
    test = _read(spec["test"])
    started = time.monotonic()
    x_test = test[spec["features"]]
    y_pred = [float(v) for v in model.predict(x_test)]
    predict_seconds = time.monotonic() - started
    y_true = [float(v) for v in test[spec["target"]]]
    proba = classes = None
    if problem_type == "classification" and hasattr(model, "predict_proba"):
        try:
            raw = model.predict_proba(x_test)
            proba = [[float(p) for p in row] for row in (raw.values if hasattr(raw, "values") else raw)]
            classes = [float(c) for c in (getattr(model, "classes_", None) if getattr(model, "classes_", None) is not None
                                          else raw.columns)]
        except Exception:  # noqa: BLE001 - thiếu xác suất thì AUC để None, không đoán
            proba = classes = None
    metrics = M.compute(problem_type, y_true, y_pred, proba, classes)
    return {"metrics": metrics, "fit_seconds": fit_seconds, "predict_seconds": predict_seconds, "info": info,
            "y_true": y_true, "y_pred": y_pred}


# ------------------------------------------------------------------------- time series

def _lag_features(history: list[float], stamps: list, index: int) -> list[float]:
    stamp = stamps[index]
    return [history[index - lag] for lag in LAGS] + [float(stamp.hour), float(stamp.dayofweek)]


def _run_time_series(method: str, spec: dict, seed: int, budget: float) -> dict:
    import pandas as pd

    train = _read(spec["train"])
    series = [float(v) for v in train[spec["target"]]]
    stamps = list(pd.to_datetime(train[spec["time_column"]]))
    started = time.monotonic()
    info: dict = {}
    if method in ("naive_last_day", "naive_last_week"):
        period = 24 if method == "naive_last_day" else 168
        tail = series[-period:]
        forecast = [tail[i % period] for i in range(HORIZON)]
        fit_seconds = time.monotonic() - started
    else:
        from sklearn.ensemble import HistGradientBoostingRegressor
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        start = max(LAGS)
        x = [_lag_features(series, stamps, i) for i in range(start, len(series))]
        y = series[start:]
        model = (make_pipeline(StandardScaler(), Ridge(alpha=1.0)) if method == "lag_ridge"
                 else HistGradientBoostingRegressor(random_state=seed))
        model.fit(x, y)
        fit_seconds = time.monotonic() - started
        # Dự báo đệ quy: mỗi bước dùng chính dự báo trước làm lịch sử (như TimeSeriesForecaster của engine).
        history, future = list(series), list(stamps)
        step = future[-1] - future[-2]
        for _ in range(HORIZON):
            future.append(future[-1] + step)
            history.append(float(model.predict([_lag_features(history, future, len(history))])[0]))
        forecast = history[len(series):]
        info = {"lags": list(LAGS), "calendar": ["hour", "dayofweek"], "train_rows": len(y)}
    test = _read(spec["test"])
    y_true = [float(v) for v in test[spec["target"]]]
    if len(y_true) != HORIZON:
        raise ValueError(f"Test time series phải có {HORIZON} bước, có {len(y_true)}.")
    metrics = M.compute("time_series", y_true, forecast)
    return {"metrics": metrics, "fit_seconds": fit_seconds, "predict_seconds": 0.0, "info": info,
            "y_true": y_true, "y_pred": forecast}


# --------------------------------------------------------------------- tiến trình con

def _child(method: str, dataset: str, seed: int, budget: float, queue) -> None:
    try:
        import random
        random.seed(seed)
        try:
            import numpy
            numpy.random.seed(seed)
        except ImportError:
            pass
        spec = dataset_spec(dataset)
        runner = _run_time_series if spec["problem_type"] == "time_series" else _run_tabular
        result = runner(method, spec, seed, budget)
        result["status"] = "ok"
    except ImportError as error:
        result = {"status": "unavailable", "error": f"{type(error).__name__}: {error}"}
    except Exception as error:  # noqa: BLE001 - một lượt lỗi được ghi lại, không chặn lượt khác
        result = {"status": "error", "error": f"{type(error).__name__}: {error}", "traceback": traceback.format_exc()[-4000:]}
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result["cpu_seconds"] = usage.ru_utime + usage.ru_stime
    result["peak_rss_mb"] = usage.ru_maxrss / 1024
    queue.put(result)


def run_one(method: str, dataset: str, seed: int, budget: float, timeout: float) -> dict:
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=_child, args=(method, dataset, seed, budget, queue))
    started = time.monotonic()
    process.start()
    result = None
    try:
        result = queue.get(timeout=timeout)
    except Exception:  # noqa: BLE001 - queue.Empty khi quá giờ
        result = {"status": "timeout", "error": f"Quá {timeout:.0f} giây, tiến trình bị dừng."}
    finally:
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join()
    result["wall_seconds"] = time.monotonic() - started
    return result


# ---------------------------------------------------------------------- manifest + CLI

def _file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def environment() -> dict:
    versions = {}
    for module in ("sklearn", "xgboost", "optuna", "pandas", "numpy", "flaml", "autogluon"):
        try:
            versions[module] = __import__(module).__version__
        except Exception:  # noqa: BLE001
            versions[module] = None
    return {"python": sys.version.split()[0], "platform": platform.platform(), "cpu_count": os.cpu_count(),
            "processor": platform.processor() or None, "libraries": versions}


def build_manifest(baseline_id: str, mode: str, methods: list[str], datasets: list[str], seeds: list[int],
                   budget: float) -> dict:
    from benchmark import protocol
    data = protocol.check_data()
    ts = protocol.check_ts_data()
    return {
        "baseline_id": baseline_id, "mode": mode, "methods": methods, "datasets": datasets, "seeds": seeds,
        "time_budget_seconds": budget, "selection_metric": SELECTION_METRIC,
        "data_sha256": {**data["sha256"], **ts["sha256"]},
        "code_sha256": {name: _file_hash(Path(__file__).with_name(name)) for name in ("baselines.py", "metrics.py")},
        "protocol": ("Split cố định của manifest (feature-group-v1 / time-holdout-v1); chọn mô hình chỉ bằng CV trên "
                     "train; test chỉ đọc sau khi fit để chấm. n_jobs=1 cho mọi mô hình."),
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Baseline ngoài agent trên split benchmark đã khoá (không gọi LLM).")
    parser.add_argument("--mode", choices=sorted(MODES), default="smoke")
    parser.add_argument("--id", help="Mã đợt baseline (thư mục kết quả); mặc định baselines-<mode>")
    parser.add_argument("--methods", help="Danh sách method, vd dummy,linear,optuna_tpe")
    parser.add_argument("--datasets", help="Danh sách dataset, vd glass,crab,electricity")
    parser.add_argument("--seeds", help="Danh sách seed, vd 0,1,2")
    parser.add_argument("--budget", type=float, help="Ngân sách thời gian (giây) cho method tối ưu tự động")
    args = parser.parse_args(argv)

    preset = MODES[args.mode]
    baseline_id = args.id or f"baselines-{args.mode}"
    datasets = args.datasets.split(",") if args.datasets else list(TABULAR + TIME_SERIES)
    methods = args.methods.split(",") if args.methods else list(TABULAR_METHODS + TS_METHODS)
    seeds = [int(s) for s in args.seeds.split(",")] if args.seeds else preset["seeds"]
    budget = args.budget if args.budget is not None else preset["budget"]
    unknown = sorted(set(datasets) - set(TABULAR + TIME_SERIES)) + sorted(set(methods) - set(TABULAR_METHODS + TS_METHODS))
    if unknown:
        raise SystemExit(f"Không có: {unknown}")

    root = ARTIFACTS / "baselines" / baseline_id
    manifest = build_manifest(baseline_id, args.mode, methods, datasets, seeds, budget)
    existing = load_json(root / "baselines_manifest.json")
    if existing:
        locked = {k: existing.get(k) for k in ("time_budget_seconds", "data_sha256", "code_sha256", "selection_metric")}
        if locked != {k: manifest[k] for k in locked}:
            raise SystemExit(f"{root} đã có kết quả với ngân sách/dữ liệu/code khác. Dùng --id mới.")
        # Thêm method/dataset/seed vào đợt cũ được, giữ hợp các danh sách.
        for key in ("methods", "datasets", "seeds"):
            manifest[key] = sorted(set(existing.get(key) or []) | set(manifest[key]), key=str)
    root.mkdir(parents=True, exist_ok=True)
    manifest["environment"] = existing.get("environment") if existing else environment()
    (root / "baselines_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    timeout = budget * 3 + 180
    for dataset in datasets:
        valid = TS_METHODS if dataset in TIME_SERIES else TABULAR_METHODS
        for method in [m for m in methods if m in valid]:
            for seed in seeds:
                out = root / method / f"{dataset}_s{seed:02d}"
                if (out / "metrics.json").exists():
                    print(f"  = {method}/{dataset} seed {seed}: đã có, bỏ qua")
                    continue
                result = run_one(method, dataset, seed, budget, timeout)
                out.mkdir(parents=True, exist_ok=True)
                y_true, y_pred = result.pop("y_true", None), result.pop("y_pred", None)
                if y_true is not None:
                    with (out / "predictions.csv").open("w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow(["row", "y_true", "y_pred"])
                        writer.writerows((i, a, p) for i, (a, p) in enumerate(zip(y_true, y_pred)))
                record = {"method": method, "dataset": dataset, "seed": seed, "baseline_id": baseline_id,
                          "time_budget_seconds": budget, **result}
                (out / "metrics.json").write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
                primary = (result.get("metrics") or {})
                shown = {k: round(primary[k], 4) for k in ("f1_macro", "accuracy", "mae", "rmse", "nps") if isinstance(primary.get(k), float)}
                print(f"  ▶ {method}/{dataset} seed {seed}: {result['status']} {shown} ({result['wall_seconds']:.1f}s)")


if __name__ == "__main__":
    main()
