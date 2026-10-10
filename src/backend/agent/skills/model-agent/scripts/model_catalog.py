"""
Danh mục model mà engine HAutoML sẽ huấn luyện, đọc từ classification.yml /
regression.yml của backend.

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
_BACKEND = Path(__file__).resolve().parents[4]
# Thứ tự tìm: cấu trúc refactor (assets/*.yml) rồi cấu trúc cũ
# (assets/system_models/*.yml). Thư mục nào có file thì dùng thư mục đó.
_CANDIDATE_DIRS = (_BACKEND / "assets", _BACKEND / "assets" / "system_models")


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

    Agent chạy ở máy/container khác backend thì đặt HAUTOML_SYSTEM_MODELS_DIR
    trỏ tới thư mục chứa yml.
    """
    name = "regression" if problem_type == "regression" else "classification"
    override = os.getenv("HAUTOML_SYSTEM_MODELS_DIR")
    directories = (Path(override),) if override else _CANDIDATE_DIRS
    path = next((d / f"{name}.yml" for d in directories if (d / f"{name}.yml").is_file()), None)
    if path is None:
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
