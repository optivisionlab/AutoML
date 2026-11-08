"""Đường dẫn và hàm dùng chung. Không import agent - analyze/report chạy được không cần backend."""

# Standard libraries
import json
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "src" / "backend"
BENCH_DIR = REPO / "benchmark"
ARTIFACTS = REPO / "benchmark_artifacts"
CASES_PATH = BENCH_DIR / "cases.json"
CONFIG_PATH = ARTIFACTS / "bench_config.json"
PRICING_PATH = ARTIFACTS / "pricing.json"

_PLACEHOLDER = re.compile(r"<([A-Z_]+)>")


def load_json(path: Path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def substitute(value, values: dict):
    """Thay <TÊN> bằng giá trị thật, đệ quy trong str/list/dict. Thiếu giá trị thì giữ nguyên."""
    if isinstance(value, str):
        return _PLACEHOLDER.sub(lambda m: str(values.get(m.group(1)) or m.group(0)), value)
    if isinstance(value, list):
        return [substitute(v, values) for v in value]
    if isinstance(value, dict):
        return {k: substitute(v, values) for k, v in value.items()}
    return value


def read_trace(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    # Giải mã từng dòng: dòng cuối có thể bị cắt giữa một ký tự UTF-8 khi tiến trình bị ngắt.
    lines = [line for line in path.read_bytes().split(b"\n") if line.strip()]
    records = []
    for index, line in enumerate(lines):
        try:
            records.append(json.loads(line.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError):
            # Dòng cuối ghi dở; lượt đó đã mang cờ interrupted. Hỏng giữa tệp thì vẫn báo lỗi.
            if index == len(lines) - 1:
                break
            raise
    return records


def canonical_value(value) -> str:
    """Giá trị ô theo một dạng chung cho mọi nguồn (CSV, PostgreSQL, MySQL, JSON): số -> 10 chữ số có nghĩa."""
    if value is None:
        return ""
    try:
        return format(float(value), ".10g")
    except (TypeError, ValueError):
        return str(value).strip()


def content_fingerprint(records: list[dict]) -> str:
    """
    Hash nội dung không phụ thuộc thứ tự dòng hay thứ tự cột: mỗi dòng là các cặp cột=giá trị (cột sắp
    theo tên), rồi sắp các dòng. So được dataset nhập từ database với tập con của file train.
    """
    import hashlib

    lines = sorted("\x1f".join(f"{k}={canonical_value(row[k])}" for k in sorted(row)) for row in records)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

