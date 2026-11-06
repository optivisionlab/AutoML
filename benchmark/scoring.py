"""
Chấm mô hình của nhóm C và T trên tập test độc lập (file *_test.csv không bao giờ đi qua LLM).
Nhóm T (time series): dự báo đúng 96 mốc thời gian của phần test, RMSLE như AutoML-Agent.

Gọi predict trực tiếp từ bộ chấm, không qua agent, nên không tính vào token hay
số tool call của agent. Không tự kích hoạt model: model chưa kích hoạt là lỗi
triển khai của agent và phải hiện ra trong SR.
"""

# Standard libraries
import csv
import json
import math
from pathlib import Path

# Local modules (cần src/backend trong sys.path - xem bench.py)
from agent import tools
from agent.api_client import HAutoMLClient

from benchmark.common import REPO, load_json
from benchmark.auth import install_reauthentication
from benchmark.protocol import file_hash
from benchmark.analyze import task_config, _job_matches_task


_BATCH = tools.MAX_PREDICT_ROWS


def _read_test(path: Path, target: str, time_column: str | None = None) -> tuple[list[dict], list[float]]:
    """time_column: cột ngày giờ của time series - giữ nguyên chuỗi (backend dự báo theo mốc thời gian)."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    y_true = [float(row[target]) for row in rows]
    x = [{k: (v if k == time_column else float(v)) for k, v in row.items() if k != target} for row in rows]
    return x, y_true


def _rmse(y_true: list[float], y_pred: list[float]) -> float:
    return math.sqrt(sum((t - p) ** 2 for t, p in zip(y_true, y_pred)) / len(y_true))


def _rmsle(y_true: list[float], y_pred: list[float]) -> float:
    """RMSLE như AutoML-Agent (sklearn mean_squared_log_error): chỉ xác định khi mọi giá trị > -1."""
    if not all(v > -1 for v in y_true + y_pred):
        raise ValueError("RMSLE không xác định: có giá trị thật/dự báo <= -1.")
    return math.sqrt(sum((math.log1p(p) - math.log1p(t)) ** 2 for t, p in zip(y_true, y_pred)) / len(y_true))


def naive_baselines(history: list[float], y_true: list[float]) -> dict:
    """
    Dự báo ngây thơ theo mùa cho chuỗi theo giờ, chỉ từ phần train: lặp lại 24 giờ cuối
    (ngày trước) và 168 giờ cuối (tuần trước). Mốc so sánh, không phải đối thủ được tối ưu.
    """
    result = {}
    for name, period in (("last_day", 24), ("last_week", 168)):
        if len(history) < period:
            continue
        tail = history[-period:]
        forecast = [tail[i % period] for i in range(len(y_true))]
        result[f"naive_{name}_rmse"] = _rmse(y_true, forecast)
        result[f"naive_{name}_rmsle"] = _rmsle(y_true, forecast)
    return result


def f1_macro(y_true: list, y_pred: list) -> float:
    """F1-macro trên đủ tập nhãn của test, nhãn thiếu dự đoán cho 0 (như zero_division=0 của sklearn)."""
    scores = []
    for label in sorted(set(y_true)):
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def compute_metrics(problem_type: str, y_true: list[float], y_pred: list[float]) -> dict:
    n = len(y_true)
    if not n or len(y_pred) != n or not all(math.isfinite(v) for v in y_true + y_pred):
        raise ValueError("Test/prediction rỗng, sai số lượng hoặc chứa NaN/Inf.")
    if problem_type not in {"classification", "regression", "time_series"}:
        raise ValueError("Loại bài toán không hợp lệ.")
    if problem_type == "time_series":
        # AutoML-Agent chấm dự báo bằng RMSLE, NPS = 1/(1+RMSLE); thêm RMSE/MAE (metric engine tính).
        metrics = {"rmse": _rmse(y_true, y_pred), "mae": sum(abs(t - p) for t, p in zip(y_true, y_pred)) / n}
        if all(p > -1 for p in y_pred):
            metrics["rmsle"] = _rmsle(y_true, y_pred)
            metrics["nps"] = 1 / (1 + metrics["rmsle"])
        else:
            # Dự báo <= -1 cho chuỗi dương: lỗi của MÔ HÌNH (không phải của phép đo) - NPS = 0, không loại khỏi trung bình.
            metrics.update({"rmsle": None, "rmsle_undefined": True, "nps": 0.0})
        if all(t > 0 for t in y_true):
            metrics["mape"] = sum(abs(t - p) / t for t, p in zip(y_true, y_pred)) / n
        return metrics
    if problem_type == "classification":
        if not set(y_pred) <= set(y_true):
            raise RuntimeError("Nhãn dự đoán nằm ngoài tập nhãn test cố định")
        f1 = f1_macro(y_true, y_pred)
        return {"accuracy": sum(t == p for t, p in zip(y_true, y_pred)) / n, "f1_macro": f1, "nps": f1}
    mae = sum(abs(t - p) for t, p in zip(y_true, y_pred)) / n
    mean = sum(y_true) / n
    total = sum((t - mean) ** 2 for t in y_true)
    residual = sum((t - p) ** 2 for t, p in zip(y_true, y_pred))
    r2 = 1 - residual / total if total else None
    return {"mae": mae, "r2": r2, "nps": 1 / (1 + mae)}


def _train_series(task: dict) -> list[float]:
    """Chuỗi train của dataset nhóm T (file đã khoá trong manifest_ts) - cho baseline ngây thơ."""
    from benchmark.prepare_ts import MANIFEST, TS_DIR

    meta = load_json(MANIFEST)["datasets"][task["dataset"]]
    with (TS_DIR / meta["files"]["train"]).open(newline="", encoding="utf-8") as f:
        return [float(row[meta["target"]]) for row in csv.DictReader(f)]


def score_run(api, folder: Path, case: dict, cfg: dict) -> str:
    out = folder / "test"
    run = load_json(folder / "run.json")
    task = case["task"]
    test_path = REPO / cfg["test_sets"][task["dataset"]]
    existing = load_json(out / "test_metrics.json")
    if existing:
        if existing.get("test_sha256") != file_hash(test_path) or existing.get("protocol_id") != run.get("protocol_id"):
            raise ValueError("Kết quả test cũ khác dữ liệu/protocol hiện tại.")
        return "đã có"
    jobs = run.get("new_jobs") or []
    if not jobs:
        return "không có job"
    handoff_jobs = list(((run.get("handoff") or {}).get("jobs") or {}))
    job_id = next((j for j in handoff_jobs if j in jobs), jobs[0])
    snapshot = (run.get("job_snapshots") or {}).get(job_id) or {}
    if snapshot.get("status") != 1:
        return "job không thành công"
    if snapshot.get("activate") != 1:
        return "model chưa được agent kích hoạt"
    if _job_matches_task(snapshot, task_config(case, run.get("placeholders") or {})):
        return "job sai yêu cầu; bộ chấm ghi FAIL, không chọn lại model"

    time_column = task.get("time_column") if task["problem_type"] == "time_series" else None
    x, y_true = _read_test(test_path, task["target"], time_column)
    y_pred = []
    for start in range(0, len(x), _BATCH):
        batch = x[start:start + _BATCH]
        result = tools.predict(api, job_id, batch)
        if not result.get("ok"):
            raise RuntimeError(f"{folder.name}: predict lỗi: {result.get('error')}")
        predictions = result.get("predictions") or []
        if len(predictions) != len(batch):
            raise RuntimeError(f"{folder.name}: số dự đoán không khớp số mẫu")
        y_pred.extend(float(item["predict"]) for item in predictions)

    metrics = compute_metrics(task["problem_type"], y_true, y_pred)
    if task["problem_type"] == "time_series":
        metrics.update(naive_baselines(_train_series(task), y_true))
    out.mkdir(exist_ok=True)
    with (out / "test_predictions.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["row", "y_true", "y_pred"])
        writer.writerows((i, a, p) for i, (a, p) in enumerate(zip(y_true, y_pred)))
    metrics.update({"job_id": job_id, "n_test": len(y_true), "score_source": "external_test",
                    "test_sha256": file_hash(test_path), "protocol_id": run.get("protocol_id")})
    (out / "test_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (out / "error.json").unlink(missing_ok=True)
    return "đã chấm"


def score_all(runs_root: Path, cases_doc: dict, cfg: dict, include_pilot: bool) -> None:
    by_id = {c["id"]: c for c in cases_doc["cases"]}
    with HAutoMLClient() as api:
        login = tools.ensure_login(api)
        if not login.get("ok"):
            raise SystemExit(f"Không đăng nhập được: {login.get('error')}")
        install_reauthentication(api)
        for run_file in sorted(runs_root.glob("*/*/run.json")):
            if ".aborted-" in run_file.parent.name or ".invalid-" in run_file.parent.name:
                continue
            run = load_json(run_file)
            case = by_id.get(run["case_id"])
            if not case or case.get("flow") != "train":
                continue
            if run.get("phase") == "pilot" and not include_pilot:
                # Quy trình khoá ngưỡng: không xem điểm test ở lượt chạy thử.
                continue
            try:
                status = score_run(api, run_file.parent, case, cfg)
            except Exception as error:  # noqa: BLE001 - một lượt lỗi không chặn các lượt khác
                status = f"LỖI: {error}"
                out = run_file.parent / "test"
                out.mkdir(exist_ok=True)
                (out / "error.json").write_text(json.dumps({"error": str(error)}, ensure_ascii=False), encoding="utf-8")
            print(f"  {run_file.parent.relative_to(runs_root)}: {status}")
