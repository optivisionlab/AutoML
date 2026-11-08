"""
Chỉ số đánh giá ML, viết bằng Python thuần.

Dùng chung cho bộ chấm agent (venv của agent không có numpy/sklearn) và bộ chạy baseline (chạy trong
image backend có sklearn). Định nghĩa bám theo sklearn để kết quả hai bên so được với nhau:

- Phân loại: nhãn dự đoán phải thuộc tập nhãn của test. Precision/recall/F1 lấy trung bình macro trên
  đủ các lớp của test; lớp không được dự đoán lần nào có precision = 0 (như `zero_division=0`).
- ROC-AUC chỉ tính khi có xác suất (baseline có `predict_proba`). API dự đoán của HAutoML chỉ trả nhãn,
  nên với agent chỉ số này để None, không ước lượng thay.
- Hồi quy: MAE, RMSE, R², RMSLE (chỉ khi mọi giá trị > -1), MAPE (chỉ khi mọi giá trị thật > 0).
- NPS như AutoML-Agent (Trirat và cs., ICML 2025, Phụ lục B.4): metric càng cao càng tốt thì giữ
  nguyên; metric sai số s thì NPS = 1 / (1 + s).

Không có hàm nào tự thay giá trị không xác định bằng 0: trả None, hoặc raise khi đầu vào sai.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

CLASSIFICATION, REGRESSION, TIME_SERIES = "classification", "regression", "time_series"
PROBLEM_TYPES = (CLASSIFICATION, REGRESSION, TIME_SERIES)


def _check_pairs(y_true: Sequence, y_pred: Sequence) -> int:
    n = len(y_true)
    if not n or len(y_pred) != n:
        raise ValueError("Test/prediction rỗng hoặc sai số lượng.")
    return n


def _check_finite(values: Iterable[float]) -> None:
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values):
        raise ValueError("Có giá trị NaN/Inf hoặc không phải số.")


# ----------------------------------------------------------------------------- phân loại

def confusion_matrix(y_true: Sequence, y_pred: Sequence, labels: Sequence | None = None) -> dict:
    """{"labels": [...], "matrix": [[...]]} - hàng là nhãn thật, cột là nhãn dự đoán (như sklearn)."""
    _check_pairs(y_true, y_pred)
    labels = list(labels) if labels is not None else sorted(set(y_true) | set(y_pred))
    index = {label: i for i, label in enumerate(labels)}
    matrix = [[0] * len(labels) for _ in labels]
    for t, p in zip(y_true, y_pred):
        matrix[index[t]][index[p]] += 1
    return {"labels": labels, "matrix": matrix}


def _per_class(y_true: Sequence, y_pred: Sequence, labels: Sequence) -> list[dict]:
    rows = []
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        rows.append({"label": label, "precision": precision, "recall": recall, "f1": f1, "support": tp + fn})
    return rows


def f1_macro(y_true: Sequence, y_pred: Sequence) -> float:
    """F1-macro trên tập nhãn của test; lớp không dự đoán được có F1 = 0 (sklearn zero_division=0)."""
    rows = _per_class(y_true, y_pred, sorted(set(y_true)))
    return sum(r["f1"] for r in rows) / len(rows)


def roc_auc(y_true: Sequence, proba: Sequence[Sequence[float]], classes: Sequence) -> float | None:
    """
    ROC-AUC từ xác suất: nhị phân dùng xác suất của lớp thứ hai (như sklearn), đa lớp lấy macro
    one-vs-rest. Lớp nào của test không có cả mẫu dương lẫn âm thì không xác định: trả None.
    """
    classes = list(classes)
    if len(proba) != len(y_true) or any(len(row) != len(classes) for row in proba):
        raise ValueError("Ma trận xác suất sai kích thước.")
    present = sorted(set(y_true))
    if len(present) < 2:
        return None
    targets = [classes[1]] if len(classes) == 2 else present
    scores = []
    for label in targets:
        column = classes.index(label)
        positives = [row[column] for t, row in zip(y_true, proba) if t == label]
        negatives = [row[column] for t, row in zip(y_true, proba) if t != label]
        if not positives or not negatives:
            return None
        scores.append(_mann_whitney_auc(positives, negatives))
    return sum(scores) / len(scores)


def _mann_whitney_auc(positives: list[float], negatives: list[float]) -> float:
    """AUC = P(điểm dương > điểm âm) + 0.5·P(bằng nhau), tính bằng hạng trung bình (O(n log n))."""
    pooled = sorted([(v, 1) for v in positives] + [(v, 0) for v in negatives])
    rank_sum, i = 0.0, 0
    while i < len(pooled):
        j = i
        while j + 1 < len(pooled) and pooled[j + 1][0] == pooled[i][0]:
            j += 1
        average_rank = (i + j) / 2 + 1
        rank_sum += average_rank * sum(1 for k in range(i, j + 1) if pooled[k][1] == 1)
        i = j + 1
    n_pos, n_neg = len(positives), len(negatives)
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def classification_metrics(y_true: Sequence, y_pred: Sequence, proba: Sequence | None = None,
                           classes: Sequence | None = None) -> dict:
    """Đủ bộ chỉ số phân loại. y_pred phải nằm trong tập nhãn của test (bộ chấm kiểm trước)."""
    n = _check_pairs(y_true, y_pred)
    labels = sorted(set(y_true))
    if not set(y_pred) <= set(labels):
        raise RuntimeError("Nhãn dự đoán nằm ngoài tập nhãn test cố định")
    rows = _per_class(y_true, y_pred, labels)
    k = len(rows)
    support = sum(r["support"] for r in rows)
    metrics = {
        "accuracy": sum(t == p for t, p in zip(y_true, y_pred)) / n,
        "balanced_accuracy": sum(r["recall"] for r in rows) / k,
        "precision_macro": sum(r["precision"] for r in rows) / k,
        "recall_macro": sum(r["recall"] for r in rows) / k,
        "f1_macro": sum(r["f1"] for r in rows) / k,
        "f1_weighted": sum(r["f1"] * r["support"] for r in rows) / support,
        "n_classes": k,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels),
        "roc_auc": None,
    }
    if proba is not None and classes is not None:
        metrics["roc_auc"] = roc_auc(y_true, proba, classes)
    metrics["nps"] = metrics["f1_macro"]
    return metrics


# ------------------------------------------------------------------------------ hồi quy

def rmse(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    return math.sqrt(sum((t - p) ** 2 for t, p in zip(y_true, y_pred)) / len(y_true))


def rmsle(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """RMSLE như sklearn mean_squared_log_error (squared=False): chỉ xác định khi mọi giá trị > -1."""
    if not all(v > -1 for v in list(y_true) + list(y_pred)):
        raise ValueError("RMSLE không xác định: có giá trị thật/dự báo <= -1.")
    return math.sqrt(sum((math.log1p(p) - math.log1p(t)) ** 2 for t, p in zip(y_true, y_pred)) / len(y_true))


def regression_metrics(y_true: Sequence[float], y_pred: Sequence[float]) -> dict:
    """
    MAE, RMSE, R², RMSLE, MAPE. `nps` = 1/(1+MAE) (protocol HAutoML từ v4, giữ để so với đợt trước);
    `nps_rmsle` = 1/(1+RMSLE) là cách AutoML-Agent chấm hồi quy bảng - dùng khi đối chiếu với bài báo.
    Dự báo <= -1 làm RMSLE không xác định: đó là lỗi của mô hình nên nps_rmsle = 0 (không bỏ khỏi trung bình).
    """
    n = _check_pairs(y_true, y_pred)
    _check_finite(list(y_true) + list(y_pred))
    mae = sum(abs(t - p) for t, p in zip(y_true, y_pred)) / n
    mean = sum(y_true) / n
    total = sum((t - mean) ** 2 for t in y_true)
    residual = sum((t - p) ** 2 for t, p in zip(y_true, y_pred))
    metrics = {
        "mae": mae,
        "rmse": rmse(y_true, y_pred),
        "r2": 1 - residual / total if total else None,
        "mape": sum(abs(t - p) / t for t, p in zip(y_true, y_pred)) / n if all(t > 0 for t in y_true) else None,
    }
    if all(v > -1 for v in y_true):
        if all(p > -1 for p in y_pred):
            metrics["rmsle"] = rmsle(y_true, y_pred)
            metrics["nps_rmsle"] = 1 / (1 + metrics["rmsle"])
        else:
            metrics.update({"rmsle": None, "rmsle_undefined": True, "nps_rmsle": 0.0})
    else:
        metrics.update({"rmsle": None, "nps_rmsle": None})
    metrics["nps"] = 1 / (1 + mae)
    return metrics


def time_series_metrics(y_true: Sequence[float], y_pred: Sequence[float]) -> dict:
    """Như AutoML-Agent: NPS = 1/(1+RMSLE). Dự báo <= -1 cho chuỗi dương là lỗi mô hình: NPS = 0."""
    metrics = regression_metrics(y_true, y_pred)
    metrics["nps_mae"] = metrics["nps"]
    if metrics.get("nps_rmsle") is None:
        raise ValueError("Chuỗi thời gian có giá trị thật <= -1: RMSLE không xác định (dữ liệu sai protocol).")
    metrics["nps"] = metrics["nps_rmsle"]
    return metrics


def compute(problem_type: str, y_true: Sequence, y_pred: Sequence, proba=None, classes=None) -> dict:
    if problem_type not in PROBLEM_TYPES:
        raise ValueError("Loại bài toán không hợp lệ.")
    if problem_type == CLASSIFICATION:
        _check_pairs(y_true, y_pred)
        _check_finite(list(y_true) + list(y_pred))
        return classification_metrics(y_true, y_pred, proba, classes)
    if problem_type == TIME_SERIES:
        return time_series_metrics(y_true, y_pred)
    return regression_metrics(y_true, y_pred)


# Chỉ số chính theo loại bài toán và hướng tốt hơn - dùng cho bảng so sánh baseline.
PRIMARY = {CLASSIFICATION: ("f1_macro", "higher"), REGRESSION: ("mae", "lower"), TIME_SERIES: ("rmse", "lower")}
LOWER_IS_BETTER = {"mae", "rmse", "rmsle", "mape", "mse"}
