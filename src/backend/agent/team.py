"""
Agent Manager uỷ thác cho 4 sub-agent - các mũi tên trong sơ đồ trang 1.

    Manager ──ask_prompt_agent──▶ ① Prompt Agent   → R (JSON 6 khoá)
            ──ask_data_agent────▶ ② Data Agent     → hồ sơ dữ liệu ──┐ "dữ liệu"
            ──ask_model_agent───▶ ③ Model Agent  ◀───────────────────┘
                                       │ submit_config
                                       ▼
                               validate_config.py (CODE)
                                       │ "config hợp lệ" → config_id
            ──ask_operation_agent─▶ ④ Operation Agent → start_training(config_id)
                                       │
                                       ▼ JobWatcher: get_job_info tới khi status ≠ 0

Mỗi sub-agent là một vòng LLM riêng: system prompt riêng (SKILL.md của nó),
tập tool riêng, và KHÔNG thấy lịch sử hội thoại. Thứ duy nhất đi giữa các agent
là Handoff - dữ liệu có cấu trúc do CODE chuyển, không phải LLM chép lại. Nhờ
vậy Model Agent nhận đúng schema mà Data Agent đã đọc, và Operation Agent chỉ
chạy được config đã qua validate_config (nó chỉ cầm config_id, không tự điền).
"""

# Standard libraries
import json
import logging
import math
import re
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass, field

# Local modules
from agent import prompts, skills as skills_module, tools, tracing
from agent.agent_openai import (
    SUBAGENT_MAX_STEPS,
    TurnBudgetExceeded,
    create_completion,
    describe_error,
    log_exception,
    _DISPATCH,
    _accumulate_usage,
    run_tool_loop,
    schemas_for,
)
from agent.prompts import DATA_AGENT, MANAGER, MODEL_AGENT, OPERATION_AGENT, PROMPT_AGENT
from agent.watcher import summarize_job, wants_deploy


# Chi tiết lỗi đầy đủ chỉ vào log phía server, không vào prompt hay Langfuse.
_log = logging.getLogger("agent.team")

PROBLEM_TYPES = tools.PROBLEM_TYPES
REQUIREMENT_KEYS = ("user", "problem", "dataset", "model", "knowledge", "service")
SEARCH_ALGORITHMS = ("grid_search", "random_search", "bayesian_search", "tpe_search", "genetic_algorithm")
_CONSTRAINT_OPS = (">=", ">", "<=", "<")

# Metric backend tính được - cùng danh sách trong skills/prompt-agent/SKILL.md.
# Ràng buộc dùng tên khác thì watcher không tìm được điểm và không kiểm định được.
VALID_METRICS = {kind: tuple(metrics) for kind, metrics in tools.DEFAULT_METRICS.items()}
# Cách người dùng (và LLM) hay gọi -> tên metric thật.
_METRIC_ALIASES = {
    "acc": "accuracy",
    "f1": "f1_macro",
    "f1_score": "f1_macro",
    "precision": "precision_macro",
    "recall": "recall_macro",
    "r2_score": "r2",
    "r_squared": "r2",
    "mean_squared_error": "mse",
    "mean_absolute_error": "mae",
    "root_mean_squared_error": "rmse",
}


# Metric là tỉ lệ (engine tính 0-1; MAPE của sklearn cũng là tỉ lệ: 10% = 0.1). Người dùng / LLM
# hay viết phần trăm ("accuracy trên 90", "MAPE dưới 10"): giữ nguyên thì ràng buộc luôn trượt
# (accuracy >= 90) hoặc luôn đạt (mape <= 10 - tự kích hoạt bất kể chất lượng).
_RATIO_METRICS = {
    "accuracy", "balanced_accuracy", "precision_macro", "precision_weighted",
    "recall_macro", "recall_weighted", "f1_macro", "f1_weighted", "r2", "mape",
}
_ERROR_METRICS = {"mse", "mae", "rmse", "mape"}


def scale_constraint_value(metric: str, value: float) -> tuple[float | None, str | None]:
    """
    Giá trị ràng buộc theo đúng thang engine tính. Trả (giá trị, ghi chú): giá trị None là
    không dùng được (ghi chú nói lý do); ghi chú khác None khi đã đổi phần trăm sang tỉ lệ.
    """
    if not math.isfinite(value):
        return None, f"Giá trị {value} của {metric} không phải số hữu hạn."
    if metric in _ERROR_METRICS and value < 0:
        return None, f"{metric} không âm - ràng buộc {metric} theo {value} không có nghĩa."
    if metric in _RATIO_METRICS and metric != "r2" and value < 0:
        return None, f"{metric} là tỉ lệ 0-1 - giá trị {value} không có nghĩa."
    # MAPE nhỏ hơn là tốt hơn: "mape <= 1" theo tỉ lệ là 100% - gần như luôn đạt. Ngưỡng >= 1 chỉ
    # có nghĩa khi là phần trăm ("MAPE dưới 1%").
    percent = value >= 1 if metric == "mape" else value > 1
    if metric in _RATIO_METRICS and percent:
        if value <= 100:
            scaled = round(value / 100, 6)
            return scaled, f"Hiểu {metric} {value:g} là {value:g}% = {scaled:g} (engine tính {metric} theo tỉ lệ 0-1)."
        return None, f"{metric} là tỉ lệ (vd 90% = 0.9) - giá trị {value:g} không có nghĩa."
    if metric == "mape":
        # Dưới 1 vẫn mơ hồ (0.5 = 50% hay 0.5%?): giữ tỉ lệ nhưng nói rõ cách hiểu để người dùng sửa.
        return value, f"Hiểu mape {value:g} là tỉ lệ = {value * 100:g}%. Ý người dùng là {value:g}% thì phải là {value / 100:g}."
    return value, None


def normalize_metric(name, problem_type: str | None) -> str | None:
    """Tên metric thật mà backend tính, hoặc None nếu hệ thống không có metric đó."""
    metric = str(name or "").strip().lower().replace("-", "_").replace(" ", "_")
    metric = _METRIC_ALIASES.get(metric, metric)
    allowed = VALID_METRICS.get(problem_type or "") or tuple(m for ms in VALID_METRICS.values() for m in ms)
    return metric if metric in allowed else None

# Dataset rộng hàng trăm cột thì hồ sơ đầy đủ quá dài cho prompt Model Agent.
_MAX_PROFILE_COLUMNS = 60
_SAMPLES_PER_COLUMN = 3
# Prompt Agent không thấy lịch sử, chỉ thấy vài câu gần nhất của người dùng -
# đủ để không mất chi tiết như "target là cột Type" nói ở lượt trước.
_RECENT_USER_MESSAGES = 6
# Dòng do hệ thống chèn vào tin người dùng (chat.py), không phải người dùng gõ.
_EVENT_PREFIX = "[Sự kiện]"
# Câu trong missing chỉ xin mẫu để dự đoán (xem normalize_requirements).
_ASKS_FOR_PREDICT_ROWS = re.compile(r"mẫu.*dự đoán|dự đoán.*mẫu", re.IGNORECASE)
# Cụm báo cột NGAY SAU nó là cột cần dự đoán ("target Type", "dự báo load_kwh"),
# và cụm đứng SAU tên cột ("Age là target"). Xem _named_targets.
_TARGET_CUE = re.compile(r"target|mục tiêu|dự đoán|dự báo|predict|forecast|nhãn|label", re.IGNORECASE)
_TARGET_CUE_AFTER = re.compile(r"\s*(?:là|làm)\s+(?:cột\s+)?(?:target|mục tiêu|nhãn|label)", re.IGNORECASE)
_CLAUSE_END = re.compile(r"[.!?;\n]")


def _named_targets(text: str, columns: list[str]) -> set[str]:
    """
    Cột người dùng nói là cột cần dự đoán: cột ĐẦU TIÊN sau một cụm như "target",
    "dự báo" trong cùng mệnh đề, hoặc cột ngay trước "là target".

    Chỉ nhắc tên cột thì không tính: "bỏ cột age, dự đoán giúp tôi" hay "feature
    Length,Diameter" không chọn age hay Diameter làm mục tiêu.
    """
    patterns = {c: re.compile(rf"(?<!\w){re.escape(c)}(?!\w)", re.IGNORECASE) for c in columns}
    chosen = set()
    for cue in _TARGET_CUE.finditer(text):
        tail = text[cue.end():cue.end() + 60]
        stop = _CLAUSE_END.search(tail)
        tail = tail[:stop.start()] if stop else tail
        hits = [(m.start(), c) for c, p in patterns.items() if (m := p.search(tail))]
        if hits:
            chosen.add(min(hits)[1])
    for cue in _TARGET_CUE_AFTER.finditer(text):
        head = text[max(0, cue.start() - 40):cue.start()]
        hits = [(m.end(), c) for c, p in patterns.items() for m in p.finditer(head)]
        if hits:
            chosen.add(max(hits)[1])
    return chosen


# --- Tự kích hoạt model sau khi train (R.service.deploy) ---------------------------------
# Ý người dùng (muốn / không muốn / rút lại) do LLM hiểu - đoán phủ định tiếng Việt tự do
# bằng regex không bao giờ đủ tin cậy. Code chỉ giữ ba chốt chắc chắn đúng:
#   1. LLM không được bịa cờ: người dùng phải có NHẮC tới việc kích hoạt (bất kể ý gì).
#   2. Cờ chỉ áp cho dataset mà R nói tới (không mang sang job của dataset khác).
#   3. Hành động hiển thị và huỷ được: thẻ job hiện "sẽ tự kích hoạt" kèm nút huỷ, và
#      Operation Agent có set_auto_activate khi người dùng đổi ý lúc job đang chạy.
_DEPLOY_CUE_VI = re.compile(
    r"(?<!hàm )kích\s*hoạt|triển\s*khai|(?:dùng|sử\s*dụng)\s+(?:model\s+|mô\s*hình\s+)?ngay"
    r"|đưa\s+vào\s+sử\s*dụng|bật\s+(?:model|mô\s*hình|api)",
    re.IGNORECASE,
)
_DEPLOY_CUE_ASCII = re.compile(
    r"\bkich\s*hoat\b|\btrien\s*khai\b|\b(?:dung|su\s*dung)\s+(?:model\s+|mo\s*hinh\s+)?ngay\b"
    r"|\bdua\s+vao\s+su\s*dung\b|\bbat\s+(?:model|mo\s*hinh|api)\b",
    re.IGNORECASE,
)
# Từ tiếng Anh đứng riêng (không phải một phần tên như "deploy_logs", "activation-data").
_DEPLOY_CUE_EN = re.compile(
    r"(?<![\w-])(?:deploy(?:s|ed|ing|ment)?|activat(?:e|es|ed|ing|ion)(?!\s+function))(?![\w-])",
    re.IGNORECASE,
)


def _mentions_activation(messages: list[str]) -> bool:
    """Người dùng (không tính dòng [Sự kiện] do hệ thống chèn) có nhắc tới việc kích hoạt / triển khai model."""
    for message in messages:
        text = unicodedata.normalize(
            "NFC", "\n".join(line for line in message.splitlines() if not line.startswith(_EVENT_PREFIX))
        )
        if any(pattern.search(text) for pattern in (_DEPLOY_CUE_VI, _DEPLOY_CUE_ASCII, _DEPLOY_CUE_EN)):
            return True
    return False


def _only_tightens(existing: list[dict], added: list[dict]) -> bool:
    """
    Điều kiện mới chỉ làm việc tự kích hoạt KHÓ hơn (thêm metric mới, hoặc cùng metric cùng
    chiều mà ngưỡng chặt hơn) - không cần người dùng xác nhận lại. Nới lỏng thì cần.
    """
    def at_least_as_strict(new: dict, old: dict) -> bool:
        op, value, old_op, old_value = new.get("op"), new.get("value"), old.get("op"), old.get("value")
        if not isinstance(value, (int, float)) or not isinstance(old_value, (int, float)):
            return False
        if op in (">=", ">") and old_op in (">=", ">"):
            return value > old_value or (value == old_value and (op == ">" or old_op == ">="))
        if op in ("<=", "<") and old_op in ("<=", "<"):
            return value < old_value or (value == old_value and (op == "<" or old_op == "<="))
        return False

    # Ràng buộc mới THAY mọi ràng buộc cũ cùng metric (watcher._merge_constraints): mỗi ràng buộc
    # cũ bị thay phải có một ràng buộc mới cùng metric chặt ít nhất bằng nó (vd khoảng
    # 0.8 <= accuracy <= 0.99 mà chỉ gửi accuracy >= 0.85 là bỏ mất cận trên - nới lỏng).
    added_metrics = {c.get("metric") for c in added}
    for old in existing:
        if old.get("metric") not in added_metrics:
            continue
        same = [c for c in added if c.get("metric") == old.get("metric")]
        if not any(at_least_as_strict(new, old) for new in same):
            return False
    return True


# Lý do set_auto_activate bị từ chối (watcher.set_auto_activate trả mã) - nói đúng lý do.
_AUTO_ACTIVATE_REFUSED = {
    "not_watched": (
        "Job '{job_id}' không còn được theo dõi trong phiên này (đã xong, hết giờ theo dõi, hoặc chưa "
        "từng theo dõi) - không còn tự kích hoạt. Job đã xong thì dùng activate_model để kích hoạt / tắt."
    ),
    "in_progress": "Job '{job_id}' vừa xong và hệ thống ĐANG kích hoạt model - không huỷ được nữa. "
                   "Muốn tắt thì đợi xong rồi dùng activate_model(activate=false).",
    "finished": "Lời hứa tự kích hoạt của job '{job_id}' đã được xử lý xong hoặc đã hết hiệu lực.",
}


# Sau ngần này giây mà vẫn không thấy job khớp trong danh sách thì lệnh tạo "chưa rõ kết quả"
# coi như chưa tạo được (backend ghi job trong vài giây sau khi nhận request).
_UNRESOLVED_RECHECK_SECONDS = 120


def _config_key(config: dict) -> tuple:
    """Những trường xác định "cùng một lần train" để chống tạo trùng."""
    return (
        config.get("target"), config.get("metric_sort"), config.get("problem_type"),
        tools.feature_set(config.get("list_feature")),
    )


def _without_deploy(requirements: dict) -> dict:
    """Bản sao R với service.deploy = false (không sửa R gốc)."""
    return {**requirements, "service": {**(requirements.get("service") or {}), "deploy": False}}


class AgentOutputError(RuntimeError):
    """Model không trả được JSON hợp lệ kể cả sau khi được nhắc sửa."""


def parse_json(text: str) -> dict:
    """
    Bóc object JSON đầu tiên khỏi câu trả lời của model.

    Không dùng response_format: các provider hỗ trợ không giống nhau, có bên trả
    400 khi gặp tham số lạ. Model hay bọc JSON trong ```json ... ``` hoặc thêm
    câu dẫn kể cả khi đã được dặn, nên lấy từ { đầu tiên tới } cuối cùng.
    """
    cleaned = (text or "").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("không tìm thấy object JSON trong câu trả lời")

    value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("JSON phải là một object")
    return value


def profile_brief(schema: dict, problem_type: str | None = None) -> dict:
    """
    Hồ sơ dữ liệu gọn cho prompt: bỏ sample_rows, cắt bớt giá trị mẫu và số cột.

    problem_type đã biết (từ R) thì target_candidates theo đúng loại đó; chưa
    biết thì Model Agent tự suy từ target_candidates_by_type.
    """
    columns = schema.get("columns") or []
    by_type = schema.get("target_candidates_by_type") or {}
    known = problem_type if problem_type in by_type else schema.get("problem_type")
    # Chỉ dataset có cột ngày giờ mới có khoá này - hồ sơ của dataset khác giữ nguyên.
    extra = {key: schema[key] for key in ("time_columns", "time_series_note") if schema.get(key)}
    return {
        "dataset_id": schema.get("dataset_id"),
        "data_name": schema.get("data_name"),
        "problem_type": known,
        "total_rows": schema.get("total_rows"),
        "column_count": schema.get("column_count"),
        "target_candidates": by_type.get(known) if known else schema.get("target_candidates"),
        "target_candidates_by_type": by_type,
        "columns": [
            {
                "name": c.get("name"),
                "type": c.get("python_type"),
                "distinct": c.get("distinct_in_preview"),
                "missing": c.get("missing_in_preview"),
                "target_for": c.get("target_for"),
                "samples": (c.get("sample_values") or [])[:_SAMPLES_PER_COLUMN],
            }
            for c in columns[:_MAX_PROFILE_COLUMNS]
        ],
        "columns_truncated": len(columns) > _MAX_PROFILE_COLUMNS,
        # Dataset rộng: thống kê chỉ cho 60 cột đầu nhưng TÊN thì đủ hết - thiếu nó
        # thì "dùng tất cả các cột còn lại" bị lặng lẽ cắt còn 60 cột.
        **({"all_column_names": [c.get("name") for c in columns]} if len(columns) > _MAX_PROFILE_COLUMNS else {}),
        "note": (
            "distinct/missing tính trên 50 dòng preview, không phải toàn bộ dataset. "
            "target_for: loại bài toán mà cột đó làm biến mục tiêu được."
            + (
                f" Chỉ {_MAX_PROFILE_COLUMNS} cột đầu có thống kê; all_column_names là ĐỦ mọi cột - "
                "chọn đặc trưng theo danh sách đó."
                if len(columns) > _MAX_PROFILE_COLUMNS else ""
            )
        ),
        **extra,
    }


def _intish(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_requirements(raw: dict, datasets: list[dict] | None) -> tuple[dict, list, list]:
    """
    Soát R do Prompt Agent sinh ra bằng code.

    LLM có thể chép sai ID, bịa loại bài toán, hoặc viết ràng buộc lung tung.
    Hàm này ép R về đúng 6 khoá, chỉ giữ dataset ID có thật trong kho của người
    dùng, và chỉ giữ ràng buộc có dạng so sánh được.

    Returns:
        (R, missing, notes) - missing là câu cần hỏi lại người dùng, notes là
        những gì code đã tự sửa/suy ra (để Manager nói lại cho người dùng).
    """
    requirements = {
        key: dict(raw.get(key)) if isinstance(raw.get(key), dict) else {}
        for key in REQUIREMENT_KEYS
    }
    # Model đôi khi trả "missing" là một câu thay vì danh sách - lặp thẳng qua
    # chuỗi sẽ ra từng ký tự.
    raw_missing = raw.get("missing") or []
    if isinstance(raw_missing, str):
        raw_missing = [raw_missing]
    elif not isinstance(raw_missing, list):
        raw_missing = []
    missing = [str(item).strip() for item in raw_missing if str(item).strip()]
    notes: list[str] = []

    if datasets is None:
        # Không đọc được danh sách dataset: giữ nguyên dataset id người dùng nêu, không kết luận
        # "chưa có dataset" (bước sau - Data / Model Agent - sẽ báo nếu id sai).
        notes.append("Không đọc được danh sách dataset lúc này - chưa kiểm được dataset id.")
        datasets_known = False
        datasets = []
    else:
        datasets_known = True
    by_id = {d["id"]: d for d in datasets if d.get("id")}
    dataset = requirements["dataset"]
    intent = str(requirements["user"].get("intent") or "").lower()

    # Mẫu cần dự đoán gửi sau khi train xong cũng được, không chặn việc train.
    # Đã gặp: Prompt Agent ghi "Mẫu dữ liệu cần dự đoán chưa được cung cấp" vào
    # missing, Manager dừng lại hỏi nên lượt đó không train.
    if intent == "train":
        blocking = [item for item in missing if not _ASKS_FOR_PREDICT_ROWS.search(item)]
        if len(blocking) < len(missing):
            notes.append("Chưa có mẫu cần dự đoán: vẫn train trước, xin mẫu khi job xong.")
            missing = blocking

    # --- dataset: chỉ nhận ID có thật ---
    dataset_id = dataset.get("id")
    if dataset_id and datasets_known and dataset_id not in by_id:
        name = str(dataset.get("name") or "").strip().lower()
        matches = [d for d in datasets if name and str(d.get("name") or "").lower() == name]
        if len(matches) == 1:
            dataset["id"] = matches[0]["id"]
            notes.append(f"Sửa dataset id theo tên '{matches[0]['name']}'.")
        else:
            dataset["id"] = None
            notes.append(f"Bỏ dataset id '{dataset_id}' vì không có trong kho của người dùng.")

    if not dataset.get("id") and intent in ("train", "analyze") and datasets_known:
        if not datasets:
            missing.append("Người dùng chưa có dataset nào - cần tải dataset lên trước.")
        elif len(datasets) == 1:
            dataset["id"] = datasets[0]["id"]
            notes.append(f"Người dùng chỉ có một dataset nên dùng '{datasets[0]['name']}'.")
        elif not any("dataset" in item.lower() for item in missing):
            names = ", ".join(f"'{d['name']}'" for d in datasets[:10])
            missing.append(f"Dùng dataset nào? Người dùng đang có: {names}.")

    known = by_id.get(dataset.get("id"))
    if known:
        dataset["name"] = known.get("name")

    # --- problem ---
    # Dataset không mang loại bài toán; không rõ thì để None, Model Agent suy
    # từ cột mục tiêu.
    problem = requirements["problem"]
    problem_type = str(problem.get("type") or "").strip().lower()
    problem["type"] = problem_type if problem_type in PROBLEM_TYPES else None
    if problem_type and not problem["type"]:
        notes.append(f"Loại bài toán '{problem_type}' không hỗ trợ, để Model Agent suy từ cột mục tiêu.")

    preferred = problem.get("metric")
    if preferred:
        problem["metric"] = normalize_metric(preferred, problem["type"])
        if problem["metric"] is None:
            notes.append(f"Hệ thống không có metric '{preferred}', để Model Agent tự chọn.")
        elif problem["metric"] != str(preferred).strip().lower():
            notes.append(f"Hiểu metric '{preferred}' là '{problem['metric']}'.")

    raw_constraints = problem.get("constraints")
    constraints = []
    dropped_constraints = False
    if raw_constraints is None:
        raw_constraints = []
    if not isinstance(raw_constraints, list):
        notes.append(f"Bỏ ràng buộc không đọc được: {raw_constraints!r}.")
        dropped_constraints = True
    for item in raw_constraints if isinstance(raw_constraints, list) else []:
        if not isinstance(item, dict):
            notes.append(f"Bỏ ràng buộc không đọc được: {item!r}.")
            dropped_constraints = True
            continue
        op = str(item.get("op") or "").strip()
        try:
            value = float(item.get("value"))
        except (TypeError, ValueError):
            value = None
        if op not in _CONSTRAINT_OPS or value is None:
            notes.append(f"Bỏ ràng buộc không so sánh được: {item}.")
            dropped_constraints = True
            continue
        metric = normalize_metric(item.get("metric"), problem["type"])
        if metric is None:
            notes.append(
                f"Bỏ ràng buộc theo metric '{item.get('metric')}' vì hệ thống không tính metric "
                "này - không kiểm định được."
            )
            dropped_constraints = True
            continue
        value, note = scale_constraint_value(metric, value)
        if value is None:
            notes.append(f"Bỏ ràng buộc {item}: {note}")
            dropped_constraints = True
            continue
        if note:
            notes.append(note)
        constraints.append({"metric": metric, "op": op, "value": value})
    problem["constraints"] = constraints

    max_time = _intish(problem.get("max_time"))
    problem["max_time"] = max_time if max_time and 60 <= max_time <= 86400 else None

    algorithm = requirements["model"].get("search_algorithm")
    if algorithm not in SEARCH_ALGORITHMS:
        requirements["model"]["search_algorithm"] = None

    # watcher tự kích hoạt model khi service.deploy đúng: chuỗi "false" không được thành True.
    service = requirements["service"]
    for flag in ("deploy", "predict"):
        value = service.get(flag)
        service[flag] = value is True or str(value).strip().lower() == "true"
    # Người dùng đặt điều kiện mà hệ thống không kiểm được ("chỉ kích hoạt nếu RMSE <= 1" với
    # regression): ràng buộc đó đã bị bỏ ở trên, nên tự kích hoạt sẽ thành vô điều kiện. Không làm.
    if service["deploy"] and dropped_constraints:
        service["deploy"] = False
        notes.append(
            "Không tự kích hoạt model: có ràng buộc người dùng đặt mà hệ thống không kiểm được. "
            "Báo người dùng; khi job xong họ tự quyết định có kích hoạt không."
        )

    return requirements, missing, notes


@dataclass
class Handoff:
    """Dữ liệu đi giữa các agent trong một phiên chat."""

    # R mới nhất từ Prompt Agent.
    requirements: dict | None = None
    # dataset_id -> kết quả get_dataset_schema mà Data Agent đã đọc.
    profiles: dict = field(default_factory=dict)
    # config_id -> config đã qua validate_config, do Model Agent chốt.
    configs: dict = field(default_factory=dict)
    # job_id -> config_id đã sinh ra job đó.
    jobs: dict = field(default_factory=dict)


class AgentTeam:
    """
    Dựng tool cho từng agent và chạy sub-agent khi Manager giao việc.

    Sống trong ChatSession: dùng chung client API (token người dùng), client
    LLM, bộ đếm token và kênh sự kiện của phiên.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.handoff = Handoff()
        # job_id -> số tin người dùng lúc tự kích hoạt bị huỷ (bật lại cần lời mới hơn mốc này).
        self._auto_cancelled_at: dict[str, int] = {}
        # job_id -> số tin người dùng lúc HỆ THỐNG huỷ lời hứa vì điều kiện không kiểm được: trong
        # đúng lượt đó được bật lại kèm điều kiện hợp lệ (người dùng vừa yêu cầu), không kèm thì không.
        self._system_cancelled_at: dict[str, int] = {}
        # Mốc huỷ (_auto_cancelled_at) ngay TRƯỚC lần hệ thống huỷ - cửa sổ đồng ý của lần thử lại.
        self._system_prev_mark: dict[str, int] = {}
        # Thay đổi tự kích hoạt do LLM làm trong lượt đang chạy - lượt lỗi thì phải báo lại.
        self._turn_auto_changes: list[tuple[str, bool]] = []
        # Kiểm đồng ý + đổi trạng thái tự kích hoạt + ghi mốc huỷ phải liền một khối: không thì
        # tool vừa qua bước kiểm, người dùng bấm Huỷ, tool lại bật lên như chưa có lần huỷ.
        self._auto_lock = threading.Lock()
        # Lệnh tạo job chưa rõ kết quả, theo dataset + cấu hình (không theo config_id: chốt lại
        # cùng cấu hình là ra config_id mới). Không xoá khi reset - job có thể đã tồn tại thật.
        self._unresolved_creates: list[dict] = []
        self._turn_unknown_creates: list[str] = []

    def begin_turn(self) -> None:
        self._turn_auto_changes = []
        self._turn_unknown_creates = []

    def after_failed_turn(self) -> list[str]:
        """
        Lượt chat lỗi bị bỏ khỏi lịch sử: kẹp mốc huỷ về số tin người dùng còn lại (tin của lượt
        lỗi không còn - không kẹp thì lời "kích hoạt lại" ở lượt sau bị coi là CŨ hơn lần huỷ).
        Trả câu báo cho các thay đổi tự kích hoạt đã thật sự xảy ra trong lượt đó.
        """
        self.clamp_auto_marks()
        notes = [
            f"Lượt chat trước bị lỗi giữa chừng NHƯNG đã {'BẬT' if enabled else 'HUỶ'} tự kích hoạt model cho job "
            f"{job_id}. Báo người dùng trạng thái này."
            for job_id, enabled in self._turn_auto_changes
        ] + self._turn_unknown_creates
        self._turn_auto_changes = []
        self._turn_unknown_creates = []
        return notes

    def clamp_auto_marks(self) -> None:
        """
        Kẹp mốc huỷ về số tin người dùng còn trong lịch sử (lượt lỗi bị bỏ, hoặc tin đã nhận nhưng
        không bao giờ vào lịch sử). Cùng khoá với change_auto_activate: nút Huỷ (luồng event loop)
        ghi mốc đúng lúc này thì không bị mất, và dict không đổi kích thước giữa lúc duyệt.
        """
        with self._auto_lock:
            remaining = len(self._user_messages())
            self._auto_cancelled_at = {
                job_id: min(mark, remaining) for job_id, mark in self._auto_cancelled_at.items()
            }
            # Mốc "hệ thống vừa huỷ trong lượt này" của lượt lỗi: lượt đó đã bị bỏ - không để lượt sau
            # trùng số tin mà được coi là chính lượt ấy.
            self._system_cancelled_at = {
                job_id: mark for job_id, mark in self._system_cancelled_at.items() if mark <= remaining
            }
            self._system_prev_mark = {
                job_id: min(mark, remaining) for job_id, mark in self._system_prev_mark.items()
                if job_id in self._system_cancelled_at
            }

    def reset(self) -> None:
        self.handoff = Handoff()
        # Lịch sử được làm lại từ đầu: mọi tin sau reset đều mới hơn lần huỷ.
        with self._auto_lock:
            self._auto_cancelled_at = {job_id: 0 for job_id in self._auto_cancelled_at}
            self._system_cancelled_at = {}
            self._system_prev_mark = {}

    # ------------------------------------------------------------------ dispatch

    def tools_for(self, agent: str) -> tuple[list, dict]:
        """Schema + hàm của đúng các tool khai trong SKILL.md của agent."""
        names = skills_module.get_skill(agent).tools
        bound = {
            "ask_prompt_agent": self.ask_prompt_agent,
            "ask_data_agent": self.ask_data_agent,
            "ask_model_agent": self.ask_model_agent,
            "ask_operation_agent": self.ask_operation_agent,
            "get_dataset_schema": self.get_dataset_schema,
            "submit_config": self.submit_config,
            "start_training": self.start_training,
            "watch_job": self.watch_job,
            "set_auto_activate": self.set_auto_activate,
        }
        dispatch = {
            name: bound.get(name) or _DISPATCH[name]
            for name in names
            if name in bound or name in _DISPATCH
        }
        return schemas_for(names), dispatch

    def _emit(self, type: str, **data) -> None:
        self.session.events.emit(type, **data)

    # ------------------------------------------------------------ chạy sub-agent

    def _run_subagent(self, agent: str, task: str, context: str = "") -> dict:
        """Chạy một sub-agent tới khi nó báo cáo xong. Không raise."""
        schemas, dispatch = self.tools_for(agent)
        messages = [
            {"role": "system", "content": prompts.agent_prompt(agent, context)},
            {"role": "user", "content": task},
        ]

        self._emit("agent_start", agent=agent, task=task[:300])
        with tracing.observe(agent, as_type="agent", input={"task": task, "context": context}) as observation:
            result = self._run_loop(agent, messages, schemas, dispatch)
            tracing.end(observation, output=result.get("report"), error=result.get("error"))
        return result

    def _run_loop(self, agent: str, messages: list, schemas: list, dispatch: dict) -> dict:
        try:
            report = run_tool_loop(
                self.session.llm,
                self.session.config.model,
                messages,
                schemas,
                dispatch,
                self.session.api,
                self.session.usage,
                agent=agent,
                emit=self.session.events.emit,
                max_steps=SUBAGENT_MAX_STEPS,
                check_budget=self.session.check_budget,
            )
        except Exception as error:  # noqa: BLE001 - sub-agent hỏng không được làm chết Manager
            # Vượt trần token cũng về đây (không raise tiếp: Manager đang giữ một
            # tool_call chờ kết quả). Manager tự dừng ở lần kiểm trần kế tiếp.
            if isinstance(error, TurnBudgetExceeded):
                message = f"{prompts.title(agent)} dừng vì lượt chat đã vượt trần token: {error}"
            else:
                log_exception(_log, "%s lỗi", agent)
                message = f"{prompts.title(agent)} lỗi khi gọi LLM: {describe_error(error)}"
            self._emit("agent_done", agent=agent, ok=False, error=message)
            return {"ok": False, "agent": agent, "error": message}

        if report is None:
            message = f"{prompts.title(agent)} chạy quá {SUBAGENT_MAX_STEPS} bước mà chưa xong."
            self._emit("agent_done", agent=agent, ok=False, error=message)
            return {"ok": False, "agent": agent, "error": message}

        self._emit("agent_done", agent=agent, ok=True)
        return {"ok": True, "agent": agent, "report": report}

    def _ask_json(self, agent: str, system: str, user: str) -> dict:
        """Một lượt LLM không tool, bắt buộc trả JSON. Hỏng thì nhắc sửa đúng một lần."""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        for attempt in range(2):
            self.session.check_budget(agent)
            response = create_completion(
                self.session.llm, model=self.session.config.model, messages=messages,
            )
            _accumulate_usage(self.session.usage, response.usage)
            if response.usage is not None:
                self._emit(
                    "llm_call",
                    agent=agent,
                    prompt_tokens=response.usage.prompt_tokens or 0,
                    completion_tokens=response.usage.completion_tokens or 0,
                    total_tokens=response.usage.total_tokens or 0,
                )

            text = response.choices[0].message.content or ""
            try:
                return parse_json(text)
            except ValueError as error:
                if attempt:
                    raise AgentOutputError(f"{prompts.title(agent)} không trả JSON hợp lệ: {error}") from error
                messages += [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": (
                        f"Câu trả lời không phải JSON hợp lệ ({error}). Trả lại DUY NHẤT một "
                        "object JSON đúng định dạng đã yêu cầu, không kèm chữ nào khác."
                    )},
                ]
        raise AgentOutputError(f"{prompts.title(agent)} không trả JSON hợp lệ")

    # ------------------------------------------------- tool của Agent Manager

    def ask_prompt_agent(self, api, request: str) -> dict:
        """① Prompt Agent: chuẩn hoá yêu cầu thành R. Không tool, một lượt JSON."""
        listing = tools.list_my_datasets(api)
        # Không đọc được danh sách: None (KHÁC "chưa có dataset nào" - nói vậy là người dùng tải lại
        # và ra dataset trùng).
        datasets = [
            {"id": d.get("_id"), "name": d.get("dataName")}
            for d in (listing.get("datasets") or [])
        ] if listing.get("ok") else None

        context = json.dumps(
            {
                "datasets_of_user": datasets if datasets is not None else "KHÔNG đọc được danh sách dataset lúc này",
                "recent_user_messages": self.session.recent_user_messages(_RECENT_USER_MESSAGES),
            },
            ensure_ascii=False,
            indent=1,
        )

        self._emit("agent_start", agent=PROMPT_AGENT, task=request[:300])
        with tracing.observe(PROMPT_AGENT, as_type="agent", input={"request": request, "context": context}) as observation:
            try:
                raw = self._ask_json(PROMPT_AGENT, prompts.agent_prompt(PROMPT_AGENT, context), request)
            except TurnBudgetExceeded as error:
                message = f"Prompt Agent dừng vì lượt chat đã vượt trần token: {error}"
                self._emit("agent_done", agent=PROMPT_AGENT, ok=False, error=message)
                tracing.end(observation, error=message)
                return {"ok": False, "agent": PROMPT_AGENT, "error": message}
            except Exception as error:  # noqa: BLE001
                log_exception(_log, "prompt-agent lỗi")
                message = f"Prompt Agent lỗi: {describe_error(error)}"
                self._emit("agent_done", agent=PROMPT_AGENT, ok=False, error=message)
                tracing.end(observation, error=message)
                return {"ok": False, "agent": PROMPT_AGENT, "error": message}

            requirements, missing, notes = normalize_requirements(raw, datasets)
            # service.deploy làm watcher TỰ kích hoạt model - một hành động thật trên hệ thống.
            # LLM có thể bịa cờ này hoặc mang nó từ một yêu cầu cũ: chỉ giữ khi vài tin gần
            # nhất của người dùng thật sự nói tới việc kích hoạt / triển khai.
            if requirements["service"].get("deploy") and not _mentions_activation(
                self.session.recent_user_messages(_RECENT_USER_MESSAGES)
            ):
                requirements["service"]["deploy"] = False
                notes.append(
                    "Sẽ KHÔNG tự kích hoạt model sau khi train: người dùng không nhắc gì tới kích hoạt. "
                    "Nếu họ có vẻ muốn dùng model ngay thì đề nghị kích hoạt khi job xong."
                )
            # Ghi cả bản LLM trả lẫn bản sau khi code soát, để thấy code đã sửa gì.
            tracing.end(observation, output={"raw": raw, "requirements": requirements, "missing": missing, "notes": notes})

        self.handoff.requirements = requirements
        self._emit("agent_done", agent=PROMPT_AGENT, ok=True, missing=missing)

        return {
            "ok": True,
            "agent": PROMPT_AGENT,
            "requirements": requirements,
            "missing": missing,
            "notes": notes,
            "clear": not missing,
        }

    def ask_data_agent(self, api, task: str, dataset_id: str = "") -> dict:
        """② Data Agent: tra cứu dataset. Schema nó đọc được giữ lại cho Model Agent."""
        if dataset_id:
            task = f"{task}\n\ndataset_id: {dataset_id}"

        context = ""
        requirements = self.handoff.requirements
        if requirements and requirements["problem"].get("type"):
            context = f"Loại bài toán người dùng nhắm tới: {requirements['problem']['type']}."

        before = set(self.handoff.profiles)
        result = self._run_subagent(DATA_AGENT, task, context)
        result["profiled_datasets"] = sorted(set(self.handoff.profiles) - before)
        return result

    def _check_dataset_id(self, api, dataset_id: str) -> dict | None:
        """
        Đối chiếu dataset_id với kho thật của người dùng. Sai thì trả lỗi kèm ID đúng.

        LLM hay chép sai ID dài (đã gặp: rơi mất 6 ký tự giữa 24 ký tự hex).
        Backend chỉ báo "not a valid ObjectId" - không giúp LLM sửa được; trả kèm
        danh sách ID thật thì lần gọi sau nó chép lại đúng.
        """
        listing = tools.list_my_datasets(api)
        if not listing.get("ok"):
            return None  # không kiểm được thì để bước sau tự báo lỗi
        datasets = [
            {"id": d.get("_id"), "name": d.get("dataName")}
            for d in listing.get("datasets") or []
        ]
        if any(d["id"] == dataset_id for d in datasets):
            return None
        return {
            "ok": False,
            "agent": MODEL_AGENT,
            "error": (
                f"dataset_id '{dataset_id}' không có trong kho của người dùng (có thể chép sai). "
                "Gọi lại với một id NGUYÊN VĂN trong available_datasets."
            ),
            "available_datasets": datasets,
        }

    def ask_model_agent(self, api, task: str, dataset_id: str = "") -> dict:
        """
        ③ Model Agent: ra quyết định config từ R + hồ sơ dữ liệu. Không bấm chạy.

        Không có dataset_id = tư vấn chung (metric, model, thuật toán): chạy
        Model Agent không kèm hồ sơ dữ liệu, và nó không chốt config.
        """
        requirements = self.handoff.requirements or {}
        wanted_type = (requirements.get("problem") or {}).get("type") or ""
        dataset_id = (dataset_id or "").strip()

        if dataset_id:
            invalid = self._check_dataset_id(api, dataset_id)
            if invalid:
                return invalid

            profile = self.handoff.profiles.get(dataset_id)
            # Chưa có hồ sơ khi Manager bỏ qua Data Agent. Hồ sơ đã có ứng viên
            # target cho cả hai loại bài toán nên không phải đọc lại theo loại.
            if profile is None:
                profile = self.get_dataset_schema(api, dataset_id=dataset_id, problem_type=wanted_type)
                if not profile.get("ok"):
                    return {"ok": False, "agent": MODEL_AGENT, "error": profile.get("error")}
            data_section = json.dumps(profile_brief(profile, wanted_type), ensure_ascii=False, indent=1)
            task = f"{task}\n\ndataset_id: {dataset_id}"
        else:
            data_section = (
                "Không gắn dataset - đây là câu hỏi TƯ VẤN CHUNG. Trả lời bằng list_metrics / "
                "list_models / tài liệu tra cứu. KHÔNG gọi submit_config."
            )

        context = "\n\n".join([
            "## Yêu cầu đã chuẩn hoá (R, từ Prompt Agent)",
            json.dumps(requirements or "Chưa có - Manager chưa gọi Prompt Agent.", ensure_ascii=False, indent=1),
            "## Hồ sơ dữ liệu (từ Data Agent)",
            data_section,
        ])

        before = set(self.handoff.configs)
        result = self._run_subagent(MODEL_AGENT, task, context)
        # Model Agent submit lại trong cùng lần chạy thì config trước đã bị thay:
        # chỉ đưa Manager config còn hiệu lực, khỏi chuyển nhầm cho Operation Agent.
        result["configs"] = [
            {key: self.handoff.configs[cid][key] for key in ("config_id", "config", "warnings")}
            for cid in self.handoff.configs
            if cid not in before and not self.handoff.configs[cid].get("superseded_by")
        ]
        if result["ok"] and not result["configs"] and dataset_id:
            result["note"] = "Model Agent chưa chốt config nào - đọc report để biết còn thiếu gì."
        return result

    def ask_operation_agent(self, api, task: str) -> dict:
        """④ Operation Agent: chạy config đã kiểm, theo dõi job, kích hoạt, dự đoán."""
        ready = [
            {
                "config_id": entry["config_id"],
                "dataset_id": entry["dataset_id"],
                "config": entry["config"],
                "already_started_job": entry.get("job_id"),
                # Lần chạy trước chưa rõ đã tạo job hay chưa: KHÔNG chạy lại, kiểm list_my_jobs.
                "outcome_unknown": bool(entry.get("outcome_unknown")),
            }
            for entry in self.handoff.configs.values()
            # Config đã bị thay thế thì không đưa vào, Operation Agent khỏi chọn nhầm.
            if not entry.get("superseded_by")
        ]
        # list_my_jobs trả cả job cũ và job của phiên khác cùng tài khoản. Đã gặp:
        # phiên chưa tạo job nào mà người dùng hỏi "job vừa tạo", Operation Agent
        # lấy một job cũ trùng dataset và báo như job vừa chạy.
        own_jobs = [
            {
                "job_id": job_id,
                "config_id": config_id,
                "dataset_id": (self.handoff.configs.get(config_id) or {}).get("dataset_id"),
                # Có tự kích hoạt khi xong không (người dùng đổi ý thì dùng set_auto_activate), và trạng
                # thái lời hứa: pending / cancelled (người dùng đã huỷ) / expired (hết giờ theo dõi) /
                # activating / done / off (không ai yêu cầu).
                "auto_activate": self.session.watcher.auto_activate(job_id),
                "auto_activate_state": self.session.watcher.auto_state(job_id),
                # Điều kiện sẽ kiểm trước khi tự kích hoạt (rỗng = bất kể điểm).
                "auto_activate_constraints": self.session.watcher.checked_constraints(job_id),
            }
            for job_id, config_id in self.handoff.jobs.items()
        ]
        context = "\n\n".join([
            "## Config đã qua validate_config (chỉ chạy được các config_id này)",
            json.dumps(ready, ensure_ascii=False, indent=1) if ready else "Chưa có config nào.",
            '## Job do chính phiên chat này tạo ("job vừa tạo" chỉ là các job này)',
            json.dumps(own_jobs, ensure_ascii=False, indent=1) if own_jobs
            else "Chưa có - phiên chat này chưa tạo job nào.",
            "## Job đang được theo dõi nền",
            ", ".join(self.session.watcher.active()) or "Không có.",
        ])

        before = set(self.handoff.jobs)
        unresolved_before = {record["record_id"] for record in self._unresolved_creates}
        result = self._run_subagent(OPERATION_AGENT, task, context)
        result["jobs_started"] = sorted(set(self.handoff.jobs) - before)
        # Lệnh tạo job chưa rõ kết quả trong lần chạy này - báo cả khi Operation Agent lỗi sau đó,
        # không thì Manager bảo "thử lại" trong khi job có thể đang chạy.
        unknown = [record for record in self._unresolved_creates if record["record_id"] not in unresolved_before]
        if unknown:
            result["outcome_unknown_creates"] = [
                {"dataset_id": record["dataset_id"], "target": record["key"][0], "possible_job_ids": record["possible_job_ids"]}
                for record in unknown
            ]
        # job_id -> có tự kích hoạt khi xong không: Manager chỉ hứa điều code thật sự làm.
        result["auto_activate"] = {job_id: self.session.watcher.auto_activate(job_id) for job_id in self.handoff.jobs}
        # Điều kiện THẬT sự được kiểm trước khi tự kích hoạt (rỗng = kích hoạt bất kể điểm).
        result["auto_activate_constraints"] = {
            job_id: self.session.watcher.checked_constraints(job_id)
            for job_id, wanted in result["auto_activate"].items()
            if wanted
        }
        result["watching"] = self.session.watcher.active()
        return result

    # ------------------------------------------------- tool của sub-agent

    def get_dataset_schema(self, api, dataset_id: str, problem_type: str = "", sample_rows: int = 3) -> dict:
        """get_dataset_schema của Data Agent, giữ kết quả lại làm hồ sơ cho Model Agent."""
        result = tools.get_dataset_schema(api, dataset_id=dataset_id, problem_type=problem_type, sample_rows=sample_rows)
        if result.get("ok"):
            self.handoff.profiles[dataset_id] = result
        return result

    def submit_config(
        self,
        api,
        dataset_id: str,
        target: str,
        list_feature: list,
        metric_sort: str,
        problem_type: str = "",
        search_algorithm: str = tools.DEFAULT_SEARCH_ALGORITHM,
        max_time: int = tools.DEFAULT_MAX_TIME,
        rationale: str = "",
    ) -> dict:
        """Model Agent chốt config. Kiểm bằng validate_config.py; hợp lệ mới có config_id."""
        if not problem_type and self.handoff.requirements:
            problem_type = self.handoff.requirements["problem"].get("type") or ""

        with tracing.observe(
            "validate_config",
            as_type="guardrail",
            input={"dataset_id": dataset_id, "target": target, "list_feature": list_feature,
                   "metric_sort": metric_sort, "search_algorithm": search_algorithm, "max_time": max_time},
        ) as observation:
            prepared = self._unconfirmed_target(api, dataset_id, target) or tools.prepare_training_config(
                api,
                dataset_id=dataset_id,
                target=target,
                list_feature=list_feature,
                metric_sort=metric_sort,
                problem_type=problem_type,
                search_algorithm=search_algorithm,
                max_time=max_time,
            )
            tracing.end(
                observation,
                output={k: prepared.get(k) for k in ("ok", "config", "errors", "warnings")},
                warning=None if prepared.get("ok") else "Config bị chặn",
            )
        if not prepared.get("ok"):
            self._emit(
                "config_checked",
                agent=MODEL_AGENT,
                ok=False,
                errors=prepared.get("errors") or [prepared.get("error")],
            )
            return prepared

        # R có thể giữ ràng buộc theo metric của loại bài toán khác (R chưa rõ loại lúc
        # chuẩn hoá, vd "rmse" mà cuối cùng là regression): job sẽ không có điểm cho
        # metric đó, watcher không kiểm định được và không tự kích hoạt. Báo ngay.
        problem_type = prepared["config"]["problem_type"]
        computed = tools.list_metrics(api, problem_type).get("metrics") or []
        constraints = ((self.handoff.requirements or {}).get("problem") or {}).get("constraints") or []
        unverifiable = sorted({c["metric"] for c in constraints if c.get("metric") not in computed})
        stored_requirements = self._requirements_for(dataset_id)
        if unverifiable:
            prepared = {**prepared, "warnings": [*prepared["warnings"], (
                f"Ràng buộc theo {', '.join(unverifiable)} KHÔNG kiểm định được với {problem_type} "
                f"(engine chỉ tính {', '.join(computed)}). Báo người dùng; hệ thống sẽ không tự "
                "kích hoạt model theo ràng buộc này."
            )]}
            # Watcher không bao giờ kích hoạt khi có ràng buộc không kiểm được: báo đúng ngay
            # từ đầu (auto_activate = false), đừng để Manager hứa điều sẽ không xảy ra.
            if wants_deploy(stored_requirements):
                stored_requirements = _without_deploy(stored_requirements)

        config_id = f"cfg_{uuid.uuid4().hex[:6]}"
        # Config mới thay thế config cũ CHƯA chạy của cùng dataset: Manager giao
        # Model Agent hai lần thì chỉ quyết định mới nhất được chạy, tránh hai
        # job trùng nhau chiếm worker hàng giờ.
        for entry in self.handoff.configs.values():
            if entry["dataset_id"] == dataset_id and not entry.get("job_id"):
                entry["superseded_by"] = config_id
        self.handoff.configs[config_id] = {
            "config_id": config_id,
            "dataset_id": dataset_id,
            "config": prepared["config"],
            "warnings": prepared["warnings"],
            "rationale": rationale,
            # R lúc chốt config: watcher kiểm định job theo đúng R này, không theo R
            # mới hơn của một yêu cầu khác trong cùng phiên.
            "requirements": stored_requirements,
        }
        # Kèm config để frontend hiện được thẻ cấu hình cả khi job chưa chạy được.
        self._emit(
            "config_checked",
            agent=MODEL_AGENT,
            ok=True,
            errors=[],
            config_id=config_id,
            config=prepared["config"],
            warnings=prepared["warnings"],
        )
        return {
            "ok": True,
            "config_id": config_id,
            "config": prepared["config"],
            "warnings": prepared["warnings"],
            "note": (
                "Config đã qua validate_config. Báo config_id này cho Manager để chuyển "
                "Operation Agent chạy - bạn KHÔNG bấm chạy."
            ),
        }

    def _requirements_for(self, dataset_id: str) -> dict | None:
        """
        R áp cho config của dataset này.

        Tự kích hoạt (service.deploy) là hành động thật trên hệ thống: chỉ giữ khi R nói về
        CHÍNH dataset này (hoặc không nêu dataset) và vài tin gần nhất của người dùng vẫn có
        yêu cầu kích hoạt. Manager có thể bỏ qua Prompt Agent và dùng lại R của một yêu cầu
        cũ ("train A, xong kích hoạt" rồi vài lượt sau "giờ train B") - B không được tự kích hoạt.
        Ý đồng ý / từ chối do LLM hiểu; code chỉ đòi người dùng CÓ nhắc tới việc kích hoạt.
        """
        requirements = self.handoff.requirements
        if not requirements or not (requirements.get("service") or {}).get("deploy"):
            return requirements
        named = (requirements.get("dataset") or {}).get("id")
        if named in (None, dataset_id) and _mentions_activation(
            self.session.recent_user_messages(_RECENT_USER_MESSAGES)
        ):
            return requirements
        return _without_deploy(requirements)

    def _unconfirmed_target(self, api, dataset_id: str, target: str) -> dict | None:
        """
        Chặn tự chọn cột mục tiêu: người dùng phải nói ra, hoặc dataset chỉ có một ứng viên.

        SKILL.md đã dặn "nhiều ứng viên thì hỏi" nhưng LLM vẫn có lúc bỏ qua (đã
        gặp: Data Agent gợi ý "Age hợp lý nhất", Manager chép thành việc giao,
        Model Agent submit Age và job chạy dù người dùng chưa chọn). Người dùng
        nói ra = có trong R, hoặc tin gần đây của người dùng nói rõ cột đó là cột
        cần dự đoán (lượt sau mới bổ sung "target là Age" thì R có thể chưa cập
        nhật) - chỉ nhắc tên cột thì không tính, xem _named_targets.

        Returns:
            None nếu được dùng cột này, ngược lại là lỗi trả cho Model Agent.
        """
        target = (target or "").strip()
        if not target:
            return None  # validate_config tự báo thiếu target
        problem = (self.handoff.requirements or {}).get("problem") or {}
        if str(problem.get("target") or "").strip().lower() == target.lower():
            return None

        schema = self.handoff.profiles.get(dataset_id) or tools.get_dataset_schema(api, dataset_id=dataset_id)
        if not schema.get("ok"):
            return None  # không đọc được dữ liệu thì để validate_config báo lỗi
        by_type = schema.get("target_candidates_by_type") or {}
        kind = problem.get("type")
        candidates = by_type[kind] if kind in by_type else list(dict.fromkeys(
            name for names in by_type.values() for name in names
        ))
        if len(candidates) <= 1:
            return None

        columns = [c["name"] for c in schema.get("columns") or []]
        if target.lower() not in {name.lower() for name in columns}:
            return None  # cột không có thật: validate_config báo đúng lỗi đó
        for message in self.session.recent_user_messages(_RECENT_USER_MESSAGES):
            text = "\n".join(line for line in message.splitlines() if not line.startswith(_EVENT_PREFIX))
            if target.lower() in {name.lower() for name in _named_targets(text, columns)}:
                return None
        return {
            "ok": False,
            "error": (
                f"Người dùng chưa chọn cột mục tiêu, dataset có {len(candidates)} cột làm mục tiêu "
                f"được. KHÔNG submit lại với cột khác: dừng và báo Manager hỏi người dùng chọn một "
                "cột trong target_candidates. Có cột đáng gợi ý thì nêu là gợi ý, không phải đã chốt."
            ),
            "target_candidates": candidates,
        }

    def start_training(self, api, config_id: str) -> dict:
        """Operation Agent chạy config theo config_id. Không nhận config tự điền."""
        entry = self.handoff.configs.get(config_id)
        if entry is None:
            return {
                "ok": False,
                "error": (
                    f"Không có config '{config_id}'. Chỉ chạy được config đã được Model Agent "
                    "chốt qua submit_config (đã kiểm bằng validate_config)."
                ),
                "available_config_ids": sorted(self.handoff.configs),
            }
        if entry.get("job_id"):
            return {
                "ok": False,
                "error": f"Config '{config_id}' đã chạy thành job {entry['job_id']}. Không chạy lại trùng.",
                "job_id": entry["job_id"],
            }
        if entry.get("outcome_unknown"):
            return {
                "ok": False,
                "outcome_unknown": True,
                "error": (
                    f"Lần chạy trước của config '{config_id}' chưa rõ đã tạo job hay chưa - KHÔNG chạy lại "
                    "(có thể ra job trùng). Kiểm tra list_my_jobs; có job khớp thì watch_job; chắc chắn "
                    "không có thì nhờ Model Agent chốt lại config."
                ),
            }
        blocked = self._blocked_by_unresolved_create(api, entry)
        if blocked:
            return blocked
        if entry.get("superseded_by"):
            return {
                "ok": False,
                "error": (
                    f"Config '{config_id}' đã bị thay bằng config mới hơn "
                    f"'{entry['superseded_by']}' của cùng dataset. Chạy config mới đó."
                ),
                "config_id": entry["superseded_by"],
            }

        # Người dùng rút lại yêu cầu kích hoạt sau lúc chốt config ("à thôi đừng kích hoạt") và
        # Prompt Agent đã dựng lại R cho CÙNG dataset này với deploy = false: theo R mới nhất.
        current = self.handoff.requirements or {}
        if (
            wants_deploy(entry.get("requirements"))
            and (current.get("dataset") or {}).get("id") == entry["dataset_id"]
            and not wants_deploy(current)
        ):
            entry["requirements"] = _without_deploy(entry["requirements"])

        config = entry["config"]
        attempt_started = time.time()
        result = tools.start_training(
            api,
            dataset_id=entry["dataset_id"],
            target=config["target"],
            list_feature=config["list_feature"],
            metric_sort=config["metric_sort"],
            problem_type=config["problem_type"],
            search_algorithm=config["search_algorithm"],
            max_time=config["max_time"],
        )
        if result.get("outcome_unknown"):
            entry["outcome_unknown"] = True
            self._unresolved_creates.append({
                "record_id": uuid.uuid4().hex,
                "dataset_id": entry["dataset_id"], "key": _config_key(config), "started_at": attempt_started,
                "possible_job_ids": result.get("possible_job_ids") or [],
            })
            self._turn_unknown_creates.append(
                f"Lượt chat trước bị lỗi giữa chừng NHƯNG đã gửi lệnh tạo job cho dataset {entry['dataset_id']} "
                f"(target {config['target']}) mà chưa rõ kết quả; job có thể đã được tạo "
                f"({', '.join(result.get('possible_job_ids') or []) or 'chưa thấy trong danh sách'}). KHÔNG chạy "
                "lại; kiểm tra list_my_jobs trước."
            )
        if not result.get("ok") or not result.get("job_id"):
            return result

        job_id = result["job_id"]
        entry["job_id"] = job_id
        self.handoff.jobs[job_id] = config_id
        self._emit(
            "job_started", agent=OPERATION_AGENT, job_id=job_id, config_id=config_id,
            dataset_id=entry["dataset_id"], config=config, auto_activate=wants_deploy(entry.get("requirements")),
        )
        self.session.watcher.watch(
            job_id,
            max_time=config.get("max_time"),
            requirements=entry.get("requirements"),
            trace_context=tracing.current_context(),
            dataset_id=entry["dataset_id"],
            problem_type=config.get("problem_type"),
        )

        result["watching"] = True
        # Manager chỉ được hứa tự kích hoạt khi cờ này true.
        result["auto_activate"] = self.session.watcher.auto_activate(job_id)
        result["note"] = (
            "Job đã vào hàng đợi và chạy nền. Hệ thống tự theo dõi tới khi xong và báo "
            "cho người dùng - KHÔNG có kết quả ngay."
        )
        return result

    def _blocked_by_unresolved_create(self, api, entry: dict) -> dict | None:
        """
        Đã có lệnh tạo job CÙNG dataset + cấu hình chưa rõ kết quả: không gửi lệnh thứ hai khi
        chưa chắc lần trước không tạo được job (sẽ ra job trùng chạy hàng giờ).

        Có job khớp (tạo sau lần gửi đó) -> từ chối, trả job đó để theo dõi. Chưa thấy mà mới
        chưa tới _UNRESOLVED_RECHECK_SECONDS -> từ chối, đợi. Quá lâu vẫn không thấy -> lần
        trước coi như chưa tạo được: cho chạy, xoá ghi nhận.
        """
        key = _config_key(entry["config"])
        for record in list(self._unresolved_creates):
            if record["dataset_id"] != entry["dataset_id"] or record["key"] != key:
                continue
            found = tools.possible_jobs(api, entry["dataset_id"], entry["config"], record["started_at"])
            if found is None:
                # Không đọc được danh sách job: KHÔNG phải "không có job" - chưa kiểm được thì chưa cho.
                return {
                    "ok": False,
                    "outcome_unknown": True,
                    "error": (
                        "Lệnh tạo job trước với CÙNG cấu hình chưa rõ kết quả và hiện không đọc được danh sách "
                        "job để kiểm. Thử lại sau - đừng chạy lại khi chưa kiểm được."
                    ),
                }
            running = [job["job_id"] for job in found if job.get("status") == tools.JOB_RUNNING]
            if running:
                return {
                    "ok": False,
                    "outcome_unknown": True,
                    "possible_job_ids": running,
                    "error": (
                        f"Lệnh tạo job trước với CÙNG cấu hình chưa rõ kết quả và có job khớp ĐANG CHẠY: "
                        f"{', '.join(running)}. KHÔNG chạy lại - watch_job job đó."
                    ),
                }
            if found:
                # Job khớp đã kết thúc: lần gửi trước đã có kết quả - chạy lại giờ là ý người dùng.
                self._unresolved_creates.remove(record)
                continue
            waited = time.time() - record["started_at"]
            if waited < _UNRESOLVED_RECHECK_SECONDS:
                return {
                    "ok": False,
                    "outcome_unknown": True,
                    "error": (
                        f"Lệnh tạo job trước với CÙNG cấu hình chưa rõ kết quả (mới {int(waited)} giây). Đợi ít nhất "
                        f"{_UNRESOLVED_RECHECK_SECONDS} giây rồi kiểm tra list_my_jobs; không có job khớp thì mới chạy lại."
                    ),
                }
            self._unresolved_creates.remove(record)
        return None

    def set_auto_activate(self, api, job_id: str, enabled: bool = False, constraints=None) -> dict:
        """
        Bật/tắt tự kích hoạt cho một job đang chạy (người dùng đổi ý: "à thôi đừng kích hoạt").

        Bật lại chỉ được khi người dùng có nhắc tới việc kích hoạt - LLM không tự bật.
        constraints: điều kiện người dùng nêu kèm khi bật ("đạt accuracy >= 0.9 thì kích hoạt") -
        được kiểm lúc job xong. Điều kiện không kiểm được thì KHÔNG bật (bật là kích hoạt bất kể điểm).
        """
        enabled = tools.as_bool(enabled)
        if enabled is None:
            return self._auto_refusal(job_id, "enabled phải là true hoặc false.")
        added, notes = None, []
        if enabled and constraints not in (None, []):
            added, notes, problem, transient = self._activation_constraints(api, job_id, constraints)
            if problem:
                # Lời hứa đang bật mà điều kiện mới không áp được (điều kiện sai, hay tạm không đọc được
                # job): để nguyên thì job xong vẫn kích hoạt theo điều kiện CŨ mà người dùng vừa đổi -
                # huỷ cho chắc, nói rõ. Thử lại trong cùng lượt với điều kiện hợp lệ thì bật lại được.
                if self.change_auto_activate(job_id, False, by_button=False, only_if_pending=True, system=True) == "ok":
                    problem += (
                        " Đã HUỶ tự kích hoạt đang bật của job này (chưa áp được điều kiện người dùng vừa đặt)"
                        + ("; thử lại set_auto_activate với cùng điều kiện khi đọc được job." if transient else ".")
                    )
                return self._auto_refusal(job_id, problem)
        outcome = self.change_auto_activate(job_id, enabled, by_button=False, constraints=added)
        if outcome == "no_request":
            if self.session.watcher.auto_state(job_id) == "pending":
                return self._auto_refusal(job_id, (
                    "Điều kiện mới NỚI LỎNG điều kiện người dùng đã đồng ý mà người dùng không yêu cầu - giữ "
                    "nguyên. Hỏi lại người dùng nếu họ muốn đổi."
                ))
            return self._auto_refusal(job_id, "Người dùng không yêu cầu kích hoạt (kể từ lần huỷ gần nhất) - không tự bật.")
        if outcome == "needs_constraints":
            return self._auto_refusal(job_id, (
                "Tự kích hoạt vừa bị huỷ vì điều kiện người dùng đặt không kiểm được - chỉ bật lại kèm constraints "
                "hợp lệ (metric job có điểm). Không bật vô điều kiện khi người dùng vừa đặt điều kiện."
            ))
        if outcome != "ok":
            return self._auto_refusal(job_id, _AUTO_ACTIVATE_REFUSED[outcome].format(job_id=job_id))
        result = {"ok": True, "job_id": job_id, "auto_activate": enabled}
        if notes:
            result["notes"] = notes
        if enabled:
            # Báo đúng điều kiện sẽ được kiểm - Manager không được hứa điều kiện hệ thống không kiểm.
            checked = self.session.watcher.checked_constraints(job_id)
            result["checked_constraints"] = checked
            result["note"] = (
                "Khi job xong chỉ kích hoạt nếu đạt MỌI ràng buộc trong checked_constraints."
                if checked else
                "Không có ràng buộc nào: model sẽ được kích hoạt khi job xong BẤT KỂ điểm. Người dùng "
                "có đặt điều kiện thì gọi lại với constraints."
            )
        return result

    def _auto_refusal(self, job_id: str, error: str) -> dict:
        """Lỗi của set_auto_activate kèm trạng thái THẬT (lỗi không có nghĩa là đã tắt)."""
        watcher = self.session.watcher
        return {
            "ok": False,
            "error": error,
            "job_id": job_id,
            "auto_activate_state": watcher.auto_state(job_id),
            "checked_constraints": watcher.checked_constraints(job_id),
        }

    def _activation_constraints(self, api, job_id: str, raw) -> tuple[list[dict] | None, list[str], str | None, bool]:
        """
        Chuẩn hoá điều kiện kích hoạt theo metric job thật sự tính.
        Trả (ràng buộc, ghi chú, lỗi, lỗi tạm?) - lỗi khác None thì không dùng được; lỗi tạm là
        không đọc được job (thử lại được), khác với điều kiện sai.
        """
        if not isinstance(raw, list):
            return None, [], "constraints phải là danh sách {metric, op, value}. Chưa bật tự kích hoạt.", False
        job, problem = tools.find_own_job(api, job_id)
        if problem:
            return None, [], (
                f"Không đọc được job để kiểm điều kiện ({problem.get('error')}). Chưa áp được điều kiện."
            ), True
        problem_type = str((job.get("config") or {}).get("problem_type") or "").strip().lower()
        computed = tools.list_metrics(api, problem_type).get("metrics") or []
        constraints, notes = [], []
        for item in raw:
            if not isinstance(item, dict):
                return None, [], f"Điều kiện không đọc được: {item!r}. Chưa bật tự kích hoạt.", False
            op = str(item.get("op") or "").strip()
            try:
                value = float(item.get("value"))
            except (TypeError, ValueError):
                value = None
            metric = normalize_metric(item.get("metric"), problem_type or None)
            if op not in _CONSTRAINT_OPS or value is None or not math.isfinite(value):
                return None, [], f"Điều kiện không so sánh được: {item}. Chưa bật tự kích hoạt.", False
            if metric is None or metric not in computed:
                return None, [], (
                    f"Job {job_id} ({problem_type or 'không rõ loại'}) không có điểm theo '{item.get('metric')}' "
                    f"(chỉ có {', '.join(computed) or 'không rõ'}) - không kiểm được điều kiện này nên KHÔNG bật "
                    "tự kích hoạt. Báo người dùng; khi job xong họ tự quyết định."
                ), False
            value, note = scale_constraint_value(metric, value)
            if value is None:
                return None, [], f"Điều kiện {item} không dùng được: {note} Chưa bật tự kích hoạt.", False
            if note:
                notes.append(note)
            constraints.append({"metric": metric, "op": op, "value": value})
        return constraints, notes, None, False

    def change_auto_activate(
        self,
        job_id: str,
        enabled: bool,
        by_button: bool,
        constraints: list[dict] | None = None,
        only_if_pending: bool = False,
        system: bool = False,
    ) -> str:
        """
        Đổi tự kích hoạt - đường DUY NHẤT, cho cả tool lẫn nút trên thẻ, giữ khoá suốt khối.

        Tool (by_button=False) bật lên chỉ khi người dùng nhắc tới việc kích hoạt SAU lần huỷ gần
        nhất; nút trên thẻ là chính người dùng bấm nên không cần kiểm. Lời hứa ĐANG bật thì thêm
        điều kiện (chỉ chặt hơn) không cần kiểm lại. only_if_pending: chỉ đổi khi đang bật.
        Trả mã của watcher.set_auto_activate, hoặc "no_request" / "not_pending".
        """
        with self._auto_lock:
            watcher = self.session.watcher
            state = watcher.auto_state(job_id)
            if only_if_pending and state != "pending":
                return "not_pending"
            current = watcher.checked_constraints(job_id)
            tightening = state == "pending" and _only_tightens(current, constraints or [])
            # Hệ thống vừa huỷ trong CHÍNH lượt này vì điều kiện sai (vẫn đang "cancelled"): bật lại chỉ
            # khi kèm điều kiện hợp lệ, và không cần lời mới khi điều kiện đó chặt hơn lời hứa đã huỷ
            # hoặc chính tin này nhắc tới kích hoạt. Nới lỏng mà người dùng không nói -> luật thường.
            messages = self._user_messages()
            same_turn_retry = (
                state == "cancelled"
                and self._system_cancelled_at.get(job_id) == len(messages)
            )
            if enabled and not by_button and same_turn_retry and not constraints:
                return "needs_constraints"
            # Lần thử lại được đúng "cửa sổ đồng ý" của lần gọi đầu (mốc huỷ TRƯỚC lần hệ thống huỷ).
            retry_ok = same_turn_retry and (
                _only_tightens(current, constraints or [])
                or _mentions_activation(messages[self._system_prev_mark.get(job_id, 0):][-_RECENT_USER_MESSAGES:])
            )
            if enabled and not by_button and not tightening and not retry_ok:
                since = self._auto_cancelled_at.get(job_id, 0)
                if not _mentions_activation(messages[since:][-_RECENT_USER_MESSAGES:]):
                    return "no_request"
            mark_before = self._auto_cancelled_at.get(job_id, 0)
            outcome = watcher.set_auto_activate(job_id, enabled, constraints)
            if outcome == "ok":
                self.record_auto_activate_change(job_id, enabled, by_button=by_button)
                if system:
                    self._system_cancelled_at[job_id] = len(self._user_messages())
                    self._system_prev_mark[job_id] = mark_before
                else:
                    if enabled and same_turn_retry and job_id in self._system_prev_mark:
                        # Thử lại thành công: lần huỷ của hệ thống coi như chưa có - trả cửa sổ đồng ý về
                        # như trước (không thu hẹp lời đồng ý cũ của người dùng vì một lần gọi sai).
                        self._auto_cancelled_at[job_id] = self._system_prev_mark[job_id]
                    self._system_cancelled_at.pop(job_id, None)
                    self._system_prev_mark.pop(job_id, None)
            return outcome

    def _user_messages(self) -> list[str]:
        return [m["content"] for m in self.session.messages if m.get("role") == "user"]

    def record_auto_activate_change(self, job_id: str, enabled: bool, by_button: bool) -> None:
        """
        Ghi lại việc đổi tự kích hoạt. Huỷ thì nhớ mốc (số tin người dùng lúc đó) - bật lại phải có
        lời mới hơn. Đổi bằng nút trên thẻ thì báo Manager ở lượt chat sau.
        """
        if not enabled:
            # Tin đã nhận mà chưa vào lịch sử (lượt đang xếp hàng / chuẩn bị) gửi TRƯỚC lần huỷ: không
            # được tính là lời mới hơn lần huỷ.
            incoming = 1 if getattr(self.session, "incoming_user_message", False) else 0
            self._auto_cancelled_at[job_id] = len(self._user_messages()) + incoming
        if not by_button:
            self._turn_auto_changes.append((job_id, enabled))
        if by_button:
            self.session.add_event(
                f"Người dùng vừa {'BẬT' if enabled else 'HUỶ'} tự kích hoạt model cho job {job_id} bằng nút trên "
                "thẻ job. Báo đúng trạng thái này; đừng đổi lại trừ khi người dùng yêu cầu."
            )

    def watch_job(self, api, job_id: str) -> dict:
        """Bật theo dõi nền cho một job có sẵn của người dùng."""
        job, problem = tools.find_own_job(api, job_id)
        if problem:
            return problem

        status = job.get("status")
        # Chỉ trạng thái kết thúc thật (1, -1, -2) mới là "đã xong"; bản ghi thiếu status thì cứ theo dõi.
        if status in tools.JOB_FINISHED:
            # Báo kết quả ra frontend: thẻ job "mất dấu" mà người dùng nhờ theo dõi lại
            # được cập nhật ngay, không phải bấm Làm mới.
            try:
                config_id = self.handoff.jobs.get(job_id)
                own_requirements = (self.handoff.configs.get(config_id) or {}).get("requirements") if config_id else None
                # Watcher còn đang theo dõi job này thì nó sẽ tự báo (kèm việc tự kích hoạt nếu có) -
                # không phát thêm một bản kết quả nữa. watch_job KHÔNG BAO GIỜ tự kích hoạt: lời hứa
                # chỉ sống khi watcher còn theo dõi (hết giờ là hết hiệu lực).
                if job_id not in self.session.watcher.active():
                    summary = summarize_job(job, self.session.watcher.requirements_now(job_id, own_requirements))
                    self._emit("job_done" if status == tools.JOB_SUCCESS else "job_failed", agent=OPERATION_AGENT, **summary)
            except Exception:  # noqa: BLE001 - chỉ là cập nhật giao diện, không được làm hỏng tool
                log_exception(_log, "báo kết quả job %s lỗi", job_id)
            return {
                "ok": True,
                "job_id": job_id,
                "status": status,
                "note": "Job đã kết thúc, không cần theo dõi. Dùng get_job_info để xem kết quả.",
            }

        state_before = self.session.watcher.auto_state(job_id)
        # Ràng buộc chỉ áp cho job do chính phiên này khởi tạo, theo R lúc chốt config của job.
        config_id = self.handoff.jobs.get(job_id)
        requirements = (self.handoff.configs.get(config_id) or {}).get("requirements") if config_id else None
        started = self.session.watcher.watch(
            job_id,
            # Backend lưu giới hạn thời gian trong config job dưới tên timeout.
            max_time=(job.get("config") or {}).get("timeout"),
            requirements=requirements,
            trace_context=tracing.current_context(),
            dataset_id=(job.get("data") or {}).get("id"),
            problem_type=(job.get("config") or {}).get("problem_type"),
        )
        if state_before in ("pending", "expired") and self.session.watcher.auto_state(job_id) == "off":
            # Lời hứa cũ đã hết hiệu lực (theo dõi lại thành "off" - kể cả khi nó vừa hết giờ ngay trước
            # lần theo dõi này): bật lại cần lời người dùng từ tin hiện tại trở đi, lời cũ không tính.
            with self._auto_lock:
                mark = max(len(self._user_messages()) - 1, 0)
                self._auto_cancelled_at[job_id] = max(self._auto_cancelled_at.get(job_id, 0), mark)
        return {"ok": True, "job_id": job_id, "status": 0, "watching": True, "already_watching": not started}


__all__ = ["AgentTeam", "Handoff", "MANAGER", "normalize_requirements", "parse_json", "profile_brief"]
