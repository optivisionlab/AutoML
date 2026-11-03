"""
Tầng tool cho agent: bọc HAutoMLClient thành các hàm "an toàn cho LLM".

Hai nguyên tắc quan trọng:

1. Không bao giờ trả access_token / refresh_token / password ra ngoài.
   Token nằm trong client và tự được gắn vào request sau, LLM không cần thấy nó.
   Token lọt vào context của LLM là rò rỉ, và cũng không giúp ích gì.

2. Không raise. Lỗi được trả về dạng {"ok": False, "status_code": ..., "error": ...}
   để agent đọc được và tự quyết định bước tiếp theo, thay vì làm vỡ vòng lặp.

Các hàm ở đây là Python thuần nên gọi trực tiếp được mà không cần LLM.
"""

# Standard libraries
import logging
import os
import time
from collections import Counter
from datetime import datetime

# Local modules
from agent.api_client import ApiError, HAutoMLClient


_log = logging.getLogger("agent.tools")


# Lỗi tạm thời của backend: mất kết nối (0), quá tải (429), proxy báo backend
# chưa sẵn sàng (502-504). Gọi lại sau vài giây thường được.
_TRANSIENT_STATUS = (0, 429, 502, 503, 504)
# Backend tự nó không trả 429/502/503 - các mã này đến từ proxy khi request
# chưa tới được backend. Lệnh TẠO (job, dataset) chỉ thử lại với các mã này:
# timeout (0, 504) có thể backend đã nhận, gọi lại là sinh bản trùng.
_NOT_RECEIVED_STATUS = (429, 502, 503)
_RETRY_DELAYS = (1.0, 3.0)


def _failure(error: ApiError) -> dict:
    return {
        "ok": False,
        "status_code": error.status_code,
        "error": error.detail,
        # Lỗi tạm thời đã được _call thử lại mà vẫn hỏng.
        "retryable": error.status_code in _TRANSIENT_STATUS,
    }


def _call(method, *args, retry_on: tuple = _TRANSIENT_STATUS, **kwargs):
    """
    Gọi một method của client, tự thử lại khi backend lỗi tạm thời.

    Thử lại ở đây thay vì để LLM tự gọi lại: LLM hay bỏ cuộc ngay lần lỗi đầu
    (benchmark v4-02 nhóm E chỉ phục hồi được 6/20 lượt) hoặc ngược lại gọi lại
    liên tục. Hết lượt thử thì raise ApiError như cũ để tool trả _failure.
    """
    for delay in _RETRY_DELAYS:
        try:
            return method(*args, **kwargs)
        except ApiError as error:
            if error.status_code not in retry_on:
                raise
            name = getattr(method, "__name__", "API")
            _log.warning("%s lỗi tạm thời (HTTP %s), thử lại sau %.0fs", name, error.status_code, delay)
            time.sleep(delay)
    return method(*args, **kwargs)


def login(client: HAutoMLClient, username: str, password: str) -> dict:
    """Đăng nhập. Token được giữ trong client, không trả ra ngoài."""
    try:
        _call(client.login, username=username, password=password)
    except ApiError as error:
        return _failure(error)

    return {
        "ok": True,
        "logged_in": True,
        "note": "Đăng nhập thành công. Token đã được lưu, các tool sau dùng được ngay.",
    }


def _ensure_user_id(client: HAutoMLClient) -> str | None:
    """
    Lấy user_id của tài khoản đang đăng nhập, gọi /me nếu chưa có.

    Cố ý không để LLM truyền user_id vào: nó không biết ID thật và sẽ bịa ra,
    mà backend lại chặn khi user_id không khớp token (403 Permission denied).
    """
    if client.user_id:
        return client.user_id

    try:
        _call(client.get_me)
    except ApiError:
        return None

    return client.user_id


def _need_login() -> dict:
    # Không có tool đăng nhập - xác thực do hệ thống lo. Báo để Manager nói lại
    # với người dùng, đừng gợi ý LLM tự xử lý.
    return {
        "ok": False,
        "status_code": 401,
        "error": "Chưa đăng nhập hoặc phiên đăng nhập đã hết hạn. Người dùng cần đăng nhập lại trên web.",
    }


# Loại bài toán agent hỗ trợ (src/core/constants.py: ProblemType của backend).
PROBLEM_TYPES = ("classification", "regression", "time_series")
# Loại suy được từ cột mục tiêu. time_series có cùng ứng viên target với
# regression nên không bao giờ tự suy: người dùng phải muốn dự báo theo thời gian.
INFERABLE_TYPES = ("classification", "regression")


def list_my_datasets(client: HAutoMLClient) -> dict:
    """Liệt kê các dataset của tài khoản đang đăng nhập (backend tự lọc theo token)."""
    try:
        datasets = _call(client.list_datasets)
    except ApiError as error:
        return _failure(error)

    return {"ok": True, "count": len(datasets), "datasets": datasets}


def get_dataset_info(client: HAutoMLClient, dataset_id: str) -> dict:
    """Xem metadata một dataset theo ID. Không có tên cột - dùng get_dataset_schema."""
    try:
        dataset = _call(client.get_dataset_info, dataset_id)
    except ApiError as error:
        return _failure(error)

    return {"ok": True, "dataset": dataset}


# Số giá trị mẫu hiển thị cho mỗi cột. Đủ để LLM đoán ý nghĩa cột mà không
# kéo cả dataset vào context.
_SAMPLE_VALUES_PER_COLUMN = 5


def _summarize_columns(names: list, by_type: dict, rows: list, problem_type: str | None) -> list:
    """
    Gộp thông tin cột từ hai nguồn: cờ target của backend (theo từng loại bài
    toán) và các dòng preview.

    Tính bằng Python thuần, không dùng pandas, để venv của agent không phải cài
    thêm gì.
    """
    summary = []

    for name in names:
        values = [row.get(name) for row in rows]
        present = [value for value in values if value is not None]
        distinct = {str(value) for value in present}
        target_for = [kind for kind in INFERABLE_TYPES if (by_type.get(kind) or {}).get(name)]

        summary.append({
            "name": name,
            "can_be_target": (problem_type in target_for) if problem_type else bool(target_for),
            "target_for": target_for,
            "python_type": type(present[0]).__name__ if present else None,
            "distinct_in_preview": len(distinct),
            "missing_in_preview": len(values) - len(present),
            "sample_values": sorted(distinct)[:_SAMPLE_VALUES_PER_COLUMN],
        })

    return summary


# Định dạng ngày giờ hay gặp ngoài ISO 8601 (datetime.fromisoformat đã đọc được ISO).
_DATE_FORMATS = ("%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y %H:%M", "%Y-%m")


def _parse_time(value) -> datetime | None:
    """Đọc một giá trị ngày giờ dạng chuỗi. Số thuần không tính là ngày giờ."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _time_columns(names: list, rows: list, total_rows) -> list[dict]:
    """
    Cột ngày giờ trong preview kèm bước thời gian - thứ Model Agent cần cho bài
    toán time_series (backend: src/modules/preprocessing/time_series.py).

    Như _find_time_column của backend, cột chỉ tính là ngày giờ khi MỌI giá trị
    đọc được thành ngày giờ. Backend còn đòi các mốc cách đều và không trùng;
    preview chỉ là 50 dòng đầu nên chỉ báo được dấu hiệu, không khẳng định.
    """
    found = []
    for name in names:
        values = [row.get(name) for row in rows if row.get(name) is not None]
        times = [_parse_time(value) for value in values]
        if len(times) < 2 or any(t is None for t in times):
            continue
        times.sort()
        steps = [b - a for a, b in zip(times, times[1:])]
        step = Counter(steps).most_common(1)[0][0]
        info = {
            "name": name,
            "first_in_preview": times[0].isoformat(sep=" "),
            "step": str(step),
            "duplicated_in_preview": len(set(times)) < len(times),
            "regular_in_preview": len(set(steps)) == 1,
        }
        # Đúng khi file sắp theo thời gian và không hở mốc (backend vốn đòi cách đều).
        if info["regular_in_preview"] and step and isinstance(total_rows, int):
            info["estimated_last"] = (times[0] + step * (total_rows - 1)).isoformat(sep=" ")
        found.append(info)
    return found


def get_dataset_schema(
    client: HAutoMLClient,
    dataset_id: str,
    problem_type: str = "",
    sample_rows: int = 3,
) -> dict:
    """
    Lấy các thuộc tính (cột) của một dataset, kèm thống kê nhanh và vài dòng mẫu.

    Dataset không còn mang loại bài toán (dataType chỉ là "table"), nên luôn hỏi
    backend cột nào làm target được cho CẢ classification lẫn regression -
    Model Agent cần cả hai để suy ra loại bài toán từ cột mục tiêu. Dataset có
    cột ngày giờ thì thêm time_columns và ứng viên target cho time_series.

    Cố ý KHÔNG trả hết 50 dòng preview - chỉ vài dòng mẫu cộng thống kê từng
    cột, để không làm phình context của LLM với dataset lớn.

    problem_type: classification | regression | time_series thì target_candidates
        theo loại đó; bỏ trống thì là mọi cột làm target được cho ít nhất một loại.
    """
    try:
        info = _call(client.get_dataset_info, dataset_id)
        preview = _call(client.get_dataset_preview, dataset_id)
        by_type = {kind: _call(client.get_dataset_features, dataset_id, kind) or {} for kind in INFERABLE_TYPES}
    except ApiError as error:
        return _failure(error)

    names = list(by_type["classification"] or by_type["regression"])
    if not names:
        return {
            "ok": False,
            "error": (
                "Backend không đọc được cột của dataset này. Thường do file trong "
                "MinIO bị thiếu hoặc hỏng."
            ),
        }

    requested = (problem_type or "").strip().lower()
    requested = requested if requested in PROBLEM_TYPES else None
    rows = preview.get("records") or []
    columns = _summarize_columns(names, by_type, rows, requested)
    by_kind = {kind: [c["name"] for c in columns if kind in c["target_for"]] for kind in INFERABLE_TYPES}
    time_columns = _time_columns(names, rows, preview.get("rows"))
    if time_columns:
        # Backend chọn target time_series theo đúng luật của regression (datasets/service.py).
        times = {t["name"] for t in time_columns}
        by_kind["time_series"] = [name for name in by_kind["regression"] if name not in times]

    schema = {
        "ok": True,
        "dataset_id": dataset_id,
        "data_name": info.get("dataName"),
        "problem_type": requested,
        "total_rows": preview.get("rows"),
        "column_count": len(columns),
        "target_candidates": by_kind.get(requested, []) if requested else [c["name"] for c in columns if c["target_for"]],
        "target_candidates_by_type": by_kind,
        "columns": columns,
        "sample_rows": rows[:sample_rows],
        "note": (
            "target_for cho biết cột làm BIẾN MỤC TIÊU được với loại bài toán nào; "
            "cột có ở cả hai thì phải chọn loại bài toán. can_be_target false KHÔNG "
            "có nghĩa là cột đó không dùng được làm đặc trưng đầu vào. Thống kê "
            "distinct/missing tính trên 50 dòng preview, không phải toàn bộ dataset."
        ),
    }
    if time_columns:
        schema["time_columns"] = time_columns
        schema["time_series_note"] = (
            "Có cột ngày giờ: làm được time_series (dự báo theo thời gian) nếu người dùng muốn "
            "dự báo. list_feature phải chứa ĐÚNG MỘT cột thời gian; các cột khác chỉ dùng được khi "
            "biết trước giá trị của chúng ở tương lai. estimated_last là mốc cuối ước tính, giả định "
            "file sắp theo thời gian."
        )
    return schema


def infer_problem_type(schema: dict, target: str) -> str | None:
    """
    Loại bài toán suy ra từ cột mục tiêu: cột chỉ làm target được cho đúng một
    loại thì là loại đó. Cột hợp cả hai (số nguyên ít giá trị) hoặc không hợp
    loại nào -> None, phải để người dùng / Model Agent quyết định. time_series
    không bao giờ được suy ra, phải truyền problem_type.
    """
    by_type = schema.get("target_candidates_by_type") or {}
    kinds = [kind for kind in INFERABLE_TYPES if target in (by_type.get(kind) or [])]
    return kinds[0] if len(kinds) == 1 else None


# Trạng thái job của backend (src/core/constants.py: JobStatus).
JOB_RUNNING, JOB_SUCCESS, JOB_FAILED, JOB_CANCELLED = 0, 1, -1, -2
JOB_FINISHED = (JOB_SUCCESS, JOB_FAILED, JOB_CANCELLED)


def _normalize_job(job: dict) -> dict:
    """Backend v1 trả ID job ở `_id`; agent và frontend dùng `job_id`."""
    job = dict(job)
    job["job_id"] = str(job.get("_id") or job.get("id") or job.get("job_id") or "")
    return job


def _own_jobs(client: HAutoMLClient) -> tuple[list | None, dict | None]:
    """
    Job CỦA người đang đăng nhập. Phải tự lọc: tài khoản admin nhận được job
    của mọi người, mà agent chỉ được thao tác trên job của chính người dùng.
    """
    user_id = _ensure_user_id(client)
    if not user_id:
        return None, _need_login()

    try:
        jobs = _call(client.list_jobs)
    except ApiError as error:
        return None, _failure(error)

    own = [
        _normalize_job(job)
        for job in jobs or []
        if str((job.get("user") or {}).get("id") or "") == str(user_id)
    ]
    return own, None


def _job_brief(job: dict) -> dict:
    """Một dòng cho danh sách job - bỏ điểm từng model cho gọn context."""
    config = job.get("config") or {}
    return {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "dataset": (job.get("data") or {}).get("name"),
        "target": config.get("target"),
        "metric_sort": config.get("metric_sort"),
        "best_model": job.get("best_model"),
        "best_score": job.get("best_score"),
        "activate": job.get("activate"),
        "create_at": job.get("create_at"),
    }


def list_my_jobs(client: HAutoMLClient) -> dict:
    """Liệt kê các job huấn luyện của tài khoản đang đăng nhập, mới nhất trước."""
    jobs, problem = _own_jobs(client)
    if problem:
        return problem

    return {
        "ok": True,
        "count": len(jobs),
        "jobs": [_job_brief(job) for job in jobs],
        "note": "Điểm đầy đủ từng model của một job: get_job_info.",
    }


def find_own_job(client: HAutoMLClient, job_id: str) -> tuple[dict | None, dict | None]:
    """
    Tìm job trong danh sách job CỦA người đang đăng nhập.

    Trả (job, None) nếu thấy, (None, lỗi) nếu không. Backend không có endpoint
    xem một job, nên đây cũng là cách lấy chi tiết job.
    """
    jobs, problem = _own_jobs(client)
    if problem:
        return None, problem

    for job in jobs:
        if job["job_id"] == job_id:
            return job, None

    return None, {
        "ok": False,
        "status_code": 404,
        "error": f"Không có job '{job_id}' trong các job của bạn. Gọi list_my_jobs để lấy job_id thật.",
    }


def get_job_info(client: HAutoMLClient, job_id: str) -> dict:
    """Xem chi tiết một job huấn luyện theo job_id."""
    job, problem = find_own_job(client, job_id)
    if problem:
        return problem

    # Vị trí file model trên MinIO không giúp gì cho LLM.
    job.pop("model", None)
    return {"ok": True, "job": job}


def activate_model(client: HAutoMLClient, job_id: str, activate: bool = True) -> dict:
    """
    Bật (hoặc tắt) model của một job đã huấn luyện xong để dùng dự đoán.

    Kiểm trước job của chính người dùng và đã xong (status = 1) để báo lỗi rõ
    ràng; backend cũng kiểm lại hai điều này.
    """
    job, problem = find_own_job(client, job_id)
    if problem:
        return problem

    if job.get("status") != JOB_SUCCESS:
        return {
            "ok": False,
            "error": (
                f"Job '{job_id}' chưa huấn luyện xong (status = {job.get('status')}), "
                "chưa có model để kích hoạt."
            ),
        }

    try:
        deployment = _call(client.activate_model, job_id, activate)
    except ApiError as error:
        return _failure(error)

    return {
        "ok": True,
        "job_id": job_id,
        "activated": bool(activate),
        "best_model": job.get("best_model"),
        "endpoint_url": (deployment or {}).get("endpoint_url"),
        "features": (deployment or {}).get("features"),
    }


# Dự đoán qua chat chỉ cho vài mẫu nhập tay. Dữ liệu lớn hơn thì dùng trang
# dự đoán trên web - LLM không nên chép hàng trăm dòng vào tham số tool.
MAX_PREDICT_ROWS = 50


def predict(client: HAutoMLClient, job_id: str, rows: list) -> dict:
    """
    Dự đoán cho vài mẫu dữ liệu bằng model của một job đã kích hoạt.

    Cột được soát với list_feature của job TRƯỚC khi gửi, cho MỌI mẫu - backend
    chỉ kiểm mẫu đầu tiên - để thiếu cột thì báo rõ thiếu cột nào.
    """
    if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
        return {"ok": False, "error": "rows phải là danh sách mẫu, mỗi mẫu là một object {cột: giá trị}."}
    if len(rows) > MAX_PREDICT_ROWS:
        return {
            "ok": False,
            "error": f"Tối đa {MAX_PREDICT_ROWS} mẫu mỗi lần qua chat. Dữ liệu lớn hơn hãy dùng trang dự đoán.",
        }

    job, problem = find_own_job(client, job_id)
    if problem:
        return problem

    if job.get("status") != JOB_SUCCESS:
        return {"ok": False, "error": f"Job '{job_id}' chưa huấn luyện xong, chưa dự đoán được."}
    if job.get("activate") != 1:
        return {
            "ok": False,
            "error": f"Model của job '{job_id}' chưa được kích hoạt. Gọi activate_model trước.",
        }

    features = (job.get("config") or {}).get("list_feature") or []
    missing = sorted({f for f in features for row in rows if f not in row})
    if missing:
        return {
            "ok": False,
            "error": f"Mẫu thiếu cột mà model cần: {', '.join(missing)}.",
            "required_columns": features,
        }

    try:
        result = _call(client.predict, job_id, [{f: row.get(f) for f in features} if features else row for row in rows])
    except ApiError as error:
        return _failure(error)

    return {
        "ok": True,
        "job_id": job_id,
        "target": (job.get("config") or {}).get("target"),
        "model": (result or {}).get("model_name"),
        "predictions": [
            {"row": index, "predict": value}
            for index, value in enumerate((result or {}).get("predictions") or [])
        ],
    }


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

# Metric backend tính được, dùng khi không đọc được metric_list trong
# classification.yml / regression.yml / time_series.yml (agent chạy tách khỏi backend).
DEFAULT_METRICS = {
    "classification": [
        "accuracy", "balanced_accuracy", "precision_macro", "precision_weighted",
        "recall_macro", "recall_weighted", "f1_macro", "f1_weighted",
    ],
    "regression": ["mse", "mae", "mape", "r2"],
    "time_series": ["mse", "mae", "rmse", "r2"],
}
_BAD_PROBLEM_TYPE = "problem_type '{}' không hợp lệ. Chọn classification, regression hoặc time_series."


def list_metrics(client: HAutoMLClient, problem_type: str) -> dict:
    """
    Danh sách metric hợp lệ cho một loại bài toán.

    Backend v1 không có endpoint metric: nó đọc metric_list trong file yml của
    engine, nên ở đây đọc cùng file đó. Tham số client giữ cho đồng nhất chữ ký.
    """
    normalized = (problem_type or "").strip().lower()
    if normalized not in PROBLEM_TYPES:
        return {"ok": False, "error": _BAD_PROBLEM_TYPE.format(problem_type)}

    metrics = _load_skill_script("model-agent", "model_catalog").load_metrics(normalized)
    return {"ok": True, "problem_type": normalized, "metrics": metrics or DEFAULT_METRICS[normalized]}


def list_models(client: HAutoMLClient, problem_type: str) -> dict:
    """
    Các model engine sẽ huấn luyện cho một loại bài toán, kèm kích thước lưới tham số.

    Đọc classification.yml / regression.yml / time_series.yml của backend qua
    scripts/model_catalog.py. Tham số client không dùng tới, giữ cho đồng nhất
    chữ ký với mọi tool khác.
    """
    normalized = (problem_type or "").strip().lower()
    if normalized not in PROBLEM_TYPES:
        return {"ok": False, "error": _BAD_PROBLEM_TYPE.format(problem_type)}

    catalog = _load_skill_script("model-agent", "model_catalog").load_catalog(normalized)
    if not catalog:
        return {
            "ok": False,
            "error": (
                f"Không tìm thấy {normalized}.yml trong src/backend/assets. "
                "Agent chạy tách khỏi backend thì đặt HAUTOML_SYSTEM_MODELS_DIR."
            ),
        }

    return {
        "ok": True,
        "problem_type": normalized,
        "models": catalog,
        "note": (
            "Engine luôn huấn luyện TẤT CẢ model trong danh sách này rồi xếp hạng theo "
            "metric_sort - config không có trường chọn model. grid_size là số tổ hợp "
            "grid_search phải thử cho model đó."
        ),
    }


def prepare_training_config(
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
    Dựng config huấn luyện và soát nó dựa trên schema thật, KHÔNG gửi đi train.

    Soát bằng scripts/validate_config.py chứ không tin LLM tự điền đúng: chọn
    nhầm cột mục tiêu thì train hàng giờ rồi vứt đi. Model Agent dùng hàm này để
    ra quyết định config; start_training gọi lại nó làm chốt cuối.

    problem_type bỏ trống thì suy từ cột mục tiêu (xem infer_problem_type).

    Trả {"ok": True, "config", "warnings"} hoặc {"ok": False, "errors", ...} kèm
    sẵn valid_columns / target_candidates / valid_metrics để agent tự sửa.
    """
    schema = get_dataset_schema(client, dataset_id=dataset_id, problem_type=problem_type)
    if not schema.get("ok"):
        return schema

    resolved_type = schema["problem_type"] or infer_problem_type(schema, target)
    if resolved_type is None:
        by_type = schema["target_candidates_by_type"]
        both = all(target in by_type[kind] for kind in INFERABLE_TYPES)
        return {
            "ok": False,
            "error": "Không xác định được loại bài toán.",
            "errors": [
                f"Cột '{target}' làm mục tiêu được cho cả classification lẫn regression - "
                "truyền problem_type theo ý người dùng (dự đoán nhóm/nhãn hay giá trị số)."
                if both else
                f"Cột '{target}' không làm biến mục tiêu được cho loại bài toán nào."
            ],
            "valid_columns": [c["name"] for c in schema["columns"]],
            "target_candidates_by_type": by_type,
        }

    # validate_config so target với target_candidates của ĐÚNG loại bài toán.
    # Không có cột ngày giờ thì không có ứng viên time_series: validate_config báo lý do.
    schema = {
        **schema,
        "problem_type": resolved_type,
        "target_candidates": schema["target_candidates_by_type"].get(resolved_type, []),
    }

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

    return {"ok": True, "config": config, "warnings": check["warnings"]}


def _backend_training_config(config: dict) -> dict:
    """
    Config của agent -> TrainingConfig của backend. Agent gọi giới hạn thời
    gian là max_time (cùng tên trong R và SKILL.md), backend gọi là timeout.
    """
    payload = {key: value for key, value in config.items() if key != "max_time"}
    payload["timeout"] = config.get("max_time")
    return payload


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

    Trả về ngay kèm job_id, KHÔNG chờ train xong.
    """
    prepared = prepare_training_config(
        client,
        dataset_id=dataset_id,
        target=target,
        list_feature=list_feature,
        metric_sort=metric_sort,
        problem_type=problem_type,
        search_algorithm=search_algorithm,
        max_time=max_time,
    )
    if not prepared["ok"]:
        return prepared

    config = prepared["config"]
    try:
        result = _call(
            client.start_training,
            dataset_id=dataset_id,
            config=_backend_training_config(config),
            retry_on=_NOT_RECEIVED_STATUS,
        )
    except ApiError as error:
        return _failure(error)

    return {
        "ok": True,
        "job_id": (result or {}).get("job_id"),
        "config": config,
        "warnings": prepared["warnings"],
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


def ensure_login(client: HAutoMLClient) -> dict:
    """
    Đăng nhập tự động bằng tài khoản trong .env, nếu chưa có token.

    Cố ý KHÔNG phơi việc này thành tool: xác thực là chuyện hạ tầng, không phải
    việc agent phải suy nghĩ. LLM không nhìn thấy token, không biết mật khẩu, và
    không thể tự đăng ký hay đổi tài khoản.

    Khi frontend gọi qua agent.server, token của phiên web đã được gán sẵn vào
    client nên hàm này không làm gì cả.
    """
    if client.access_token:
        return {"ok": True, "note": "Đã có token sẵn."}

    username = os.getenv("AGENT_USER")
    password = os.getenv("AGENT_PASSWORD")

    if not username or not password:
        return {
            "ok": False,
            "error": (
                "Chưa đăng nhập được: thiếu AGENT_USER và AGENT_PASSWORD trong "
                "src/backend/.env"
            ),
        }

    return login(client, username=username, password=password)


def upload_dataset_file(
    client: HAutoMLClient,
    filename: str,
    content: bytes,
    data_name: str,
    data_type: str,
    mime_type: str = "text/csv",
) -> dict:
    """
    Đưa file dataset vào kho dataset của người dùng đang đăng nhập.

    KHÔNG phơi cho LLM: LLM không cầm được file. Hàm này được server.py gọi khi
    người dùng bấm nút tải lên trong khung chat. File phải được kiểm tra bằng
    agent.uploads.check_dataset_file TRƯỚC khi tới đây.

    data_type là loại bài toán người dùng chọn lúc tải lên (classification /
    regression / time_series). Backend v1 không lưu nó - dataset chỉ là "table" -
    nên chỉ trả lại để báo cho Agent Manager biết ý định của người dùng.
    """
    try:
        dataset = _call(
            client.upload_dataset_content,
            data_name=data_name,
            filename=filename,
            content=content,
            mime_type=mime_type,
            retry_on=_NOT_RECEIVED_STATUS,
        )
    except ApiError as error:
        return _failure(error)

    return {
        "ok": True,
        "dataset": {
            "id": dataset.get("_id") or dataset.get("id"),
            "name": dataset.get("dataName"),
            "type": data_type,
        },
    }
