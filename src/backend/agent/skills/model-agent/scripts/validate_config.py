"""
Kiểm tra config huấn luyện trước khi gửi đi train.

Gọi từ tools.start_training, KHÔNG phải LLM tự chạy. Đây là loại logic phải
đúng tuyệt đối: chọn sai cột mục tiêu thì train hàng giờ rồi vứt đi, nên không
thể chỉ dặn trong prompt mà phải chặn bằng code.

Hàm ở đây là thuần tuý: không mạng, không LLM, không đọc file. Nhờ vậy test
được bằng pytest hoặc chạy tay, không tốn quota.
"""

# Tên thuật toán tìm kiếm mà backend chấp nhận.
# Nguồn: src/core/constants.py (SearchAlgorithm) của backend v1
SEARCH_ALGORITHMS = ("grid_search", "random_search", "bayesian_search", "tpe_search", "genetic_algorithm")

PROBLEM_TYPES = ("classification", "regression", "time_series")

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
    elif not targets_allowed:
        errors.append(
            f"Dataset không có cột nào dùng làm biến mục tiêu được với "
            f"problem_type '{problem_type}'."
        )
    elif target not in targets_allowed:
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

    if problem_type == "time_series":
        _check_time_series(features, target, schema, errors, warnings)
        target_info = by_name.get(target) if target else None
        if target_info and target_info.get("missing_in_preview", 0) > 0:
            # Backend (make_time_series_table) từ chối mọi giá trị target thiếu, nhưng
            # chỉ sau khi job đã vào hàng đợi - chặn ở đây báo được ngay.
            errors.append(
                f"Cột mục tiêu '{target}' thiếu {target_info['missing_in_preview']} giá trị ngay trong "
                "preview. time_series không bỏ được dòng thiếu target - cần điền hoặc lọc dữ liệu trước."
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


def _check_time_series(features: list, target, schema: dict, errors: list, warnings: list) -> None:
    """
    Điều kiện riêng của time_series, theo src/modules/preprocessing/time_series.py
    của backend: đúng một cột ngày giờ trong list_feature, mốc không trùng và
    cách đều. Sai thì job chỉ hỏng sau khi đã vào hàng đợi, nên chặn ở đây.
    """
    time_columns = {t["name"]: t for t in schema.get("time_columns") or []}
    if not time_columns:
        errors.append(
            "time_series cần một cột ngày giờ, nhưng dataset không có cột nào mà mọi "
            "giá trị đều đọc được thành ngày giờ."
        )
        return

    chosen = [f for f in features if f in time_columns]
    if not chosen:
        errors.append(
            "time_series cần ĐÚNG MỘT cột thời gian trong list_feature (backend tìm cột "
            f"thời gian trong đó). Thêm một trong: {', '.join(time_columns)}"
        )
        return
    if len(chosen) > 1:
        errors.append(f"list_feature chỉ được có một cột thời gian, đang có: {', '.join(chosen)}")
        return

    info = time_columns[chosen[0]]
    if info.get("duplicated_in_preview"):
        errors.append(
            f"Cột '{chosen[0]}' có mốc thời gian trùng nhau ngay trong preview. time_series "
            "chỉ nhận MỘT chuỗi, mỗi mốc một dòng - cần gộp hoặc lọc dữ liệu trước."
        )
    elif not info.get("regular_in_preview"):
        warnings.append(
            f"Các mốc của '{chosen[0]}' trong preview không cách đều. Backend sẽ báo lỗi nếu "
            "toàn bộ dữ liệu không cách đều (cần resample trước)."
        )

    exogenous = [f for f in features if f != chosen[0] and f != target]
    if exogenous:
        warnings.append(
            f"Khi dự báo phải biết trước giá trị tương lai của: {', '.join(exogenous)}. "
            "Không biết trước thì chỉ nên dùng cột thời gian."
        )
