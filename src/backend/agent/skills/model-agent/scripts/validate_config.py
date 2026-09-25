"""
Kiểm tra config huấn luyện trước khi gửi đi train.

Gọi từ tools.start_training, KHÔNG phải LLM tự chạy. Đây là loại logic phải
đúng tuyệt đối: chọn sai cột mục tiêu thì train hàng giờ rồi vứt đi, nên không
thể chỉ dặn trong prompt mà phải chặn bằng code.

Hàm ở đây là thuần tuý: không mạng, không LLM, không đọc file. Nhờ vậy test
được bằng pytest hoặc chạy tay, không tốn quota.
"""

# Tên thuật toán tìm kiếm mà backend chấp nhận.
# Nguồn: automl/search/factory/search_strategy_factory.py
SEARCH_ALGORITHMS = ("grid_search", "genetic_algorithm", "bayesian_search")

PROBLEM_TYPES = ("classification", "regression")

# Mẫu tên cột trông như khoá định danh - không mang thông tin dự đoán.
# Nguồn: database/get_dataset.py, cùng mẫu backend dùng để loại cột ID.
_ID_HINTS = ("id", "stt", "no", "key", "code", "uuid", "guid")

# Giới hạn thời gian hợp lý, tính bằng giây.
MIN_MAX_TIME = 60
MAX_MAX_TIME = 24 * 60 * 60


def looks_like_id(column: str) -> bool:
    """Đoán cột có phải khoá định danh không, để cảnh báo khi dùng làm đặc trưng."""
    lowered = column.strip().lower()
    return lowered in _ID_HINTS or lowered.endswith("_id") or lowered.startswith("id_")


def validate_config(config: dict, schema: dict, valid_metrics: list[str]) -> dict:
    """
    Soát config huấn luyện dựa trên schema thật của dataset.

    Args:
        config: config sắp gửi đi, gồm target, list_feature, metric_sort,
            problem_type, search_algorithm, max_time.
        schema: kết quả của tools.get_dataset_schema cho chính dataset đó.
        valid_metrics: danh sách metric hợp lệ, lấy từ tools.list_metrics.

    Returns:
        {"ok": bool, "errors": [...], "warnings": [...]}
        errors chặn việc gửi đi; warnings chỉ để báo cho người dùng biết.
    """
    errors: list[str] = []
    warnings: list[str] = []

    columns = {c["name"] for c in schema.get("columns", [])}
    targets_allowed = set(schema.get("target_candidates") or [])
    by_name = {c["name"]: c for c in schema.get("columns", [])}

    problem_type = (config.get("problem_type") or "").strip().lower()
    if problem_type not in PROBLEM_TYPES:
        errors.append(
            f"problem_type '{config.get('problem_type')}' không hợp lệ. "
            f"Chọn một trong: {', '.join(PROBLEM_TYPES)}"
        )

    # --- target ---
    target = config.get("target")
    if not target:
        errors.append("Thiếu 'target'.")
    elif target not in columns:
        errors.append(
            f"Cột mục tiêu '{target}' không có trong dataset. "
            f"Các cột có thật: {', '.join(sorted(columns))}"
        )
    elif targets_allowed and target not in targets_allowed:
        errors.append(
            f"Cột '{target}' không dùng làm biến mục tiêu được với "
            f"problem_type '{problem_type}'. Cột hợp lệ: {', '.join(sorted(targets_allowed))}"
        )

    # --- list_feature ---
    features = config.get("list_feature") or []
    if not isinstance(features, list):
        errors.append("'list_feature' phải là danh sách.")
        features = []

    if not features:
        errors.append("Thiếu 'list_feature'. Phải có ít nhất một cột đặc trưng.")

    unknown = [f for f in features if f not in columns]
    if unknown:
        errors.append(
            f"Các cột đặc trưng không có trong dataset: {', '.join(unknown)}. "
            f"Các cột có thật: {', '.join(sorted(columns))}"
        )

    if target and target in features:
        errors.append(
            f"Cột mục tiêu '{target}' không được nằm trong list_feature - "
            "để nó vào là mô hình nhìn thấy đáp án, kết quả vô nghĩa."
        )

    if len(set(features)) != len(features):
        warnings.append("list_feature có cột bị lặp, backend sẽ bỏ qua bản trùng.")

    for column in features:
        if looks_like_id(column):
            warnings.append(
                f"Cột '{column}' trông như khoá định danh, thường không mang "
                "thông tin dự đoán. Cân nhắc bỏ khỏi list_feature."
            )

        info = by_name.get(column)
        if info and info.get("missing_in_preview", 0) > 25:
            warnings.append(
                f"Cột '{column}' thiếu {info['missing_in_preview']}/50 giá trị "
                "trong phần preview."
            )

    # --- metric_sort ---
    metric = config.get("metric_sort")
    if not metric:
        errors.append("Thiếu 'metric_sort'.")
    elif valid_metrics and metric not in valid_metrics:
        errors.append(
            f"metric_sort '{metric}' không hợp lệ cho {problem_type}. "
            f"Chọn một trong: {', '.join(valid_metrics)}"
        )

    # --- search_algorithm ---
    algorithm = config.get("search_algorithm")
    if algorithm and algorithm not in SEARCH_ALGORITHMS:
        errors.append(
            f"search_algorithm '{algorithm}' không hợp lệ. "
            f"Chọn một trong: {', '.join(SEARCH_ALGORITHMS)}"
        )

    # --- max_time ---
    max_time = config.get("max_time")
    if max_time is not None:
        if not isinstance(max_time, int) or isinstance(max_time, bool):
            errors.append("'max_time' phải là số nguyên (giây).")
        elif max_time < MIN_MAX_TIME:
            errors.append(f"'max_time' quá nhỏ, tối thiểu {MIN_MAX_TIME} giây.")
        elif max_time > MAX_MAX_TIME:
            errors.append(f"'max_time' quá lớn, tối đa {MAX_MAX_TIME} giây.")

    return {"ok": not errors, "errors": errors, "warnings": warnings}
