"""
Chấm mô hình của nhóm C và T trên tập test độc lập (file *_test.csv không bao giờ đi qua LLM).
Nhóm T (time series): dự báo đúng 96 mốc thời gian của phần test, RMSLE như AutoML-Agent.

Gọi predict trực tiếp từ bộ chấm, không qua agent, nên không tính vào token hay
số tool call của agent.

Từ v5: job đúng yêu cầu, train xong nhưng agent không kích hoạt thì bộ chấm BẬT TẠM model để đo chất lượng
rồi tắt lại (`activated_by_scorer`). Lỗi triển khai vẫn nằm nguyên trong SR (0.5 / 0.25, chỉ xét snapshot lúc
chạy và lời gọi predict của agent) - như AutoML-Agent: NPS đo khi có model chạy được, SR đo mức triển khai.
Không đo thì lượt đó mất NPS khỏi trung bình, làm biến thể hay quên kích hoạt trông tốt hơn.
"""

# Standard libraries
import csv
import json
import math
from pathlib import Path

# Local modules (cần src/backend trong sys.path - xem bench.py)
from agent import tools
from agent.api_client import HAutoMLClient

from benchmark import metrics as metrics_module
from benchmark.common import REPO, load_json
from benchmark.auth import install_reauthentication
from benchmark.protocol import file_hash
from benchmark.analyze import task_config, _job_matches_task


_BATCH = tools.MAX_PREDICT_ROWS


def _read_test(path: Path, target: str, time_column: str | None = None,
               column_case: str | None = None) -> tuple[list[dict], list[float]]:
    """
    time_column: cột ngày giờ của time series - giữ nguyên chuỗi (backend dự báo theo mốc thời gian).
    column_case="lower": dataset nhập từ PostgreSQL có tên cột chữ thường (S06) - đổi tên cột của test cho
    khớp, không đổi giá trị.
    """
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if column_case == "lower":
        rows = [{k.lower(): v for k, v in row.items()} for row in rows]
    y_true = [float(row[target]) for row in rows]
    x = [{k: (v if k == time_column else float(v)) for k, v in row.items() if k != target} for row in rows]
    return x, y_true


def _rmse(y_true: list[float], y_pred: list[float]) -> float:
    return metrics_module.rmse(y_true, y_pred)


def _rmsle(y_true: list[float], y_pred: list[float]) -> float:
    """RMSLE như AutoML-Agent (sklearn mean_squared_log_error): chỉ xác định khi mọi giá trị > -1."""
    return metrics_module.rmsle(y_true, y_pred)


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
    return metrics_module.f1_macro(y_true, y_pred)


def compute_metrics(problem_type: str, y_true: list[float], y_pred: list[float]) -> dict:
    """
    Đủ bộ chỉ số trên test (benchmark/metrics.py). `nps` giữ đúng định nghĩa protocol v4 (F1-macro;
    1/(1+MAE) cho hồi quy; 1/(1+RMSLE) cho time series); thêm `nps_rmsle` cho hồi quy để đối chiếu bài báo.
    API HAutoML chỉ trả nhãn nên không có ROC-AUC cho agent.
    """
    return metrics_module.compute(problem_type, y_true, y_pred)


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
    if _job_matches_task(snapshot, task_config(case, run.get("placeholders") or {})):
        return "job sai yêu cầu; bộ chấm ghi FAIL, không chọn lại model"
    current = tools.get_job_info(api, job_id)
    if not current.get("ok"):
        raise RuntimeError(f"{folder.name}: không đọc được job {job_id}: {current.get('error')}")
    out.mkdir(exist_ok=True)
    # Dấu "bộ chấm đã bật tạm" ghi TRƯỚC khi bật: lần chấm trước bật mà chưa tắt lại được thì lần này biết đó
    # không phải trạng thái agent để lại, và phải tắt.
    marker_path = out / "scorer_activation.json"
    marker = load_json(marker_path) or {}
    left_on_by_scorer = marker.get("job_id") == job_id and marker.get("activated") and not marker.get("restored")
    agent_active = (current.get("job") or {}).get("activate") == 1 and not left_on_by_scorer
    activated_by_scorer = not agent_active
    if activated_by_scorer:
        marker_path.write_text(json.dumps({"job_id": job_id, "activated": True, "restored": False}), encoding="utf-8")
        if (current.get("job") or {}).get("activate") != 1:
            result = tools.activate_model(api, job_id, True)
            if not result.get("ok"):
                raise RuntimeError(f"{folder.name}: không bật tạm được model để chấm: {result.get('error')}")
    restored = None
    try:
        metrics = _predict_and_measure(api, folder, job_id, task, test_path)
    finally:
        if activated_by_scorer:
            # Trả model về đúng trạng thái agent để lại.
            restored = bool(tools.activate_model(api, job_id, False).get("ok"))
            marker_path.write_text(json.dumps({"job_id": job_id, "activated": True, "restored": restored}),
                                   encoding="utf-8")
    if activated_by_scorer and not restored:
        # Không lưu kết quả: chạy lại `score` sẽ đo lại và thử tắt lại (dấu cho biết model đang bật là do bộ chấm).
        raise RuntimeError(f"{folder.name}: đã chấm nhưng KHÔNG tắt lại được model job {job_id} - chạy lại score.")
    metrics["activated_by_scorer"] = activated_by_scorer
    y_true, y_pred = metrics.pop("_y_true"), metrics.pop("_y_pred")
    marker_path.unlink(missing_ok=True)
    with (out / "test_predictions.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["row", "y_true", "y_pred"])
        writer.writerows((i, a, p) for i, (a, p) in enumerate(zip(y_true, y_pred)))
    metrics.update({"job_id": job_id, "n_test": len(y_true), "score_source": "external_test",
                    "test_sha256": file_hash(test_path), "protocol_id": run.get("protocol_id")})
    (out / "test_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (out / "error.json").unlink(missing_ok=True)
    return "đã chấm" + (" (bộ chấm bật tạm model)" if activated_by_scorer else "")


def _predict_and_measure(api, folder: Path, job_id: str, task: dict, test_path: Path) -> dict:
    time_column = task.get("time_column") if task["problem_type"] == "time_series" else None
    x, y_true = _read_test(test_path, task["target"], time_column, task.get("column_case"))
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
    metrics["_y_true"], metrics["_y_pred"] = y_true, y_pred
    return metrics


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
