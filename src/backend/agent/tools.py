"""
Tầng tool cho agent: bọc HAutoMLClient thành các hàm "an toàn cho LLM".

Hai nguyên tắc quan trọng:

1. Không bao giờ trả access_token / refresh_token / password ra ngoài.
   Token nằm trong client và tự được gắn vào request sau, LLM không cần thấy nó.
   Token lọt vào context của LLM là rò rỉ, và cũng không giúp ích gì.

2. Không raise. Lỗi được trả về dạng {"ok": False, "status_code": ..., "error": ...}
   để agent đọc được và tự quyết định bước tiếp theo, thay vì làm vỡ vòng lặp.

Các hàm ở đây là Python thuần nên gọi trực tiếp được, test được mà không cần LLM
(xem smoke_test.py).
"""

# Standard libraries
import os
from urllib.parse import parse_qs, unquote, urlparse

# Local modules
from agent.api_client import ApiError, HAutoMLClient


def _failure(error: ApiError) -> dict:
    return {"ok": False, "status_code": error.status_code, "error": error.detail}


def dev_tools_enabled() -> bool:
    """
    Tool dev chỉ bật khi AGENT_DEV_TOOLS được đặt.

    Mặc định tắt để dev_verify_account không lọt vào môi trường thật - nó bỏ qua
    bước chứng minh quyền sở hữu email.
    """
    return os.getenv("AGENT_DEV_TOOLS", "").strip().lower() in {"1", "true", "yes"}


def signup(
    client: HAutoMLClient,
    username: str,
    email: str,
    password: str,
    full_name: str,
    gender: str,
    date: str,
    number: str,
) -> dict:
    """Đăng ký tài khoản mới."""
    try:
        user = client.signup(
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            gender=gender,
            date=date,
            number=number,
        )
    except ApiError as error:
        return _failure(error)

    return {
        "ok": True,
        "user": {
            "id": user.get("id") or user.get("_id"),
            "username": user.get("username"),
            "email": user.get("email"),
            "role": user.get("role"),
        },
        "is_verified": False,
        "note": (
            "Tài khoản mới luôn ở trạng thái chưa xác thực email. "
            "Backend sẽ từ chối đăng nhập (403) cho tới khi email được xác thực."
        ),
    }


def login(client: HAutoMLClient, username: str, password: str) -> dict:
    """Đăng nhập. Token được giữ trong client, không trả ra ngoài."""
    try:
        client.login(username=username, password=password)
    except ApiError as error:
        return _failure(error)

    return {
        "ok": True,
        "logged_in": True,
        "note": "Đăng nhập thành công. Token đã được lưu, các tool sau dùng được ngay.",
    }


def get_me(client: HAutoMLClient) -> dict:
    """Lấy thông tin tài khoản đang đăng nhập."""
    if not client.access_token:
        return {
            "ok": False,
            "status_code": 401,
            "error": "Chưa đăng nhập. Gọi tool login trước.",
        }

    try:
        user = client.get_me()
    except ApiError as error:
        return _failure(error)

    return {"ok": True, "user": user}


def logout(client: HAutoMLClient) -> dict:
    """Đăng xuất và xoá token khỏi client."""
    if not client.access_token:
        return {"ok": True, "note": "Chưa đăng nhập, không cần đăng xuất."}

    try:
        client.logout()
    except ApiError as error:
        return _failure(error)

    return {"ok": True, "logged_in": False}


def resend_verification_email(client: HAutoMLClient, email: str) -> dict:
    """Yêu cầu backend gửi lại email xác thực."""
    try:
        result = client.resend_verification_email(email=email)
    except ApiError as error:
        return _failure(error)

    return {"ok": True, "detail": result.get("detail")}


def _ensure_user_id(client: HAutoMLClient) -> str | None:
    """
    Lấy user_id của tài khoản đang đăng nhập, gọi /me nếu chưa có.

    Cố ý không để LLM truyền user_id vào: nó không biết ID thật và sẽ bịa ra,
    mà backend lại chặn khi user_id không khớp token (403 Permission denied).
    """
    if client.user_id:
        return client.user_id

    try:
        client.get_me()
    except ApiError:
        return None

    return client.user_id


def _need_login() -> dict:
    return {"ok": False, "status_code": 401, "error": "Chưa đăng nhập. Gọi tool login trước."}


def list_my_datasets(client: HAutoMLClient) -> dict:
    """Liệt kê các dataset của tài khoản đang đăng nhập."""
    user_id = _ensure_user_id(client)
    if not user_id:
        return _need_login()

    try:
        datasets = client.list_datasets(user_id)
    except ApiError as error:
        return _failure(error)

    return {"ok": True, "count": len(datasets), "datasets": datasets}


def get_dataset_info(client: HAutoMLClient, dataset_id: str) -> dict:
    """Xem metadata một dataset theo ID. Không có tên cột - dùng get_dataset_schema."""
    try:
        dataset = client.get_dataset_info(dataset_id)
    except ApiError as error:
        return _failure(error)

    return {"ok": True, "dataset": dataset}


# Số giá trị mẫu hiển thị cho mỗi cột. Đủ để LLM đoán ý nghĩa cột mà không
# kéo cả dataset vào context.
_SAMPLE_VALUES_PER_COLUMN = 5


def _summarize_columns(features: dict, rows: list) -> list:
    """
    Gộp thông tin cột từ hai nguồn: cờ target của backend và các dòng preview.

    Tính bằng Python thuần, không dùng pandas, để venv của agent không phải cài
    thêm gì.
    """
    summary = []

    for name, can_be_target in features.items():
        values = [row.get(name) for row in rows]
        present = [value for value in values if value is not None]
        distinct = {str(value) for value in present}

        summary.append({
            "name": name,
            "can_be_target": can_be_target,
            "python_type": type(present[0]).__name__ if present else None,
            "distinct_in_preview": len(distinct),
            "missing_in_preview": len(values) - len(present),
            "sample_values": sorted(distinct)[:_SAMPLE_VALUES_PER_COLUMN],
        })

    return summary


def get_dataset_schema(
    client: HAutoMLClient,
    dataset_id: str,
    problem_type: str = "",
    sample_rows: int = 3,
) -> dict:
    """
    Lấy các thuộc tính (cột) của một dataset, kèm thống kê nhanh và vài dòng mẫu.

    Gộp ba lời gọi API: metadata, danh sách cột (/v2/auto/features) và preview
    (/v2/auto/data). Cố ý KHÔNG trả hết 50 dòng preview - chỉ vài dòng mẫu cộng
    thống kê từng cột, để không làm phình context của LLM với dataset lớn.

    problem_type bỏ trống thì lấy theo dataType của chính dataset.
    """
    try:
        info = client.get_dataset_info(dataset_id)
    except ApiError as error:
        return _failure(error)

    resolved_type = (problem_type or info.get("dataType") or "classification").strip().lower()

    try:
        features = client.get_dataset_features(dataset_id, resolved_type).get("features")
        preview = client.get_dataset_preview(dataset_id)
    except ApiError as error:
        return _failure(error)

    if not features:
        return {
            "ok": False,
            "error": (
                "Backend không đọc được cột của dataset này. Thường do file trong "
                "MinIO bị thiếu hoặc hỏng."
            ),
        }

    rows = preview.get("data") or []
    columns = _summarize_columns(features, rows)

    return {
        "ok": True,
        "dataset_id": dataset_id,
        "data_name": info.get("dataName"),
        "problem_type": resolved_type,
        "total_rows": preview.get("rows"),
        "column_count": len(columns),
        "target_candidates": [c["name"] for c in columns if c["can_be_target"]],
        "columns": columns,
        "sample_rows": rows[:sample_rows],
        "note": (
            "can_be_target chỉ nói cột đó có phù hợp làm BIẾN MỤC TIÊU với "
            "problem_type này hay không. Nó KHÔNG có nghĩa là cột đó không dùng "
            "được làm đặc trưng đầu vào. Thống kê distinct/missing tính trên "
            "50 dòng preview, không phải toàn bộ dataset."
        ),
    }


def list_my_jobs(client: HAutoMLClient) -> dict:
    """Liệt kê các job huấn luyện của tài khoản đang đăng nhập."""
    user_id = _ensure_user_id(client)
    if not user_id:
        return _need_login()

    try:
        jobs = client.list_jobs(user_id)
    except ApiError as error:
        return _failure(error)

    return {"ok": True, "count": len(jobs), "jobs": jobs}


def get_job_info(client: HAutoMLClient, job_id: str) -> dict:
    """Xem chi tiết một job huấn luyện theo job_id."""
    try:
        job = client.get_job_info(job_id)
    except ApiError as error:
        return _failure(error)

    return {"ok": True, "job": job}


def _extract_token(raw: str) -> str:
    """
    Lấy token từ chuỗi người dùng đưa vào.

    Người dùng thường dán nguyên link trong email thay vì chỉ token, nên nhận cả
    hai dạng: token thuần, hoặc `.../verify-email?token=<token>`.
    """
    value = (raw or "").strip()

    if "token=" in value:
        found = parse_qs(urlparse(value).query).get("token")
        if found:
            return unquote(found[0])

    return value


def verify_email(client: HAutoMLClient, token: str) -> dict:
    """Xác thực email bằng token lấy từ link trong email."""
    clean_token = _extract_token(token)
    if not clean_token:
        return {"ok": False, "status_code": 400, "error": "Token trống."}

    try:
        client.verify_email(clean_token)
    except ApiError as error:
        return _failure(error)

    return {
        "ok": True,
        "verified": True,
        "logged_in": True,
        "note": (
            "Xác thực thành công. Endpoint này trả luôn token đăng nhập nên tài "
            "khoản đã ở trạng thái đăng nhập, không cần gọi login nữa."
        ),
    }


def dev_verify_account(client: HAutoMLClient, user_id: str, email: str = "") -> dict:
    """
    CHỈ DÙNG KHI PHÁT TRIỂN: tự ký token xác thực rồi gọi endpoint thật.

    Bỏ qua khâu gửi/nhận email nhưng vẫn đi qua `POST /auth/verifications` như
    luồng thật, không ghi thẳng vào MongoDB.

    Chỉ chạy được khi agent nằm cùng máy/cùng cấu hình với backend, vì cần
    SECRET_KEY trong .env để ký token giống hệt backend.
    """
    if not dev_tools_enabled():
        return {
            "ok": False,
            "error": "Tool dev đang tắt. Đặt AGENT_DEV_TOOLS=1 trong .env để bật.",
        }

    try:
        from users.utils.authentication import jwt_service
    except ImportError as error:
        return {
            "ok": False,
            "error": (
                f"Không import được jwt_service ({error}). "
                "Cần chạy từ thư mục src/backend và đã cài PyJWT."
            ),
        }

    token = jwt_service.create_verification_token({"sub": user_id, "email": email})
    return verify_email(client, token)


# Giới hạn độ dài một reference trả về, tránh một file dài làm phình context.
_MAX_REFERENCE_CHARS = 6000


def read_reference(client: HAutoMLClient, ref_id: str) -> dict:
    """
    Đọc một file tài liệu trong references/ của skill.

    Các file này cố ý KHÔNG nằm trong system prompt - chỉ tên và mô tả được liệt
    kê ở đó. Nhờ vậy tài liệu dài bao nhiêu cũng không tốn token mỗi lượt, agent
    chỉ trả giá khi thật sự cần đọc.

    Tham số client không dùng tới, giữ cho đồng nhất chữ ký với mọi tool khác.
    """
    from agent import skills as skills_module

    reference = skills_module.find_reference((ref_id or "").strip())
    if reference is None:
        available = [
            ref.ref_id
            for skill in skills_module.load_skills()
            for ref in skill.references
        ]
        return {
            "ok": False,
            "error": f"Không có tài liệu '{ref_id}'.",
            "available": available,
        }

    text = reference.path.read_text(encoding="utf-8")
    truncated = len(text) > _MAX_REFERENCE_CHARS

    return {
        "ok": True,
        "ref_id": reference.ref_id,
        "truncated": truncated,
        "content": text[:_MAX_REFERENCE_CHARS],
    }


# Mặc định khi người dùng không nêu. 900 giây đủ cho dataset nhỏ/vừa.
DEFAULT_MAX_TIME = 900
DEFAULT_SEARCH_ALGORITHM = "grid_search"


def list_metrics(client: HAutoMLClient, problem_type: str) -> dict:
    """Danh sách metric hợp lệ cho một loại bài toán, đọc từ cấu hình backend."""
    normalized = (problem_type or "").strip().lower()
    if normalized not in ("classification", "regression"):
        return {
            "ok": False,
            "error": f"problem_type '{problem_type}' không hợp lệ. Chọn classification hoặc regression.",
        }

    try:
        result = client.get_metrics(normalized)
    except ApiError as error:
        return _failure(error)

    metrics = result.get("metrics") or []
    return {"ok": True, "problem_type": normalized, "metrics": metrics}


def start_training(
    client: HAutoMLClient,
    dataset_id: str,
    target: str,
    list_feature: list,
    metric_sort: str,
    problem_type: str = "",
    search_algorithm: str = DEFAULT_SEARCH_ALGORITHM,
    max_time: int = DEFAULT_MAX_TIME,
) -> dict:
    """
    Khởi tạo job huấn luyện sau khi soát config dựa trên schema thật.

    Soát bằng scripts/validate_config.py chứ không tin LLM tự điền đúng: chọn
    nhầm cột mục tiêu thì train hàng giờ rồi vứt đi.

    Trả về ngay kèm job_id, KHÔNG chờ train xong.
    """
    user_id = _ensure_user_id(client)
    if not user_id:
        return _need_login()

    schema = get_dataset_schema(client, dataset_id=dataset_id, problem_type=problem_type)
    if not schema.get("ok"):
        return schema

    resolved_type = schema["problem_type"]

    metrics = list_metrics(client, resolved_type)
    if not metrics.get("ok"):
        return metrics

    config = {
        "choose": "new_model",
        "problem_type": resolved_type,
        "target": target,
        "list_feature": list(list_feature or []),
        "metric_sort": metric_sort,
        "search_algorithm": search_algorithm,
        "max_time": max_time,
    }

    check = _validate_training_config(config, schema, metrics["metrics"])
    if not check["ok"]:
        return {
            "ok": False,
            "error": "Config huấn luyện không hợp lệ.",
            "errors": check["errors"],
            "warnings": check["warnings"],
            "valid_columns": [c["name"] for c in schema["columns"]],
            "target_candidates": schema["target_candidates"],
            "valid_metrics": metrics["metrics"],
        }

    try:
        result = client.start_training(dataset_id=dataset_id, user_id=user_id, config=config)
    except ApiError as error:
        return _failure(error)

    return {
        "ok": True,
        "job_id": result.get("job_id"),
        "config": config,
        "warnings": check["warnings"],
        "note": (
            "Job đã được đưa vào hàng đợi và đang chạy nền. Dùng get_job_info với "
            "job_id này để xem tiến độ. KHÔNG có kết quả ngay."
        ),
    }


def _load_skill_script(skill: str, module_name: str):
    """
    Nạp một module trong skills/<skill>/scripts/.

    Nạp động thay vì import thẳng vì thư mục skills không phải package Python -
    nó là dữ liệu của skill, và mỗi skill tự quản lý script của mình.
    """
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parent / "skills" / skill / "scripts" / f"{module_name}.py"
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy script: {path}")

    spec = importlib.util.spec_from_file_location(f"skill_{skill}_{module_name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_training_config(config: dict, schema: dict, valid_metrics: list) -> dict:
    """Gọi validate_config.py của model-agent."""
    try:
        script = _load_skill_script("model-agent", "validate_config")
    except FileNotFoundError as error:
        return {"ok": False, "errors": [str(error)], "warnings": []}

    return script.validate_config(config, schema, valid_metrics)
