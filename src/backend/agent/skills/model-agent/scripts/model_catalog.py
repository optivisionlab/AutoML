"""
Danh mục model mà engine HAutoML sẽ huấn luyện, đọc từ assets/system_models/*.yml.

Gọi từ pipeline (Model Agent và RAP), KHÔNG phải LLM tự chạy. Lý do cần nó:
LLM không biết engine có model nào, sẽ đề xuất "LSTM" hay "LightGBM" mà engine
không có. Đưa danh mục thật vào prompt thì kế hoạch bám đúng khả năng hệ thống.

Lưu ý quan trọng cho người viết prompt: config train của backend KHÔNG có
trường chọn model - engine luôn train TOÀN BỘ model trong file yml rồi xếp hạng
theo metric_sort. Model trong kế hoạch là dự đoán "model nào sẽ thắng", dùng để
so sánh kế hoạch, không phải bộ lọc gửi xuống backend.
"""

# Standard libraries
import os
from pathlib import Path

# Third party libraries
import yaml


# skills/model-agent/scripts/ -> lên 4 cấp là src/backend/
_DEFAULT_DIR = Path(__file__).resolve().parents[4] / "assets" / "system_models"


def _grid_size(param_sets: list) -> int:
    """Số tổ hợp tham số grid_search phải thử, cộng qua các nhánh params."""
    total = 0
    for params in param_sets or [{}]:
        combos = 1
        for values in (params or {}).values():
            combos *= len(values) if isinstance(values, list) else 1
        total += combos
    return total


def load_catalog(problem_type: str) -> list[dict]:
    """
    Trả [{model, grid_size, params}], rỗng nếu không đọc được file.

    Rỗng không phải lỗi chặn: pipeline vẫn chạy được, chỉ là kế hoạch kém cụ
    thể hơn. Agent chạy ở máy/container khác backend thì đặt
    HAUTOML_SYSTEM_MODELS_DIR trỏ tới thư mục chứa yml.
    """
    directory = Path(os.getenv("HAUTOML_SYSTEM_MODELS_DIR") or _DEFAULT_DIR)
    name = "regression" if problem_type == "regression" else "classification"
    path = directory / f"{name}.yml"
    if not path.is_file():
        return []

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return []

    models = data.get(f"{name.capitalize()}_models") or {}
    catalog = []
    for info in models.values():
        param_sets = info.get("params") or [{}]
        catalog.append({
            "model": info.get("model"),
            "grid_size": _grid_size(param_sets),
            "params": sorted({key for params in param_sets for key in (params or {})}),
        })
    return catalog
