#!/usr/bin/env python3
"""
HAutoML Tools — CLI để HAgent tương tác với HAutoML REST API.

Script này được HAgent thực thi qua lệnh hệ thống.
Mỗi subcommand tương ứng với một HAutoML API endpoint.
KHÔNG có logic ML nào ở đây — chỉ gọi API và trả kết quả.

Cách dùng:
    python hautoml_tools.py <lệnh> [tùy chọn]
"""

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
    import httpx
except ImportError:
    httpx = None


HAUTOML_BASE_URL = os.getenv("HAUTOML_BASE_URL", "http://localhost:8080")
TOKEN_FALLBACK_FILE = os.getenv("HAGENT_USER_TOKEN_FILE", "/tmp/hagent_user_token")
USER_ID_FALLBACK_FILE = os.getenv("HAGENT_USER_ID_FILE", "/tmp/hagent_user_id")


class _MaxLevelFilter(logging.Filter):
    def __init__(self, max_level: int):
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno <= self.max_level


logger = logging.getLogger("hautoml_tools")
if not logger.handlers:
    logger.setLevel(logging.INFO)

    info_handler = logging.StreamHandler(sys.stdout)
    info_handler.setLevel(logging.DEBUG)
    info_handler.addFilter(_MaxLevelFilter(logging.WARNING))
    info_handler.setFormatter(logging.Formatter("%(message)s"))

    error_handler = logging.StreamHandler(sys.stderr)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(info_handler)
    logger.addHandler(error_handler)
    logger.propagate = False


class SimpleResponse:
    def __init__(self, status_code: int, text: str, headers: dict | None = None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

    def json(self):
        return json.loads(self.text) if self.text else {}


def _request(
    method: str,
    url: str,
    headers: dict | None = None,
    params: dict | None = None,
    json_body: dict | None = None,
    timeout: int = 30,
):
    query = urllib.parse.urlencode(params or {}, doseq=True)
    full_url = f"{url}?{query}" if query else url

    data = None
    req_headers = dict(headers or {})
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(full_url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return SimpleResponse(resp.status, body, dict(resp.headers.items()))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return SimpleResponse(e.code, body, dict(e.headers.items()) if e.headers else {})


def _get(url: str, headers: dict | None = None, params: dict | None = None, timeout: int = 30):
    if httpx is not None:
        return httpx.get(url, headers=headers, params=params, timeout=timeout)
    return _request("GET", url, headers=headers, params=params, timeout=timeout)


def _post(
    url: str,
    headers: dict | None = None,
    params: dict | None = None,
    json_data: dict | None = None,
    timeout: int = 30,
):
    if httpx is not None:
        return httpx.post(url, headers=headers, params=params, json=json_data, timeout=timeout)
    return _request("POST", url, headers=headers, params=params, json_body=json_data, timeout=timeout)


def _delete(url: str, headers: dict | None = None, timeout: int = 30):
    if httpx is not None:
        return httpx.delete(url, headers=headers, timeout=timeout)
    return _request("DELETE", url, headers=headers, timeout=timeout)


def _read_file_value(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _resolve_token(token: str | None = None) -> str:
    resolved = (token or "").strip()
    if resolved.startswith("Bearer "):
        resolved = resolved[7:].strip()

    if resolved in {"$USER_TOKEN", "${USER_TOKEN}", '"$USER_TOKEN"', "'$USER_TOKEN'"}:
        resolved = ""

    if not resolved:
        resolved = os.getenv("USER_TOKEN", "").strip()

    if not resolved:
        resolved = _read_file_value(TOKEN_FALLBACK_FILE)

    return resolved


def _resolve_user_id(user_id: str | None = None) -> str:
    resolved = (user_id or "").strip()

    if resolved in {"$USER_ID", "${USER_ID}", '"$USER_ID"', "'$USER_ID'"}:
        resolved = ""

    if not resolved:
        resolved = os.getenv("USER_ID", "").strip()

    if not resolved:
        resolved = _read_file_value(USER_ID_FALLBACK_FILE)

    return resolved or "0"


def _headers(token: str | None = None) -> dict:
    """Tạo request headers với JWT token tùy chọn."""
    token = _resolve_token(token)
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _print_json(data):
    """In dữ liệu JSON đẹp mắt."""
    logger.info(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _handle_response(resp):
    """Xử lý phản hồi HTTP, in kết quả hoặc lỗi."""
    if resp.status_code >= 400:
        logger.error(f"LỖI [{resp.status_code}]: {resp.text}")
        sys.exit(1)
    try:
        data = resp.json()
        _print_json(data)
    except Exception:
        logger.info(resp.text)


# ─── Các lệnh hiện có ───────────────────────────────────


def cmd_health(args):
    """Kiểm tra xem HAutoML backend có đang chạy không."""
    try:
        resp = _get(f"{HAUTOML_BASE_URL}/home", timeout=10)
        logger.info(json.dumps({
            "status": "connected",
            "hautoml_url": HAUTOML_BASE_URL,
            "response_code": resp.status_code
        }, indent=2))
    except Exception:
        logger.error(json.dumps({
            "status": "disconnected",
            "hautoml_url": HAUTOML_BASE_URL,
            "error": "Không thể kết nối tới HAutoML"
        }, indent=2))
        sys.exit(1)


def cmd_list_datasets(args):
    """Liệt kê tất cả dataset của người dùng đã xác thực."""
    user_id = _resolve_user_id(args.user_id)
    resp = _post(
        f"{HAUTOML_BASE_URL}/get-list-data-by-userid",
        headers=_headers(args.token),
        params={"id": user_id},
        timeout=30,
    )
    _handle_response(resp)


def cmd_get_dataset_info(args):
    """Lấy thông tin chi tiết về một dataset cụ thể."""
    resp = _get(
        f"{HAUTOML_BASE_URL}/get-data-info",
        headers=_headers(args.token),
        params={"id": args.dataset_id},
        timeout=30,
    )
    _handle_response(resp)


def cmd_list_jobs(args):
    """Liệt kê tất cả job huấn luyện của người dùng."""
    user_id = _resolve_user_id(args.user_id)
    resp = _post(
        f"{HAUTOML_BASE_URL}/get-list-job-by-userId",
        headers=_headers(args.token),
        params={"user_id": user_id},
        timeout=30,
    )
    _handle_response(resp)


def cmd_get_job_info(args):
    """Lấy thông tin chi tiết về một job huấn luyện cụ thể."""
    resp = _post(
        f"{HAUTOML_BASE_URL}/get-job-info",
        headers=_headers(args.token),
        params={"id": args.job_id},
        timeout=30,
    )
    _handle_response(resp)


def cmd_train_model(args):
    """Gửi yêu cầu huấn luyện model mới (API cũ v1)."""
    user_id = _resolve_user_id(args.user_id)
    body = {
        "dataId": args.dataset_id,
        "target": args.target_column,
        "problemType": args.problem_type,
    }
    if args.model_list:
        body["modelList"] = args.model_list.split(",")

    resp = _post(
        f"{HAUTOML_BASE_URL}/train-from-requestbody-json/",
        headers=_headers(args.token),
        params={"userId": user_id, "id_data": args.dataset_id},
        json_data=body,
        timeout=60,
    )
    _handle_response(resp)


def cmd_activate_model(args):
    """Kích hoạt/triển khai model đã huấn luyện cho inference."""
    resp = _post(
        f"{HAUTOML_BASE_URL}/activate-model",
        headers=_headers(args.token),
        params={"job_id": args.job_id, "activate": 1},
        timeout=30,
    )
    _handle_response(resp)


def cmd_get_available_models(args):
    """Lấy danh sách thuật toán ML khả dụng theo loại bài toán."""
    resp = _get(
        f"{HAUTOML_BASE_URL}/api/v1/available-models/{args.problem_type}",
        timeout=15,
    )
    _handle_response(resp)


# ─── Các lệnh MỚI — API v2 ─────────────────────────────


def cmd_get_features(args):
    """Lấy danh sách đặc trưng (features) của dataset và gợi ý target."""
    resp = _get(
        f"{HAUTOML_BASE_URL}/v2/auto/features",
        headers=_headers(args.token),
        params={
            "id_data": args.dataset_id,
            "problem_type": args.problem_type,
        },
        timeout=30,
    )
    _handle_response(resp)


def cmd_preview_data(args):
    """Xem trước dữ liệu (vài dòng đầu) của một dataset."""
    resp = _get(
        f"{HAUTOML_BASE_URL}/v2/auto/data",
        headers=_headers(args.token),
        params={"id_data": args.dataset_id},
        timeout=30,
    )
    _handle_response(resp)


def cmd_get_metrics(args):
    """Lấy danh sách metric (độ đo) cho loại bài toán."""
    resp = _get(
        f"{HAUTOML_BASE_URL}/v2/auto/metrics",
        headers=_headers(args.token),
        params={"problem_type": args.problem_type},
        timeout=15,
    )
    _handle_response(resp)


def cmd_start_training(args):
    """Gửi yêu cầu huấn luyện phân tán (API v2)."""
    features = [f.strip() for f in args.features.split(",")] if args.features else []
    user_id = _resolve_user_id(args.user_id)

    body = {
        "id_data": args.dataset_id,
        "id_user": user_id,
        "config": {
            "choose": args.search_algorithm or "grid_search",
            "metric_sort": args.metric_sort or "accuracy",
            "list_feature": features,
            "target": args.target_column,
            "problem_type": args.problem_type,
        },
    }

    if args.max_time:
        body["config"]["max_time"] = int(args.max_time)

    resp = _post(
        f"{HAUTOML_BASE_URL}/v2/auto/jobs/training",
        headers=_headers(args.token),
        json_data=body,
        timeout=300,
    )
    _handle_response(resp)


def cmd_list_jobs_paginated(args):
    """Liệt kê job huấn luyện với phân trang (API v2)."""
    user_id = _resolve_user_id(args.user_id)
    page = args.page or 1
    limit = args.limit or 5

    resp = _get(
        f"{HAUTOML_BASE_URL}/v2/auto/jobs/offset/{user_id}",
        headers=_headers(args.token),
        params={"page": page, "limit": limit},
        timeout=30,
    )
    _handle_response(resp)


def cmd_batch_predict(args):
    """Chạy batch prediction bằng file CSV/Excel (API v2)."""
    file_path = args.file_path

    if not os.path.exists(file_path):
        logger.error(json.dumps({
            "error": f"File không tồn tại: {file_path}"
        }, indent=2, ensure_ascii=False))
        sys.exit(1)

    filename = os.path.basename(file_path)
    content_type = "text/csv" if filename.endswith(".csv") else \
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    if httpx is None:
        logger.error(json.dumps({
            "error": "batch_predict yêu cầu httpx nhưng môi trường hiện tại không có"
        }, indent=2, ensure_ascii=False))
        sys.exit(1)

    with open(file_path, "rb") as f:
        token = _resolve_token(args.token)
        resp = httpx.post(
            f"{HAUTOML_BASE_URL}/v2/auto/{args.job_id}/predictions",
            headers={"Authorization": f"Bearer {token}"} if token else {},
            files={"file_data": (filename, f, content_type)},
            timeout=120,
        )

    if resp.status_code >= 400:
        logger.error(f"LỖI [{resp.status_code}]: {resp.text}")
        sys.exit(1)

    # Kết quả có thể là file download hoặc JSON
    content_disp = resp.headers.get("content-disposition", "")
    if "attachment" in content_disp:
        out_file = f"predicted_{filename}"
        with open(out_file, "wb") as f:
            f.write(resp.content)
        logger.info(json.dumps({
            "status": "success",
            "output_file": out_file,
            "size_bytes": len(resp.content)
        }, indent=2, ensure_ascii=False))
    else:
        try:
            _print_json(resp.json())
        except Exception:
            logger.info(resp.text)


def cmd_delete_dataset(args):
    """Xóa một dataset."""
    resp = _delete(
        f"{HAUTOML_BASE_URL}/delete-dataset/{args.dataset_id}",
        headers=_headers(args.token),
        timeout=30,
    )
    _handle_response(resp)


# ─── CLI Parser ─────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="HAutoML Tools — CLI cho HAgent (CHỈ GỌI API)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # health
    subparsers.add_parser("health", help="Kiểm tra HAutoML có hoạt động không")

    # list_datasets
    p = subparsers.add_parser("list_datasets", help="Liệt kê dataset của người dùng")
    p.add_argument("--user-id", default=None, help="User ID (lấy từ JWT)")
    p.add_argument("--token", required=True, help="JWT access token")

    # get_dataset_info
    p = subparsers.add_parser("get_dataset_info", help="Lấy chi tiết dataset")
    p.add_argument("--dataset-id", required=True, help="ID dataset")
    p.add_argument("--token", required=True, help="JWT access token")

    # get_features — MỚI
    p = subparsers.add_parser("get_features", help="Lấy đặc trưng của dataset")
    p.add_argument("--dataset-id", required=True, help="ID dataset")
    p.add_argument("--problem-type", required=True,
                   choices=["classification", "regression"],
                   help="Loại bài toán")
    p.add_argument("--token", required=True, help="JWT access token")

    # preview_data — MỚI
    p = subparsers.add_parser("preview_data", help="Xem trước dữ liệu dataset")
    p.add_argument("--dataset-id", required=True, help="ID dataset")
    p.add_argument("--token", required=True, help="JWT access token")

    # list_jobs
    p = subparsers.add_parser("list_jobs", help="Liệt kê job huấn luyện")
    p.add_argument("--user-id", default=None, help="User ID")
    p.add_argument("--token", required=True, help="JWT access token")

    # list_jobs_paginated — MỚI
    p = subparsers.add_parser("list_jobs_paginated", help="Liệt kê job phân trang")
    p.add_argument("--user-id", required=True, help="User ID")
    p.add_argument("--page", type=int, default=1, help="Trang (mặc định: 1)")
    p.add_argument("--limit", type=int, default=5, help="Số job/trang (mặc định: 5)")
    p.add_argument("--token", required=True, help="JWT access token")

    # get_job_info
    p = subparsers.add_parser("get_job_info", help="Lấy chi tiết job")
    p.add_argument("--job-id", required=True, help="ID job")
    p.add_argument("--token", required=True, help="JWT access token")

    # get_available_models
    p = subparsers.add_parser("get_available_models",
                              help="Liệt kê thuật toán ML khả dụng")
    p.add_argument("--problem-type", required=True,
                   choices=["classification", "regression"],
                   help="Loại bài toán")

    # get_metrics — MỚI
    p = subparsers.add_parser("get_metrics", help="Liệt kê metric (độ đo)")
    p.add_argument("--problem-type", required=True,
                   choices=["classification", "regression"],
                   help="Loại bài toán")
    p.add_argument("--token", required=True, help="JWT access token")

    # train_model (v1 — legacy)
    p = subparsers.add_parser("train_model", help="Huấn luyện model (v1 legacy)")
    p.add_argument("--dataset-id", required=True, help="ID dataset")
    p.add_argument("--target-column", required=True, help="Tên cột target")
    p.add_argument("--problem-type", required=True,
                   choices=["classification", "regression"],
                   help="Loại bài toán")
    p.add_argument("--model-list", default=None,
                   help="Danh sách model phân cách bằng dấu phẩy")
    p.add_argument("--user-id", default=None, help="User ID")
    p.add_argument("--token", required=True, help="JWT access token")

    # start_training (v2 — phân tán) — MỚI
    p = subparsers.add_parser("start_training", help="Huấn luyện phân tán (v2)")
    p.add_argument("--dataset-id", required=True, help="ID dataset")
    p.add_argument("--target-column", required=True, help="Tên cột target")
    p.add_argument("--problem-type", required=True,
                   choices=["classification", "regression"],
                   help="Loại bài toán")
    p.add_argument("--metric-sort", default="accuracy",
                   help="Metric để tối ưu (mặc định: accuracy)")
    p.add_argument("--features", required=True,
                   help="Danh sách đặc trưng phân cách bằng dấu phẩy")
    p.add_argument("--search-algorithm", default="grid_search",
                   choices=["grid_search", "bayesian_search", "genetic_algorithm"],
                   help="Thuật toán tìm kiếm siêu tham số (mặc định: grid_search)")
    p.add_argument("--max-time", type=int, default=None,
                   help="Giới hạn thời gian (giây)")
    p.add_argument("--user-id", default=None, help="User ID")
    p.add_argument("--token", required=True, help="JWT access token")

    # activate_model
    p = subparsers.add_parser("activate_model", help="Kích hoạt model")
    p.add_argument("--job-id", required=True, help="ID job")
    p.add_argument("--token", required=True, help="JWT access token")

    # batch_predict — MỚI
    p = subparsers.add_parser("batch_predict", help="Chạy batch prediction")
    p.add_argument("--job-id", required=True, help="ID job")
    p.add_argument("--file-path", required=True, help="Đường dẫn file CSV/Excel")
    p.add_argument("--token", required=True, help="JWT access token")

    # delete_dataset — MỚI
    p = subparsers.add_parser("delete_dataset", help="Xóa dataset")
    p.add_argument("--dataset-id", required=True, help="ID dataset")
    p.add_argument("--token", required=True, help="JWT access token")

    args = parser.parse_args()

    commands = {
        "health": cmd_health,
        "list_datasets": cmd_list_datasets,
        "get_dataset_info": cmd_get_dataset_info,
        "get_features": cmd_get_features,
        "preview_data": cmd_preview_data,
        "list_jobs": cmd_list_jobs,
        "list_jobs_paginated": cmd_list_jobs_paginated,
        "get_job_info": cmd_get_job_info,
        "get_available_models": cmd_get_available_models,
        "get_metrics": cmd_get_metrics,
        "train_model": cmd_train_model,
        "start_training": cmd_start_training,
        "activate_model": cmd_activate_model,
        "batch_predict": cmd_batch_predict,
        "delete_dataset": cmd_delete_dataset,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
