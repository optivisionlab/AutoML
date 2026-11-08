"""
Biến thể ablation và chèn lỗi cho benchmark.

Mọi thay đổi chỉ áp lên MỘT phiên benchmark (monkeypatch rồi khôi phục), không
sửa code agent. Nhờ vậy cùng một commit chạy được bản đầy đủ lẫn các bản bị gỡ
bớt thành phần, và kết quả so sánh được với nhau.
"""

# Standard libraries
import time
from contextlib import ExitStack
from types import SimpleNamespace

# Local modules (cần src/backend trong sys.path - xem bench.py)
from agent import chat as chat_module, prompts, tools
from agent import skills as skills_module
from agent.agent_openai import MAX_STEPS, SUBAGENT_MAX_STEPS
from agent.api_client import ApiError
from agent.prompts import DATA_AGENT, MANAGER, MODEL_AGENT, OPERATION_AGENT, SQL_AGENT

from benchmark.variants_doc import VARIANT_DOCS


VARIANTS = VARIANT_DOCS

_REMOVED_AGENT = {
    "no-prompt-agent": ("ask_prompt_agent", "Prompt Agent"),
    "no-data-agent": ("ask_data_agent", "Data Agent"),
}

_SINGLE_AGENT_INTRO = """Bạn là agent DUY NHẤT của hệ thống HAutoML. Bạn nói chuyện
với người dùng và tự làm mọi việc: lấy dữ liệu từ database đã kết nối và nhập
thành dataset, tra cứu dataset, chốt config bằng submit_config, đề nghị train
bằng start_training(config_id), theo dõi job, kích hoạt model và dự đoán. Các
SKILL bên dưới viết cho hệ thống nhiều agent: bỏ qua mọi chỉ dẫn nói rằng một
việc thuộc agent khác hoặc phải báo cáo cho Agent Manager - trong phiên này bạn
làm tất cả."""

# Sub-agent nghiệp vụ mà single-agent gộp tool (Prompt Agent không có tool nghiệp vụ - xem VARIANT_DOCS).
_BUSINESS_AGENTS = (DATA_AGENT, MODEL_AGENT, OPERATION_AGENT, SQL_AGENT)


def apply_variant(session, name: str, stack: ExitStack) -> None:
    """Áp biến thể lên phiên; mọi thay đổi toàn cục được khôi phục khi stack đóng."""
    if name not in VARIANTS:
        raise ValueError(f"Biến thể không tồn tại: {name}. Có: {', '.join(VARIANTS)}")

    if name == "single-agent":
        _single_agent(session)
        # Một agent duy nhất làm cả việc của Manager và 4 sub-agent nghiệp vụ, nên trần bước của
        # Manager quá chật. MAX_STEPS + 4 x SUBAGENT_MAX_STEPS là ngân sách benchmark chọn cho biến thể
        # này, không phải tổng trần của bản đầy đủ (mỗi lần giao việc sub-agent lại có trần riêng).
        stack.callback(setattr, chat_module, "MAX_STEPS", chat_module.MAX_STEPS)
        chat_module.MAX_STEPS = single_agent_max_steps()
    elif name in _REMOVED_AGENT:
        _remove_subagent(session, *_REMOVED_AGENT[name])
    elif name == "no-validate":
        original = tools._validate_training_config
        tools._validate_training_config = lambda config, schema, valid_metrics: {
            "ok": True, "errors": [], "warnings": [],
        }
        stack.callback(setattr, tools, "_validate_training_config", original)
    elif name == "no-verify":
        watch = session.watcher.watch
        on_finish = session.watcher._on_finish

        def watch_without_requirements(job_id, *args, **kwargs):
            # Bỏ RÀNG BUỘC (không kiểm định), giữ phần còn lại của R - nhất là service.deploy: người dùng mô phỏng
            # đã chọn "train + tự kích hoạt" trên thẻ; bỏ cả R thì biến thể mất luôn lời hứa đó và phải thêm một
            # lượt "tiếp tục" so với full - nhiễu không thuộc về việc tắt kiểm định.
            kwargs["requirements"] = _without_constraints(kwargs.get("requirements"))
            return watch(job_id, *args, **kwargs)

        def finish_without_verification(summary):
            # Không có R thì sự kiện nói "người dùng không đặt ràng buộc nào" - sai với ca
            # có ngưỡng. Biến thể chỉ tắt kiểm định, không được đưa thông tin sai cho Manager.
            on_finish(summary)
            with session._pending_lock:
                if session.pending_events:
                    session.pending_events[-1] = session.pending_events[-1].replace(
                        "người dùng không đặt ràng buộc nào",
                        "kiểm định ràng buộc bị tắt trong phiên này, chưa đối chiếu với yêu cầu của người dùng",
                    )

        session.watcher.watch = watch_without_requirements
        session.watcher._on_finish = finish_without_verification


def _without_constraints(requirements: dict | None) -> dict | None:
    if not requirements:
        return None
    problem = dict(requirements.get("problem") or {})
    problem["constraints"] = []
    return {**requirements, "problem": problem}


def single_agent_max_steps() -> int:
    return MAX_STEPS + len(_BUSINESS_AGENTS) * SUBAGENT_MAX_STEPS


def _single_agent(session) -> None:
    team = session.team
    original = team.tools_for

    def tools_for(agent: str):
        if agent != MANAGER:
            return original(agent)
        # Ghép đúng các tool (đã bind với Handoff) của 4 sub-agent nghiệp vụ.
        schemas, dispatch, seen = [], {}, set()
        for sub in _BUSINESS_AGENTS:
            sub_schemas, sub_dispatch = original(sub)
            for schema in sub_schemas:
                tool = schema["function"]["name"]
                if tool not in seen:
                    seen.add(tool)
                    schemas.append(schema)
                    dispatch[tool] = sub_dispatch[tool]
        return schemas, dispatch

    team.tools_for = tools_for
    loaded = skills_module.load_skills()
    prompt = skills_module.build_prompt(
        f"{_SINGLE_AGENT_INTRO}\n\n{prompts.BASE_PROMPT}",
        [skills_module.get_skill(agent, loaded) for agent in _BUSINESS_AGENTS],
    )
    session.messages[0] = {"role": "system", "content": prompt}


def _remove_subagent(session, tool: str, title: str) -> None:
    team = session.team
    original = team.tools_for

    def tools_for(agent: str):
        schemas, dispatch = original(agent)
        if agent != MANAGER:
            return schemas, dispatch
        return (
            [s for s in schemas if s["function"]["name"] != tool],
            {k: v for k, v in dispatch.items() if k != tool},
        )

    team.tools_for = tools_for
    session.messages[0] = {
        "role": "system",
        "content": (
            f"{session.messages[0]['content']}\n\n\n# Cấu hình phiên này\n\n"
            f"{title} KHÔNG khả dụng (tool `{tool}` đã bị gỡ). Tự hoàn thành việc "
            "với các sub-agent còn lại."
        ),
    }


def instrument_llm(session, record, faults: list) -> None:
    """
    Bọc client LLM để đo thời gian từng lời gọi và (nếu có) chèn lỗi.

    record(kind, data) ghi vào trace. Fault {"kind": "llm", "call": n} chèn lỗi ở
    lời gọi thứ n (đếm từ 1, mọi agent); {"kind": "llm", "target": "subagent"}
    chèn ở lời gọi đầu tiên nằm trong một sub-agent. Không dùng số thứ tự cho
    lỗi sub-agent: ask_model_agent có thể trả về sớm không gọi LLM, khi đó lời
    gọi thứ 2 lại là của Manager.
    """
    real = session.llm
    create = real.chat.completions.create
    llm_faults = [dict(f, left=f.get("times", 1)) for f in faults if f.get("kind") == "llm"]
    counter = {"n": 0, "subagents": 0}

    def track(event):
        # Sub-agent chạy đồng bộ trong thread của lượt chat, giữa agent_start và agent_done.
        if event["type"] in ("agent_start", "agent_done") and event.get("agent") != MANAGER:
            counter["subagents"] += 1 if event["type"] == "agent_start" else -1

    session.events.subscribe(track)

    def timed_create(*args, **kwargs):
        counter["n"] += 1
        for fault in llm_faults:
            due = counter["subagents"] > 0 if fault.get("target") == "subagent" else counter["n"] >= fault["call"]
            if fault["left"] > 0 and due:
                fault["left"] -= 1
                record("fault", {"kind": "llm", "call": counter["n"]})
                raise RuntimeError("Injected LLM failure (benchmark)")
        started = time.monotonic()
        response = None
        try:
            response = create(*args, **kwargs)
            return response
        finally:
            record("llm_timing", {"call": counter["n"], "seconds": time.monotonic() - started,
                                  "missing_usage": getattr(response, "usage", None) is None})

    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=timed_create)))


def instrument_tools(session, record):
    """Capture sanitized business results for independent semantic/endpoint review."""
    original = session.team.tools_for

    def tools_for(agent):
        schemas, dispatch = original(agent)
        wrapped = {}
        for name, function in dispatch.items():
            def call(api, _name=name, _function=function, **kwargs):
                result = _function(api, **kwargs)
                if not _name.startswith("ask_"):
                    record("tool_result", {"name": _name, "agent": agent, "arguments": kwargs, "result": result})
                return result
            wrapped[name] = call
        return schemas, wrapped

    session.team.tools_for = tools_for


def instrument_schema_reads(session, record) -> None:
    """
    Ghi mọi lần đọc schema qua Handoff, kể cả khi không có tool call của LLM.

    Không có Data Agent thì ask_model_agent tự đọc schema bằng code
    (team.get_dataset_schema); chấm "agent có đọc đúng dataset" phải thấy cả đường này.
    """
    original = session.team.get_dataset_schema

    def get_dataset_schema(api, dataset_id: str, problem_type: str = "", sample_rows: int = 3):
        result = original(api, dataset_id=dataset_id, problem_type=problem_type, sample_rows=sample_rows)
        record("schema_read", {"dataset_id": dataset_id, "ok": bool(result.get("ok"))})
        return result

    session.team.get_dataset_schema = get_dataset_schema


def inject_api_faults(api, record, faults: list) -> None:
    """Lời gọi đầu tiên tới method của client backend trả lỗi 503 tạm thời."""
    for fault in faults:
        if fault.get("kind") != "api":
            continue
        method = fault["method"]
        original = getattr(api, method)
        state = {"left": fault.get("times", 1)}

        def failing(*args, _original=original, _state=state, _method=method, **kwargs):
            if _state["left"] > 0:
                _state["left"] -= 1
                record("fault", {"kind": "api", "method": _method})
                raise ApiError(503, "Injected transient error (benchmark)")
            return _original(*args, **kwargs)

        setattr(api, method, failing)
