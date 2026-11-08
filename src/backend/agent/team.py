"""
Agent Manager uỷ thác cho 5 sub-agent (Prompt, Data, Model, Operation, SQL) - các mũi tên trong sơ đồ trang 1.

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
    TurnCancelled,
    TurnDeadlineExceeded,
    create_completion,
    describe_error,
    first_message,
    log_exception,
    _DISPATCH,
    _accumulate_usage,
    usage_or_estimate,
    run_tool_loop,
    schemas_for,
)
from agent.actions import ActionError, PendingAction, PendingActions
from agent.prompts import DATA_AGENT, MANAGER, MODEL_AGENT, OPERATION_AGENT, PROMPT_AGENT, SQL_AGENT
from agent.watcher import _merge_constraints, summarize_job, wants_deploy


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


# --- Hành động thật: chỉ chạy khi NGƯỜI DÙNG bấm xác nhận (audit AG-01, AG-12) ----------------------
# Trước đây code đoán ý người dùng bằng regex từ khoá tiếng Việt / Anh ("tôi không muốn huấn luyện" vẫn lọt,
# "có nên kích hoạt không?" bị coi là đồng ý). Nay start_training, activate_model và việc BẬT tự kích hoạt chỉ
# tạo một PendingAction (agent/actions.py); frontend hiện thẻ do code dựng và hành động chỉ chạy khi người dùng
# bấm Xác nhận (POST /agent/confirm kèm token mà LLM không bao giờ thấy). Hướng an toàn (huỷ tự kích hoạt, siết
# điều kiện của lời hứa đang chờ) vẫn làm ngay.


def _user_text(message: str) -> str:
    """Phần do người dùng gõ (bỏ các dòng [Sự kiện] hệ thống chèn vào)."""
    return unicodedata.normalize(
        "NFC", "\n".join(line for line in message.splitlines() if not line.startswith(_EVENT_PREFIX))
    )


def _mentions_any(text: str, labels: list[str]) -> bool:
    """Văn bản có nhắc một nhãn (tên / id dataset) nào - đúng từ, không phân biệt hoa thường."""
    return any(
        re.search(rf"(?<!\w){re.escape(label)}(?!\w)", text, 0 if len(label.strip()) <= 2 else re.IGNORECASE)
        for label in labels if label.strip()
    )


def _mentions_column(messages: list[str], column: str) -> bool:
    """Người dùng có gõ tên cột này (đúng từ, không phân biệt hoa thường; '_' coi như dấu cách)."""
    names = {column, column.replace("_", " ")}
    patterns = [re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.IGNORECASE) for name in names if name.strip()]
    return any(p.search(_user_text(message)) for message in messages for p in patterns)


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

# Số cột đặc trưng liệt kê trên thẻ xác nhận huấn luyện (đủ để nhận ra; số cột đầy đủ đi kèm).
_CARD_FEATURES = 30
_AWAITING_NOTE = (
    " Báo người dùng bấm nút trên thẻ xác nhận (Xác nhận / Từ chối). KHÔNG nói việc đó đã xong, KHÔNG gọi lại tool "
    "để \"thử lại\", KHÔNG xin người dùng gõ câu xác nhận - chỉ nút trên thẻ có hiệu lực. Kết quả sẽ tới ở lượt sau "
    "dưới dạng [Sự kiện]."
)
_ACTION_NAMES = {
    "train": "huấn luyện",
    "activate": "KÍCH HOẠT model",
    "deactivate": "TẮT model",
    "auto_activate": "BẬT tự kích hoạt model",
}


def _constraints_text(constraints: list[dict]) -> str:
    return ", ".join(f"{c.get('metric')} {c.get('op')} {c.get('value')}" for c in constraints or [])


def _describe_action(action: dict) -> str:
    """Một dòng mô tả thẻ xác nhận (dạng public) cho Manager - không có token."""
    summary = action.get("summary") or {}
    kind = action.get("kind")
    what = _ACTION_NAMES.get(kind, str(kind))
    if kind == "train":
        target = f", target {summary.get('target')}" if summary.get("target") else ""
        return f"{what} dataset {summary.get('dataset_name') or summary.get('dataset_id')}{target}"
    if kind == "auto_activate":
        constraints = summary.get("constraints") or []
        condition = f" nếu đạt {_constraints_text(constraints)}" if constraints else " (bất kể điểm)"
        return f"{what} cho job {summary.get('job_id')}{condition}"
    return f"{what} của job {summary.get('job_id')}"


def _brief_result(result: dict) -> dict:
    """Phần kết quả gửi kèm sự kiện action_resolved cho frontend (không kèm dữ liệu lớn)."""
    keep = ("ok", "job_id", "activated", "endpoint_url", "auto_activate", "auto_activate_constraints",
            "checked_constraints", "outcome_unknown", "possible_job_ids", "status_code")
    return {key: result[key] for key in keep if key in result}


def _confirmed_note(action: PendingAction, result: dict) -> str:
    """[Sự kiện] cho Manager sau khi người dùng bấm Xác nhận - nói đúng điều đã THẬT SỰ xảy ra."""
    what = _describe_action(action.public())
    if not result.get("ok"):
        unknown = (
            f" Chưa rõ job đã được tạo hay chưa (có thể: {', '.join(result.get('possible_job_ids') or []) or 'chưa thấy'})"
            " - KHÔNG đề nghị chạy lại, kiểm tra danh sách job trước." if result.get("outcome_unknown") else ""
        )
        return f"Người dùng đã XÁC NHẬN {what} nhưng KHÔNG thực hiện được: {result.get('error')}.{unknown}"
    if action.kind == "train":
        auto = result.get("auto_activate")
        constraints = result.get("auto_activate_constraints") or []
        promise = (
            f" Tự kích hoạt khi xong: CÓ{' nếu đạt ' + _constraints_text(constraints) if constraints else ' (bất kể điểm)'}."
            if auto else " Tự kích hoạt khi xong: KHÔNG (người dùng chọn chỉ huấn luyện)."
        )
        return (
            f"Người dùng đã XÁC NHẬN {what}: job {result.get('job_id')} đã chạy nền và đang được theo dõi - CHƯA có "
            f"kết quả.{promise} Báo người dùng job_id; hệ thống tự báo khi xong."
        )
    if action.kind in ("activate", "deactivate"):
        endpoint = f" Endpoint: {result.get('endpoint_url')}." if result.get("endpoint_url") else ""
        return f"Người dùng đã XÁC NHẬN {what}: đã {'KÍCH HOẠT' if action.params.get('activate') else 'TẮT'} xong.{endpoint}"
    constraints = result.get("checked_constraints") or []
    return (
        f"Người dùng đã XÁC NHẬN {what}: khi job xong sẽ tự kích hoạt"
        f"{' nếu đạt ' + _constraints_text(constraints) if constraints else ' bất kể điểm'}."
    )


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


def _bounded_candidates(candidates, by_type: dict) -> dict:
    """target_candidates / theo loại bài toán: tên cột, cùng trần với all_column_names (dataset rất rộng)."""
    shown, hidden = tools._fit_names([str(c) for c in candidates or []], budget=8_000)
    by_type_shown, by_type_hidden = {}, 0
    for kind, names in (by_type or {}).items():
        kept, extra = tools._fit_names([str(c) for c in names or []], budget=4_000)
        by_type_shown[kind] = kept
        by_type_hidden += extra
    out = {"target_candidates": shown, "target_candidates_by_type": by_type_shown}
    if hidden or by_type_hidden:
        out["target_candidates_hidden"] = hidden + by_type_hidden
    return out


def _all_column_names(columns: list) -> dict:
    """
    Đủ tên cột của dataset rộng - có TRẦN: file upload không giới hạn số cột / độ dài tên, một header 1 MB thành
    ~300k token trong MỘT lời gọi (check_budget chỉ chặn trước lời gọi kế tiếp). Tên dài > 128 ký tự bị ẩn.
    """
    names, hidden = tools._fit_names([str(c.get("name")) for c in columns], budget=12_000)
    return {"all_column_names": names, **({"column_names_hidden": hidden} if hidden else {})}


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
    if extra.get("time_columns"):
        # Cột ngày giờ cũng có trần: file có hàng nghìn cột ngày giờ tên dài thành ~250k token một lần gọi.
        kept, used = [], 0
        for item in extra["time_columns"]:
            size = len(json.dumps(item, ensure_ascii=False, default=str))
            if used + size > 4_000:
                continue  # chỉ ẩn đúng cột không vừa (vd tên quá dài), không ẩn cả các cột sau
            kept.append(item)
            used += size
        if len(kept) < len(extra["time_columns"]):
            extra["time_columns_hidden"] = len(extra["time_columns"]) - len(kept)
        extra["time_columns"] = kept
    return {
        "dataset_id": schema.get("dataset_id"),
        "data_name": schema.get("data_name"),
        "problem_type": known,
        "total_rows": schema.get("total_rows"),
        "column_count": schema.get("column_count"),
        **_bounded_candidates(by_type.get(known) if known else schema.get("target_candidates"), by_type),
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
            if len(str(c.get("name"))) <= tools._NAME_CHARS_FOR_LLM  # tên cột dài bất thường: ẩn, không tràn context
        ],
        "columns_truncated": len(columns) > _MAX_PROFILE_COLUMNS,
        # Dataset rộng: thống kê chỉ cho 60 cột đầu nhưng TÊN thì đủ hết - thiếu nó
        # thì "dùng tất cả các cột còn lại" bị lặng lẽ cắt còn 60 cột.
        **(_all_column_names(columns) if len(columns) > _MAX_PROFILE_COLUMNS else {}),
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
    # dataset_id -> {data_name, connection_id, row_count, columns, truncated}: dataset SQL Agent vừa
    # nhập từ database ngoài. Code chuyển ID thật cho Manager, không để LLM chép lại.
    imported_datasets: dict = field(default_factory=dict)


class AgentTeam:
    """
    Dựng tool cho từng agent và chạy sub-agent khi Manager giao việc.

    Sống trong ChatSession: dùng chung client API (token người dùng), client
    LLM, bộ đếm token và kênh sự kiện của phiên.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.handoff = Handoff()
        # Hành động thật chờ người dùng bấm xác nhận (train / bật / tắt model / bật tự kích hoạt).
        self.actions = PendingActions(self._emit)
        # Thay đổi tự kích hoạt do LLM làm trong lượt đang chạy - lượt lỗi thì phải báo lại.
        self._turn_auto_changes: list[tuple[str, bool]] = []
        # Lệnh tạo job chưa rõ kết quả, theo dataset + cấu hình (không theo config_id: chốt lại
        # cùng cấu hình là ra config_id mới). Không xoá khi reset - job có thể đã tồn tại thật.
        self._unresolved_creates: list[dict] = []
        self._turn_unknown_creates: list[str] = []
        # Dataset SQL Agent nhập trong lượt đang chạy - lượt lỗi thì phải báo lại (audit AG-17).
        self._turn_imports: list[str] = []
        # Một lần xác nhận chạy tại một thời điểm (hai request xác nhận song song không chen nhau).
        self._confirm_lock = threading.Lock()

    def begin_turn(self) -> None:
        self._turn_auto_changes = []
        self._turn_unknown_creates = []
        self._turn_imports = []

    def after_failed_turn(self) -> list[str]:
        """
        Lượt chat lỗi bị bỏ khỏi lịch sử: trả câu báo cho những việc đã THẬT SỰ xảy ra trong lượt đó (đổi tự kích
        hoạt, lệnh tạo job chưa rõ kết quả, dataset đã nhập) - không báo thì người dùng gửi lại câu cũ là Manager
        làm lại (nhập trùng dataset, tạo trùng job).
        """
        notes = [
            f"Lượt chat trước bị lỗi giữa chừng NHƯNG đã {'BẬT' if enabled else 'HUỶ'} tự kích hoạt model cho job "
            f"{job_id}. Báo người dùng trạng thái này."
            for job_id, enabled in self._turn_auto_changes
        ] + self._turn_unknown_creates
        for dataset_id in self._turn_imports:
            info = self.handoff.imported_datasets.get(dataset_id) or {}
            notes.append(
                f"Lượt chat trước bị lỗi giữa chừng NHƯNG đã nhập dữ liệu từ database thành dataset "
                f"'{info.get('data_name') or dataset_id}' (id: {dataset_id}, {info.get('row_count')} dòng). KHÔNG nhập "
                "lại - dùng dataset này."
            )
        pending = self.actions.pending_public()
        if pending:
            notes.append(
                "Lượt chat trước bị lỗi giữa chừng; đang có thẻ chờ người dùng xác nhận: "
                + "; ".join(_describe_action(a) for a in pending)
                + ". Đừng đề nghị lại - nhắc người dùng bấm nút trên thẻ."
            )
        self._turn_auto_changes = []
        self._turn_unknown_creates = []
        self._turn_imports = []
        return notes

    def reset(self) -> None:
        self.handoff = Handoff()
        # Thẻ chờ xác nhận dựa trên config / R vừa bị xoá: hết hiệu lực.
        self.actions.drop_all("Phiên chat vừa được làm mới.")

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
            "activate_model": self.activate_model,
            "ask_sql_agent": self.ask_sql_agent,
            "import_database_query": self.import_database_query,
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
            {"role": "system", "content": prompts.agent_prompt(agent)},
            {"role": "user", "content": prompts.with_context(task, context)},
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
                time_left=getattr(self.session, "time_left", None),
            )
        except Exception as error:  # noqa: BLE001 - sub-agent hỏng không được làm chết Manager
            # Vượt trần token cũng về đây (không raise tiếp: Manager đang giữ một
            # tool_call chờ kết quả). Manager tự dừng ở lần kiểm trần kế tiếp.
            if isinstance(error, (TurnDeadlineExceeded, TurnCancelled)):
                # Quá hạn lượt hoặc người dùng bấm Dừng - nói đúng lý do, không gọi là "lỗi LLM".
                message = f"{prompts.title(agent)} dừng giữa chừng: {error}"
            elif isinstance(error, TurnBudgetExceeded):
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
        if not report.strip():
            # Audit AG-10: sub-agent xong mà không viết gì. Không gọi là lỗi (việc nó làm - config, thẻ xác nhận,
            # dataset đã nhập - đã được code chuyển trong các trường đi kèm), nhưng nói rõ để Manager không bịa.
            return {
                "ok": True, "agent": agent, "empty_report": True,
                "report": (
                    f"({prompts.title(agent)} không viết báo cáo. Chỉ dựa vào các trường dữ liệu đi kèm kết quả này; "
                    "đừng suy diễn thêm, cần thì giao lại việc kèm yêu cầu báo cáo.)"
                ),
            }
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
                self.session.llm, time_left=getattr(self.session, "time_left", None),
                model=self.session.config.model, messages=messages,
            )
            spent = usage_or_estimate(response, messages)
            _accumulate_usage(self.session.usage, spent)
            self._emit(
                "llm_call",
                agent=agent,
                prompt_tokens=spent.prompt_tokens or 0,
                completion_tokens=spent.completion_tokens or 0,
                total_tokens=spent.total_tokens or 0,
            )

            text = first_message(response).content or ""
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
                raw = self._ask_json(PROMPT_AGENT, prompts.agent_prompt(PROMPT_AGENT), prompts.with_context(request, context))
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
            # service.deploy chỉ là ĐỀ NGHỊ: thẻ xác nhận huấn luyện có nút riêng "huấn luyện + tự kích hoạt",
            # người dùng phải chọn nút đó thì lời hứa mới có (LLM có bịa cờ này cũng không tự kích hoạt được).
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

    def ask_sql_agent(self, api, task: str, connection_id: str = "") -> dict:
        """
        ⑥ SQL Agent: lấy dữ liệu từ database người dùng đã kết nối (metadata -> preview -> import).
        Dataset vừa nhập được trả kèm (ID thật, do code ghi) để Manager đi tiếp luồng huấn luyện.
        """
        if connection_id:
            task = f"{task}\n\nconnection_id: {connection_id}"
        before = set(self.handoff.imported_datasets)
        result = self._run_subagent(SQL_AGENT, task)
        new = [
            {"dataset_id": dataset_id, **self.handoff.imported_datasets[dataset_id]}
            for dataset_id in self.handoff.imported_datasets
            if dataset_id not in before
        ]
        result["imported_datasets"] = new
        if new:
            result["note"] = (
                "Dataset đã nhập là dataset thường của người dùng: muốn huấn luyện thì đi tiếp "
                "ask_prompt_agent (nêu dataset_id) -> ask_data_agent -> ask_model_agent -> ask_operation_agent."
            )
        return result

    def import_database_query(self, api, connection_id: str, preview_id: str, data_name: str,
                              allow_truncated: bool = False) -> dict:
        """
        import_database_query của SQL Agent, ghi dataset vừa tạo vào Handoff.

        allow_truncated KHÔNG nhận từ LLM (review 2026-11-08): "đồng ý chỉ nhập phần đầu" phải là ý người
        dùng, mà code không kiểm được LLM có hỏi thật hay không - và backend ghi chú dataset là "đã được
        người dùng đồng ý". Kết quả quá trần thì SQL Agent thêm điều kiện lọc / LIMIT vào câu truy vấn (người
        dùng thấy rõ trong bản xem trước) rồi preview lại.
        """
        result = tools.import_database_query(api, connection_id, preview_id, data_name, False)
        if result.get("ok") and result.get("dataset_id"):
            if result["dataset_id"] not in self.handoff.imported_datasets:
                self._turn_imports.append(result["dataset_id"])
            self.handoff.imported_datasets[result["dataset_id"]] = {
                "data_name": result.get("data_name", data_name),
                "connection_id": connection_id,
                "row_count": result.get("row_count"),
                "columns": result.get("columns"),
                "truncated": bool(result.get("truncated")),
            }
            self._emit(
                "dataset_imported", agent=SQL_AGENT, dataset_id=result["dataset_id"],
                data_name=result.get("data_name", data_name), row_count=result.get("row_count"),
                truncated=bool(result.get("truncated")),
            )
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
        pending_before = self.actions.pending_public()
        context = "\n\n".join([
            "## Config đã qua validate_config (chỉ chạy được các config_id này)",
            json.dumps(ready, ensure_ascii=False, indent=1) if ready else "Chưa có config nào.",
            '## Job do chính phiên chat này tạo ("job vừa tạo" chỉ là các job này)',
            json.dumps(own_jobs, ensure_ascii=False, indent=1) if own_jobs
            else "Chưa có - phiên chat này chưa tạo job nào.",
            "## Job đang được theo dõi nền",
            ", ".join(self.session.watcher.active()) or "Không có.",
            "## Thẻ đang chờ người dùng bấm xác nhận (đừng đề nghị lại việc đã có thẻ)",
            json.dumps(pending_before, ensure_ascii=False, indent=1) if pending_before else "Không có.",
        ])

        before = set(self.handoff.jobs)
        unresolved_before = {record["record_id"] for record in self._unresolved_creates}
        result = self._run_subagent(OPERATION_AGENT, task, context)
        result["jobs_started"] = sorted(set(self.handoff.jobs) - before)
        # Hành động thật Operation Agent vừa ĐỀ NGHỊ: chưa chạy, chờ người dùng bấm xác nhận trên thẻ.
        before_ids = {a["action_id"] for a in pending_before}
        awaiting = [a for a in self.actions.pending_public() if a["action_id"] not in before_ids]
        if awaiting:
            result["awaiting_confirmation"] = [
                {"action_id": a["action_id"], "kind": a["kind"], "what": _describe_action(a)} for a in awaiting
            ]
            result["confirmation_note"] = (
                "Các việc trong awaiting_confirmation CHƯA được thực hiện: người dùng phải bấm Xác nhận trên thẻ hiện "
                "trong khung chat. Nói rõ điều đó; đừng nói đã chạy / đã kích hoạt."
            )
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
        # Dataset phải nằm trong kho CỦA người dùng (không phải dataset public / của người khác, hay ID
        # chép sai) - ask_model_agent đã kiểm, nhưng Model Agent có thể submit với ID khác.
        wrong_dataset = self._check_dataset_id(api, dataset_id)
        if wrong_dataset:
            return wrong_dataset
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

        Đề nghị tự kích hoạt (service.deploy) chỉ giữ khi R nói về CHÍNH dataset này (hoặc không nêu
        dataset). Manager có thể bỏ qua Prompt Agent và dùng lại R của một yêu cầu cũ ("train A, xong
        kích hoạt" rồi vài lượt sau "giờ train B") - thẻ xác nhận của B không được đề nghị tự kích hoạt.
        Đề nghị còn giữ cũng chỉ thành lời hứa khi người dùng chọn nút "huấn luyện + tự kích hoạt".
        """
        requirements = self.handoff.requirements
        if not requirements or not (requirements.get("service") or {}).get("deploy"):
            return requirements
        named = (requirements.get("dataset") or {}).get("id")
        if named in (None, dataset_id):
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
        requirements = self.handoff.requirements or {}
        problem = requirements.get("problem") or {}
        schema = self.handoff.profiles.get(dataset_id) or tools.get_dataset_schema(api, dataset_id=dataset_id)
        columns = [c["name"] for c in schema.get("columns") or []] if schema.get("ok") else []
        recent = self._messages_about_dataset(api, dataset_id, columns)
        # R là output LLM, dựng từ việc Manager viết: Manager chép gợi ý của Data Agent ("Age hợp lý
        # nhất") vào yêu cầu là R có target dù người dùng chưa chọn. Chỉ tin R khi R nói về CHÍNH dataset
        # này và người dùng có gõ tên cột đó; không thì xét như chưa chọn (ít ứng viên vẫn qua bên dưới).
        if (
            str(problem.get("target") or "").strip().lower() == target.lower()
            and (requirements.get("dataset") or {}).get("id") == dataset_id
            and _mentions_column(recent, target)
        ):
            return None

        if not schema.get("ok"):
            return None  # không đọc được dữ liệu thì để validate_config báo lỗi
        by_type = schema.get("target_candidates_by_type") or {}
        kind = problem.get("type")
        candidates = by_type[kind] if kind in by_type else list(dict.fromkeys(
            name for names in by_type.values() for name in names
        ))
        if len(candidates) <= 1:
            return None

        if target.lower() not in {name.lower() for name in columns}:
            return None  # cột không có thật: validate_config báo đúng lỗi đó
        for message in recent:
            if target.lower() in {name.lower() for name in _named_targets(_user_text(message), columns)}:
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

    def _messages_about_dataset(self, api, dataset_id: str, columns: list[str] | tuple = ()) -> list[str]:
        """
        Tin gần đây của người dùng, bỏ những tin nói về dataset KHÁC (nhắc tên / id dataset khác của họ mà không
        nhắc dataset này): "Dataset sales, target y" không mở khoá cột y khi train dataset demo - cả khi Prompt
        Agent gán nhầm target đó vào R của demo.
        """
        recent = self.session.recent_user_messages(_RECENT_USER_MESSAGES)
        listing = tools.list_my_datasets(api)
        if not listing.get("ok"):
            return recent
        datasets = listing.get("datasets") or []
        # Tên dataset khác trùng TÊN CỘT của dataset này ("Target là sales" khi có dataset tên sales) thì không
        # coi là nhắc dataset khác - mơ hồ, nghiêng về không chặn nhầm.
        column_names = {str(c).lower() for c in columns}
        others = [
            label for d in datasets if str(d.get("_id")) != dataset_id
            for label in (str(d.get("_id") or ""), str(d.get("dataName") or ""))
            if label and label.lower() not in column_names
        ]
        own = [dataset_id] + [str(d.get("dataName") or "") for d in datasets if str(d.get("_id")) == dataset_id]
        return [
            message for message in recent
            if not (_mentions_any(_user_text(message), others) and not _mentions_any(_user_text(message), own))
        ]

    def start_training(self, api, config_id: str) -> dict:
        """
        Operation Agent ĐỀ NGHỊ chạy config theo config_id - KHÔNG chạy ngay (audit AG-01).

        Huấn luyện chiếm worker dùng chung tới max_time (≤ 24 giờ). Code kiểm mọi điều kiện (config đã qua
        validate_config, chưa chạy, không có lệnh tạo trùng chưa rõ kết quả...) rồi tạo thẻ xác nhận; job chỉ
        được tạo khi người dùng bấm Xác nhận (confirm_action). Không nhận config tự điền.
        """
        entry, problem, duplicates = self._runnable_config(api, config_id, executing=False)
        if problem:
            return problem
        requirements = self._aligned_requirements(entry)
        config = entry["config"]
        dataset_name = ((self.handoff.profiles.get(entry["dataset_id"]) or {}).get("dataset") or {}).get("name")
        offers_auto = wants_deploy(requirements)
        summary = {
            "dataset_id": entry["dataset_id"],
            "dataset_name": dataset_name,
            "target": config.get("target"),
            "feature_count": len(config.get("list_feature") or []),
            "features": list(config.get("list_feature") or [])[:_CARD_FEATURES],
            "problem_type": config.get("problem_type"),
            "metric_sort": config.get("metric_sort"),
            "search_algorithm": config.get("search_algorithm"),
            "max_time": config.get("max_time"),
        }
        if offers_auto:
            summary["auto_activate_constraints"] = ((requirements or {}).get("problem") or {}).get("constraints") or []
        if duplicates:
            summary["duplicate_of"] = duplicates
        action = self.actions.propose(
            "train", key=f"train:{entry['dataset_id']}", params={"config_id": config_id}, summary=summary,
            offers={"auto_activate": offers_auto}, api=api,
        )
        return self._awaiting(action, (
            "CHƯA chạy. Đã gửi thẻ xác nhận huấn luyện cho người dùng; job chỉ được tạo khi họ bấm Xác nhận trên "
            "thẻ." + (" Thẻ có nút riêng để huấn luyện KÈM tự kích hoạt khi xong - người dùng tự chọn." if offers_auto
                      else "")
            + (f" Lưu ý: cấu hình này GIỐNG HỆT job {', '.join(summary['duplicate_of'])} đã chạy - thẻ có ghi rõ."
               if summary.get("duplicate_of") else "")
        ))

    def _awaiting(self, action: PendingAction, note: str) -> dict:
        """Kết quả tool khi hành động đã thành thẻ chờ xác nhận (không có token)."""
        return {
            "ok": True,
            "awaiting_confirmation": True,
            "executed": False,
            **action.public(),
            "note": note + _AWAITING_NOTE,
        }

    def _aligned_requirements(self, entry: dict) -> dict | None:
        """
        R của config, theo đúng R mới nhất về việc tự kích hoạt: người dùng rút lại yêu cầu kích hoạt sau lúc chốt
        config ("à thôi đừng kích hoạt") và Prompt Agent đã dựng lại R cho CÙNG dataset với deploy = false thì
        không đề nghị tự kích hoạt nữa.
        """
        current = self.handoff.requirements or {}
        requirements = entry.get("requirements")
        if (
            wants_deploy(requirements)
            and (current.get("dataset") or {}).get("id") == entry["dataset_id"]
            and not wants_deploy(current)
        ):
            return _without_deploy(requirements)
        return requirements

    def _runnable_config(self, api, config_id: str, executing: bool) -> tuple[dict | None, dict | None, list[str]]:
        """
        Config chạy được không: (entry, None, job trùng) hoặc (None, lỗi, []). Kiểm cả lúc đề nghị lẫn lúc người
        dùng bấm xác nhận (bối cảnh có thể đã đổi: config khác đã chạy, config bị thay, lệnh tạo chưa rõ kết quả).

        Lúc đề nghị, cấu hình giống hệt một job đã chạy KHÔNG bị chặn mà trả danh sách job đó để thẻ xác nhận nói
        rõ - người dùng bấm xác nhận nghĩa là họ muốn chạy lại.
        """
        entry = self.handoff.configs.get(config_id)
        if entry is None:
            return None, {
                "ok": False,
                "error": (
                    f"Không có config '{config_id}'. Chỉ chạy được config đã được Model Agent "
                    "chốt qua submit_config (đã kiểm bằng validate_config)."
                ),
                "available_config_ids": sorted(self.handoff.configs),
            }, []
        if entry.get("job_id"):
            return None, {
                "ok": False,
                "error": f"Config '{config_id}' đã chạy thành job {entry['job_id']}. Không chạy lại trùng.",
                "job_id": entry["job_id"],
            }, []
        if entry.get("outcome_unknown"):
            return None, {
                "ok": False,
                "outcome_unknown": True,
                "error": (
                    f"Lần chạy trước của config '{config_id}' chưa rõ đã tạo job hay chưa - KHÔNG chạy lại "
                    "(có thể ra job trùng). Kiểm tra list_my_jobs; có job khớp thì watch_job; chắc chắn "
                    "không có thì nhờ Model Agent chốt lại config."
                ),
            }, []
        if entry.get("superseded_by"):
            return None, {
                "ok": False,
                "error": (
                    f"Config '{config_id}' đã bị thay bằng config mới hơn "
                    f"'{entry['superseded_by']}' của cùng dataset. Chạy config mới đó."
                ),
                "config_id": entry["superseded_by"],
            }, []
        blocked, finished_matches = self._unresolved_create_check(api, entry, executing)
        if blocked:
            return None, blocked, []
        duplicates: list[str] = []
        if not executing:
            # So theo TẬP cột (đổi thứ tự cột vẫn là cùng một lần train) cộng thuật toán và thời gian - đổi thuật
            # toán theo yêu cầu "thử thuật toán khác" là lần train khác.
            def run_key(config: dict) -> tuple:
                return _config_key(config), config.get("search_algorithm"), config.get("max_time")

            same = [
                other["job_id"] for other in self.handoff.configs.values()
                if other is not entry and other.get("job_id") and other.get("dataset_id") == entry["dataset_id"]
                and run_key(other.get("config") or {}) == run_key(entry["config"])
            ]
            duplicates = list(dict.fromkeys(same + finished_matches))
        return entry, None, duplicates

    def _execute_training(self, api, config_id: str, auto_activate: bool) -> dict:
        """Người dùng đã bấm xác nhận: kiểm lại rồi tạo job thật, bật theo dõi (và lời hứa tự kích hoạt nếu chọn)."""
        entry, problem, _ = self._runnable_config(api, config_id, executing=True)
        if problem:
            return problem
        requirements = self._aligned_requirements(entry)
        if not auto_activate:
            requirements = _without_deploy(requirements) if wants_deploy(requirements) else requirements

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
        if not result.get("ok") or not result.get("job_id"):
            return result

        job_id = result["job_id"]
        entry["job_id"] = job_id
        # Chỉ ghi lựa chọn tự kích hoạt khi job đã tạo: tạo hỏng thì thẻ đề nghị lại vẫn có nút "+ tự kích hoạt".
        entry["requirements"] = requirements
        self.handoff.jobs[job_id] = config_id
        self._emit(
            "job_started", agent=OPERATION_AGENT, job_id=job_id, config_id=config_id,
            dataset_id=entry["dataset_id"], config=config, auto_activate=wants_deploy(requirements),
        )
        self.session.watcher.watch(
            job_id,
            max_time=config.get("max_time"),
            requirements=requirements,
            trace_context=tracing.current_context(),
            dataset_id=entry["dataset_id"],
            problem_type=config.get("problem_type"),
        )

        result["watching"] = True
        result["auto_activate"] = self.session.watcher.auto_activate(job_id)
        result["auto_activate_constraints"] = (
            self.session.watcher.checked_constraints(job_id) if result["auto_activate"] else []
        )
        return result

    def _unresolved_create_check(self, api, entry: dict, executing: bool) -> tuple[dict | None, list[str]]:
        """
        Đã có lệnh tạo job CÙNG dataset + cấu hình chưa rõ kết quả: không gửi lệnh thứ hai khi chưa chắc lần
        trước không tạo được job (sẽ ra job trùng chạy hàng giờ). Trả (lỗi chặn | None, job khớp đã XONG).

        Có job khớp đang chạy -> chặn, trả job đó để theo dõi. Job khớp đã xong thành công -> không chặn, nhưng
        báo lại để thẻ xác nhận ghi "giống hệt job đã chạy" (người dùng xác nhận là muốn chạy lại); chỉ khi
        thực thi mới xoá ghi nhận. Chưa thấy mà mới chưa tới _UNRESOLVED_RECHECK_SECONDS -> chặn, đợi. Quá lâu
        vẫn không thấy -> lần trước coi như chưa tạo được: cho chạy, xoá ghi nhận.
        """
        key = _config_key(entry["config"])
        finished: list[str] = []
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
                }, []
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
                }, []
            if found:
                # Job khớp đã kết thúc. Thành công (hay thiếu / lạ status) = lần gửi trước ĐÃ là lần train này:
                # chạy nữa là chạy lại - thẻ phải nói rõ. Chỉ toàn job lỗi thì chạy lại là khắc phục.
                succeeded = [job["job_id"] for job in found
                             if job.get("status") not in (tools.JOB_FAILED, tools.JOB_CANCELLED)]
                finished += succeeded
                if executing or not succeeded:
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
                }, []
            self._unresolved_creates.remove(record)
        return None, finished

    def set_auto_activate(self, api, job_id: str, enabled: bool = False, constraints=None) -> dict:
        """
        Bật/tắt tự kích hoạt cho một job đang chạy (người dùng đổi ý: "à thôi đừng kích hoạt").

        TẮT (và siết điều kiện của lời hứa đang chờ) là hướng an toàn - làm ngay. BẬT (hoặc nới điều kiện) là
        hứa một hành động thật về sau - chỉ tạo thẻ xác nhận; lời hứa có khi người dùng bấm Xác nhận.
        constraints: điều kiện người dùng nêu kèm ("đạt accuracy >= 0.9 thì kích hoạt") - kiểm lúc job xong.
        Điều kiện không kiểm được thì KHÔNG đề nghị (bật là kích hoạt bất kể điểm).
        """
        enabled = tools.as_bool(enabled)
        if enabled is None:
            return self._auto_refusal(job_id, "enabled phải là true hoặc false.")
        watcher = self.session.watcher
        if not enabled:
            outcome = self.change_auto_activate(job_id, False, by_button=False)
            if outcome != "ok":
                return self._auto_refusal(job_id, _AUTO_ACTIVATE_REFUSED[outcome].format(job_id=job_id))
            return {"ok": True, "job_id": job_id, "auto_activate": False}

        added, notes = [], []
        if constraints not in (None, []):
            added, notes, problem, transient = self._activation_constraints(api, job_id, constraints)
            if problem:
                # Lời hứa đang chờ mà điều kiện mới không áp được (điều kiện sai, hay tạm không đọc được job): để
                # nguyên thì job xong vẫn kích hoạt theo điều kiện CŨ mà người dùng vừa đổi - huỷ cho chắc, nói rõ.
                if watcher.set_auto_activate(job_id, False, only_if_pending=True) == "ok":
                    self.record_auto_activate_change(job_id, False, by_button=False)
                    problem += (
                        " Đã HUỶ tự kích hoạt đang bật của job này (chưa áp được điều kiện người dùng vừa đặt)"
                        + ("; thử lại set_auto_activate với cùng điều kiện khi đọc được job." if transient else ".")
                    )
                return self._auto_refusal(job_id, problem)

        state = watcher.auto_state(job_id)
        current = watcher.checked_constraints(job_id)
        if state == "pending" and _only_tightens(current, added):
            # Lời hứa đang chờ, điều kiện mới chỉ làm việc kích hoạt KHÓ hơn: an toàn, áp ngay. Nguyên tử trong
            # watcher - người dùng vừa bấm Huỷ thì không bật lại ("not_pending" -> đi đường đề nghị).
            if not added:
                return self._auto_ok(job_id, notes)
            if watcher.set_auto_activate(job_id, True, added, only_if_pending=True) == "ok":
                self.record_auto_activate_change(job_id, True, by_button=False)
                return self._auto_ok(job_id, notes)
            state = watcher.auto_state(job_id)
        if job_id not in watcher.active():
            return self._auto_refusal(job_id, _AUTO_ACTIVATE_REFUSED["not_watched"].format(job_id=job_id))
        if state == "activating":
            return self._auto_refusal(job_id, _AUTO_ACTIVATE_REFUSED["in_progress"].format(job_id=job_id))
        if state in ("done", "expired"):
            return self._auto_refusal(job_id, _AUTO_ACTIVATE_REFUSED["finished"].format(job_id=job_id))
        will_check = _merge_constraints(current, added)
        action = self.actions.propose(
            "auto_activate", key=f"auto:{job_id}", params={"job_id": job_id, "constraints": added},
            summary={
                "job_id": job_id,
                "dataset_id": self._job_dataset(job_id),
                "constraints": will_check,
                "unconditional": not will_check,
            }, api=api,
        )
        result = self._awaiting(action, (
            "CHƯA bật. Đã gửi thẻ xác nhận BẬT tự kích hoạt cho người dùng; lời hứa chỉ có khi họ bấm Xác nhận."
            + (f" Khi job xong sẽ kiểm: {_constraints_text(will_check)}." if will_check
               else " Không có điều kiện: nếu được xác nhận, model kích hoạt khi job xong BẤT KỂ điểm.")
        ))
        if notes:
            result["notes"] = notes
        return result

    def _auto_ok(self, job_id: str, notes: list[str]) -> dict:
        """Lời hứa đang chờ (vừa siết điều kiện, hoặc không đổi gì): báo ĐÚNG điều kiện sẽ kiểm."""
        checked = self.session.watcher.checked_constraints(job_id)
        result = {
            "ok": True,
            "job_id": job_id,
            "auto_activate": True,
            "checked_constraints": checked,
            "note": (
                "Khi job xong chỉ kích hoạt nếu đạt MỌI ràng buộc trong checked_constraints."
                if checked else
                "Không có ràng buộc nào: model sẽ được kích hoạt khi job xong BẤT KỂ điểm."
            ),
        }
        if notes:
            result["notes"] = notes
        return result

    def _job_dataset(self, job_id: str) -> str | None:
        config_id = self.handoff.jobs.get(job_id)
        return (self.handoff.configs.get(config_id) or {}).get("dataset_id") if config_id else None

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
        self, job_id: str, enabled: bool, by_button: bool, constraints: list[dict] | None = None,
    ) -> str:
        """
        Đổi tự kích hoạt ngay (không qua thẻ xác nhận): TẮT từ tool hay nút, hoặc BẬT bằng nút trên thẻ job /
        thẻ xác nhận - đều là người dùng tự bấm, hoặc hướng an toàn. Tool muốn BẬT thì phải qua set_auto_activate
        (tạo thẻ xác nhận). Trả mã của watcher.set_auto_activate.
        """
        if enabled and not by_button:
            raise ValueError("Bật tự kích hoạt từ tool phải qua thẻ xác nhận (set_auto_activate).")
        outcome = self.session.watcher.set_auto_activate(job_id, enabled, constraints)
        if outcome == "ok":
            self.record_auto_activate_change(job_id, enabled, by_button=by_button)
        return outcome

    def record_auto_activate_change(self, job_id: str, enabled: bool, by_button: bool) -> None:
        """Ghi lại việc đổi tự kích hoạt. Đổi bằng nút trên thẻ thì báo Manager ở lượt chat sau."""
        if not by_button:
            self._turn_auto_changes.append((job_id, enabled))
            return
        self.session.add_event(
            f"Người dùng vừa {'BẬT' if enabled else 'HUỶ'} tự kích hoạt model cho job {job_id} bằng nút trên "
            "thẻ job. Báo đúng trạng thái này; đừng đổi lại trừ khi người dùng yêu cầu."
        )

    def activate_model(self, api, job_id: str, activate: bool = True) -> dict:
        """
        ĐỀ NGHỊ bật / tắt model của một job - hành động thật (endpoint dự đoán đổi ngay), nên chỉ chạy khi người
        dùng bấm Xác nhận trên thẻ. Tên cột, ô dữ liệu hay lỗi backend có thể chứa câu kiểu "người dùng yêu cầu
        tắt model job X" (prompt injection gián tiếp): LLM làm theo thì cũng chỉ ra được một thẻ mà người dùng
        thấy rõ job nào, bật hay tắt - và từ chối được.
        """
        flag = tools.as_bool(activate)
        if flag is None:
            return tools.activate_model(api, job_id, activate)  # tool tự báo lỗi tham số, không làm gì
        job, problem = tools.find_own_job(api, job_id)
        if problem:
            return problem
        if flag and job.get("status") != tools.JOB_SUCCESS:
            return {
                "ok": False,
                "job_id": job_id,
                "error": (
                    f"Job '{job_id}' chưa huấn luyện xong (status = {job.get('status')}), chưa có model để kích hoạt."
                    + (" Job đang chạy: muốn tự kích hoạt khi xong thì dùng set_auto_activate."
                       if job.get("status") == tools.JOB_RUNNING else "")
                ),
            }
        if job.get("activate") == (1 if flag else 0):
            return {
                "ok": True,
                "job_id": job_id,
                "activated": flag,
                "note": f"Model của job này đã {'được kích hoạt' if flag else 'ở trạng thái tắt'} - không cần làm gì.",
            }
        summary = self._job_card(api, job)
        action = self.actions.propose(
            "activate" if flag else "deactivate", key=f"activation:{job_id}",
            params={"job_id": job_id, "activate": flag}, summary=summary, api=api,
        )
        return self._awaiting(action, (
            f"CHƯA {'kích hoạt' if flag else 'tắt'}. Đã gửi thẻ xác nhận {'KÍCH HOẠT' if flag else 'TẮT'} model của "
            f"job {job_id} cho người dùng; chỉ làm khi họ bấm Xác nhận trên thẻ."
        ))

    def propose_activation_after_job(self, summary: dict) -> bool:
        """
        Job xong, ràng buộc chỉ đạt theo điểm cross-validation (audit AG-02): không tự kích hoạt mà đưa thẻ xác
        nhận kích hoạt cho người dùng (watcher gọi qua ChatSession._on_job_finished). Trả True nếu đã tạo thẻ.
        """
        job_id = summary.get("job_id")
        if not job_id:
            return False
        checks = (summary.get("verification") or {}).get("checks") or []
        try:
            self.actions.propose(
                "activate", key=f"activation:{job_id}", params={"job_id": job_id, "activate": True},
                summary={
                    "job_id": job_id,
                    "dataset_id": summary.get("dataset_id"),
                    "dataset_name": summary.get("dataset"),
                    "problem_type": summary.get("problem_type"),
                    "best_model": summary.get("best_model"),
                    "metric_sort": summary.get("metric_sort"),
                    "best_score": summary.get("best_score"),
                    "score_source": summary.get("score_source"),
                    "constraints": [{k: c.get(k) for k in ("metric", "op", "value", "score")} for c in checks],
                    "currently_active": False,
                },
                api=self.session.api,
            )
        except Exception:  # noqa: BLE001 - thẻ là phần thêm; không được làm hỏng việc báo job xong
            log_exception(_log, "tạo thẻ kích hoạt cho job %s lỗi", job_id)
            return False
        return True

    def _job_card(self, api, job: dict) -> dict:
        """Thông tin job cho thẻ xác nhận bật / tắt model - do code dựng từ bản ghi job thật."""
        config = job.get("config") or {}
        card = {
            "job_id": job.get("job_id"),
            "dataset_id": (job.get("data") or {}).get("id"),
            "dataset_name": (job.get("data") or {}).get("name"),
            "target": config.get("target"),
            "problem_type": config.get("problem_type"),
            "best_model": job.get("best_model"),
            "metric_sort": config.get("metric_sort"),
            "best_score": job.get("best_score"),
            "currently_active": job.get("activate") == 1,
        }
        if job.get("status") == tools.JOB_SUCCESS:
            # Audit AG-02: thẻ nói rõ điểm là CV (lạc quan) hay holdout - người dùng quyết định có dữ kiện.
            card["score_source"] = tools.job_score_source(api, str(job.get("job_id")))
        return card

    # ------------------------------------------------- xác nhận của người dùng

    def confirm_action(self, action_id: str, token: str, auto_activate: bool | None = None) -> dict:
        """
        Người dùng bấm Xác nhận trên thẻ (POST /agent/confirm, hoặc lệnh trong agent.chat): thực thi đúng hành
        động đã đề nghị, sau khi kiểm lại điều kiện. Raise ActionError khi thẻ không xác nhận được (sai token,
        hết hạn, đã xử lý). Không gọi LLM.

        auto_activate: chỉ cho thẻ huấn luyện có đề nghị tự kích hoạt - True = người dùng chọn nút "huấn luyện +
        tự kích hoạt"; mặc định KHÔNG tự kích hoạt.
        """
        with self._confirm_lock:
            action = self.actions.get(action_id)
            if action is not None and action.kind == "train" and auto_activate and not action.offers.get("auto_activate"):
                raise ActionError("bad_option", "Thẻ này không có lựa chọn tự kích hoạt.")
            action = self.actions.claim(action_id, token)
            action.choice = {"auto_activate": bool(auto_activate)} if action.kind == "train" else {}
            try:
                result = self._execute(action)
            except Exception as error:  # noqa: BLE001 - thẻ không được kẹt ở "executing"
                log_exception(_log, "thực thi hành động %s lỗi", action.action_id)
                result = {"ok": False, "error": f"Lỗi nội bộ khi thực hiện ({type(error).__name__})."}
            ok = bool(result.get("ok"))
            self.actions.resolve(action, ok, result=_brief_result(result), error=None if ok else str(result.get("error")))
            self.session.add_event(_confirmed_note(action, result))
            return {**result, "action_id": action.action_id, "kind": action.kind}

    def reject_action(self, action_id: str, token: str) -> dict:
        """Người dùng bấm Từ chối: không làm gì, báo Manager ở lượt sau."""
        action = self.actions.reject(action_id, token)
        self.session.add_event(
            f"Người dùng đã TỪ CHỐI {_describe_action(action.public())}. Không làm việc đó; đừng đề nghị lại trừ khi "
            "người dùng tự yêu cầu."
        )
        return {"ok": True, "action_id": action.action_id, "kind": action.kind, "status": "rejected"}

    def _execute(self, action: PendingAction) -> dict:
        api = action.api or self.session.api
        params = action.params
        if action.kind == "train":
            return self._execute_training(api, params["config_id"], bool(action.choice.get("auto_activate")))
        if action.kind in ("activate", "deactivate"):
            result = tools.activate_model(api, params["job_id"], params["activate"])
            if result.get("ok"):
                self._emit(
                    "model_activation", agent=OPERATION_AGENT, job_id=params["job_id"], activated=params["activate"],
                    endpoint_url=result.get("endpoint_url"),
                )
            return result
        if action.kind == "auto_activate":
            job_id = params["job_id"]
            # Thẳng vào watcher: _confirmed_note đã báo Manager (không báo thêm câu "bấm nút trên thẻ job").
            outcome = self.session.watcher.set_auto_activate(job_id, True, params.get("constraints"))
            if outcome != "ok":
                return {"ok": False, "job_id": job_id, "error": _AUTO_ACTIVATE_REFUSED[outcome].format(job_id=job_id)}
            return {
                "ok": True, "job_id": job_id, "auto_activate": True,
                "checked_constraints": self.session.watcher.checked_constraints(job_id),
            }
        return {"ok": False, "error": f"Loại hành động lạ: {action.kind}"}

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
                    source = tools.job_score_source(api, job_id) if status == tools.JOB_SUCCESS else None
                    summary = summarize_job(
                        job, self.session.watcher.requirements_now(job_id, own_requirements), score_source=source,
                    )
                    self._emit("job_done" if status == tools.JOB_SUCCESS else "job_failed", agent=OPERATION_AGENT, **summary)
            except Exception:  # noqa: BLE001 - chỉ là cập nhật giao diện, không được làm hỏng tool
                log_exception(_log, "báo kết quả job %s lỗi", job_id)
            return {
                "ok": True,
                "job_id": job_id,
                "status": status,
                "note": "Job đã kết thúc, không cần theo dõi. Dùng get_job_info để xem kết quả.",
            }

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
        return {"ok": True, "job_id": job_id, "status": 0, "watching": True, "already_watching": not started}


__all__ = ["AgentTeam", "Handoff", "MANAGER", "normalize_requirements", "parse_json", "profile_brief"]
