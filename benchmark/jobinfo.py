"""
Đọc bằng chứng về quá trình train từ pipeline JSON của backend (GET /inference/jobs/{id}).

Pipeline (src/backend/src/modules/trainings/pipeline.py) ghi trạng thái, thời điểm bắt đầu/kết thúc
từng bước (độ phân giải 1 giây) và các trial của từng model. Từ đó đo được: thời gian huấn luyện thật
của engine, số cấu hình HPO đã đánh giá (trial khác tham số), số model lỗi, nguồn điểm (cv/holdout).
Không có trong backend: CPU/RAM của worker, thời gian fit từng trial (bị bỏ khi lưu) - báo là chưa đo.
"""

from __future__ import annotations

from datetime import datetime

_NODES = ("read_dataset", "split_holdout_data", "preprocessing", "model_selection", "train", "select_best", "save_result")


def _instant(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _seconds(start, end) -> float | None:
    a, b = _instant(start), _instant(end)
    return (b - a).total_seconds() if a and b else None


def pipeline_summary(pipeline: dict | None) -> dict | None:
    """Tóm tắt gọn (không chép toàn bộ trial) để lưu vào run.json."""
    if not isinstance(pipeline, dict):
        return None
    nodes = {k: pipeline.get(k) or {} for k in _NODES}
    models = ((nodes["train"].get("output") or {}).get("models")) or {}
    per_model = {}
    for name, info in models.items():
        trials = (info or {}).get("trials") or []
        per_model[name] = {
            "status": (info or {}).get("status"),
            "trials": len(trials),
            "pruned": sum(1 for t in trials if (t or {}).get("status") == "pruned"),
        }
    first = next((nodes[k].get("started_at") for k in _NODES if nodes[k].get("started_at")), None)
    last = next((nodes[k].get("finished_at") for k in reversed(_NODES) if nodes[k].get("finished_at")), None)
    split = nodes["split_holdout_data"].get("output") or {}
    return {
        "status": pipeline.get("status"),
        "score_source": (nodes["select_best"].get("output") or {}).get("score_source"),
        "best_model": (nodes["select_best"].get("output") or {}).get("best_model"),
        "train_rows": split.get("train_rows"),
        "holdout_rows": split.get("holdout_rows"),
        "n_features": (nodes["preprocessing"].get("output") or {}).get("n_features"),
        "models": per_model,
        "models_failed": sum(1 for m in per_model.values() if m["status"] == "failed"),
        "candidates_evaluated": sum(m["trials"] for m in per_model.values()),
        "node_seconds": {k: _seconds(nodes[k].get("started_at"), nodes[k].get("finished_at")) for k in _NODES},
        "training_seconds": _seconds(nodes["train"].get("started_at"), nodes["train"].get("finished_at")),
        "pipeline_seconds": _seconds(first, last),
        "cv": (nodes["model_selection"].get("params") or {}).get("cv"),
    }


def fetch_summary(api, job_id: str) -> dict:
    """Đọc pipeline của job (chỉ gọi cho job đã xác nhận là của tài khoản benchmark). Lỗi thì ghi lỗi, không raise."""
    try:
        return pipeline_summary(api.get_job_pipeline(job_id)) or {"error": "pipeline rỗng"}
    except Exception as error:  # noqa: BLE001 - thiếu bằng chứng phụ không được làm hỏng lượt đo
        return {"error": f"{type(error).__name__}: {error}"}
