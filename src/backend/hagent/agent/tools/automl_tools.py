"""
DeerFlow-AutoML Tools — HAutoML API wrappers as LangChain Tools.

Replaces the old CLI-based hautoml_tools.py with proper async LangChain
tools that call the HAutoML REST API directly.

"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ── Config-driven helpers ────────────────────────────────


def _get_base_url() -> str:
    """Lấy HAutoML base URL từ config hautoml.base_url."""
    from hagent.bridge.config import get_hautoml_config
    return get_hautoml_config()["base_url"].rstrip("/")


def _get_timeout() -> int:
    """Lấy timeout từ agent config."""
    from hagent.bridge.config import get_agent_config
    return get_agent_config().get("timeout_seconds", 120)


def _auth_headers(token: str | None = None) -> dict[str, str]:
    """Build auth headers — token từ tham số hoặc env var."""
    import os
    tok = token or os.getenv("USER_TOKEN", "")
    if tok:
        return {"Authorization": f"Bearer {tok}"}
    return {}


# ── Tool result cache ────────────────────────────────────

_cache: dict[str, tuple[float, Any]] = {}


def _get_cache_config() -> dict:
    from hagent.bridge.config import get_cache_config
    return get_cache_config()


def _cache_key(path: str, params: dict | None) -> str:
    return f"{path}:{json.dumps(params or {}, sort_keys=True)}"


def _get_cached(key: str) -> Any | None:
    """Trả về cached result nếu còn hiệu lực."""
    cfg = _get_cache_config()
    if not cfg.get("enabled", False):
        return None
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < cfg.get("ttl_seconds", 300):
        logger.debug("Cache hit: %s", key)
        return entry[1]
    return None


def _set_cache(key: str, value: Any) -> None:
    """Lưu kết quả vào cache."""
    cfg = _get_cache_config()
    if not cfg.get("enabled", False):
        return
    # Evict nếu quá max_entries
    max_entries = cfg.get("max_entries", 100)
    if len(_cache) >= max_entries:
        # Xóa entry cũ nhất
        oldest_key = min(_cache, key=lambda k: _cache[k][0])
        del _cache[oldest_key]
    _cache[key] = (time.time(), value)


# ── HTTP helpers ─────────────────────────────────────────


async def _api_get(
    path: str,
    *,
    params: dict | None = None,
    token: str | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """GET request tới HAutoML API."""
    if use_cache:
        key = _cache_key(path, params)
        cached = _get_cached(key)
        if cached is not None:
            return cached

    url = f"{_get_base_url()}{path}"
    async with httpx.AsyncClient(timeout=_get_timeout()) as client:
        resp = await client.get(url, params=params, headers=_auth_headers(token))
        resp.raise_for_status()
        result = resp.json()

    if use_cache:
        _set_cache(_cache_key(path, params), result)
    return result


async def _api_post(
    path: str,
    *,
    params: dict | None = None,
    data: dict | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """POST request tới HAutoML API (không cache mutations)."""
    url = f"{_get_base_url()}{path}"
    async with httpx.AsyncClient(timeout=_get_timeout()) as client:
        resp = await client.post(url, params=params, json=data, headers=_auth_headers(token))
        resp.raise_for_status()
        return resp.json()


def _result(data: Any) -> str:
    """Serialize kết quả tool thành JSON string."""
    return json.dumps(data, ensure_ascii=False, default=str)


def _error(exc: Exception) -> str:
    """Serialize lỗi thành JSON string."""
    return json.dumps({"error": str(exc)}, ensure_ascii=False)


# ── Dataset Tools ────────────────────────────────────────


@tool
async def list_datasets(user_id: str, token: str | None = None) -> str:
    """Liệt kê tất cả datasets của người dùng.

    Args:
        user_id: ID của người dùng.
        token: JWT token (tùy chọn, sẽ lấy từ env nếu không truyền).

    Returns:
        Danh sách datasets dạng JSON string.
    """
    try:
        result = await _api_post(
            "/get-list-data-by-userid",
            params={"id": user_id},
            token=token,
        )
        return _result(result)
    except Exception as exc:
        return _error(exc)


@tool
async def get_dataset_info(dataset_id: str, token: str | None = None) -> str:
    """Lấy thông tin chi tiết về một dataset.

    Args:
        dataset_id: ID của dataset cần xem.
        token: JWT token (tùy chọn).

    Returns:
        Thông tin dataset dạng JSON string (features, target, statistics).
    """
    try:
        result = await _api_get(
            "/get-data-info",
            params={"id": dataset_id},
            token=token,
        )
        return _result(result)
    except Exception as exc:
        return _error(exc)


@tool
async def get_available_models(problem_type: str) -> str:
    """Lấy danh sách thuật toán ML khả dụng cho loại bài toán.

    Args:
        problem_type: Loại bài toán — 'classification' hoặc 'regression'.

    Returns:
        Danh sách models, metrics, và hyperparameters dạng JSON string.
    """
    try:
        result = await _api_get(f"/api/v1/available-models/{problem_type}")
        return _result(result)
    except Exception as exc:
        return _error(exc)


@tool
async def start_training(
    user_id: str,
    dataset_id: str,
    problem_type: str,
    target_column: str,
    models: list[str] | None = None,
    metric: str | None = None,
    time_limit: int = 300,
    token: str | None = None,
) -> str:
    """Khởi tạo một job training AutoML.

    Args:
        user_id: ID người dùng.
        dataset_id: ID dataset để train.
        problem_type: 'classification' hoặc 'regression'.
        target_column: Tên cột mục tiêu (target/label).
        models: Danh sách tên model muốn thử (None = dùng tất cả).
        metric: Metric đánh giá (None = dùng mặc định).
        time_limit: Giới hạn thời gian (giây), mặc định 300s.
        token: JWT token (tùy chọn).

    Returns:
        Thông tin job đã tạo (bao gồm job_id) dạng JSON string.
    """
    try:
        training_item: dict[str, Any] = {
            "problem_type": problem_type,
            "target_column": target_column,
            "time_limit": time_limit,
        }
        if models:
            training_item["models"] = models
        if metric:
            training_item["metric"] = metric

        result = await _api_post(
            "/train-from-requestbody-json/",
            params={"userId": user_id, "id_data": dataset_id},
            data=training_item,
            token=token,
        )
        return _result(result)
    except Exception as exc:
        return _error(exc)


@tool
async def get_job_info(job_id: str, token: str | None = None) -> str:
    """Lấy trạng thái và kết quả của một training job.

    Args:
        job_id: ID của job cần kiểm tra.
        token: JWT token (tùy chọn).

    Returns:
        Thông tin job (status, best_model, best_score, metrics) dạng JSON string.
    """
    try:
        result = await _api_post(
            "/get-job-info",
            params={"id": job_id},
            token=token,
        )
        return _result(result)
    except Exception as exc:
        return _error(exc)


@tool
async def list_jobs(user_id: str, token: str | None = None) -> str:
    """Liệt kê tất cả training jobs của người dùng.

    Args:
        user_id: ID người dùng.
        token: JWT token (tùy chọn).

    Returns:
        Danh sách jobs dạng JSON string.
    """
    try:
        result = await _api_post(
            "/get-list-job-by-userId",
            params={"user_id": user_id},
            token=token,
        )
        return _result(result)
    except Exception as exc:
        return _error(exc)


@tool
async def check_system_health() -> str:
    """Kiểm tra trạng thái hệ thống HAutoML.

    Returns:
        Thông tin health check dạng JSON string.
    """
    try:
        result = await _api_get("/home", use_cache=False)
        return _result({"status": "ok", **result})
    except Exception as exc:
        return _result({"status": "error", "error": str(exc)})


# ── Tool registry ────────────────────────────────────────

ALL_TOOLS = [
    list_datasets,
    get_dataset_info,
    get_available_models,
    start_training,
    get_job_info,
    list_jobs,
    check_system_health,
]

DATASET_TOOLS = [list_datasets, get_dataset_info]
TRAINING_TOOLS = [start_training, get_job_info, list_jobs]
MODEL_TOOLS = [get_available_models]
SYSTEM_TOOLS = [check_system_health]
