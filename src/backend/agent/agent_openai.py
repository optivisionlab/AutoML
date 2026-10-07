"""
Sổ đăng ký tool và vòng lặp tool-calling dùng chung cho mọi agent.

Hệ thống có 5 agent (xem docs/hautoml-multi-agent-detailed.drawio, trang 1):

    Agent Manager ─┬─ ① Prompt Agent     hiểu yêu cầu → R (JSON 6 khoá)
                   ├─ ② Data Agent       đặc điểm dữ liệu
                   ├─ ③ Model Agent      ra quyết định config (không bấm chạy)
                   └─ ④ Operation Agent  chạy, theo dõi, triển khai

Agent nào dùng tool nào do `tools:` trong SKILL.md của nó quyết định - file này
chỉ khai schema và nối tên tool với hàm Python. Mọi agent đều chạy qua cùng một
hàm `run_tool_loop`, chỉ khác system prompt và tập tool.

Dùng được với OpenRouter, Google AI Studio, OpenAI và Azure - cả bốn đều nói
chuẩn Chat Completions (xem providers.py). Vòng lặp tự viết thay vì dùng helper
của SDK để chen được vào từng bước: báo tiến độ, đếm token, và giữ
thought_signature của Gemini.

Chạy:
    cd src/backend
    python -m agent.cli "tôi có dataset nào"
"""

# Standard libraries
import json

# Local modules
from agent import tools, tracing
from agent.api_client import HAutoMLClient


# Số vòng lặp tối đa của Agent Manager, chặn model gọi tool luẩn quẩn.
MAX_STEPS = 12
# Sub-agent làm một việc hẹp, cần ít bước hơn.
SUBAGENT_MAX_STEPS = 8

# Những khoá bị che khi in log, tránh lộ mật khẩu ra terminal.
_SECRET_KEYS = {"password", "new_password", "confirm_password"}

_DATASET_ID = {
    "type": "string",
    "description": "ID dataset, lấy từ trường _id trong kết quả list_my_datasets.",
}
_PROBLEM_TYPE = {
    "type": "string",
    "enum": ["classification", "regression"],
    "description": "Loại bài toán của dataset.",
}
_JOB_ID = {"type": "string", "description": "job_id, lấy từ list_my_jobs hoặc start_training."}
_TASK = {
    "type": "string",
    "description": (
        "Việc giao cho agent, viết đủ ngữ cảnh: agent này KHÔNG thấy lịch sử hội thoại. "
        "Nêu rõ ID, tên cột, ràng buộc người dùng đã nói."
    ),
}


def _tool(name: str, description: str, properties: dict | None = None, required=None) -> dict:
    """
    Schema theo định dạng OpenAI function calling.

    Cố ý không dùng "additionalProperties" vì một số provider (Gemini) chỉ nhận
    một tập con của JSON Schema.
    """
    parameters: dict = {"type": "object", "properties": properties or {}}
    if required:
        parameters["required"] = list(required)
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": parameters},
    }


TOOL_SCHEMAS = [
    # --- Agent Manager: uỷ thác cho 4 sub-agent ---------------------------------
    _tool(
        "ask_prompt_agent",
        (
            "Giao cho Prompt Agent chuẩn hoá yêu cầu thành R (JSON 6 khoá: user, problem, "
            "dataset, model, knowledge, service) và liệt kê thông tin còn thiếu. Gọi ĐẦU TIÊN "
            "khi người dùng muốn huấn luyện model mới. Không dùng cho tra cứu hay thao tác "
            "trên job đã có."
        ),
        {"request": {
            "type": "string",
            "description": "Yêu cầu của người dùng, kèm mọi chi tiết họ đã nêu ở các lượt trước.",
        }},
        ["request"],
    ),
    _tool(
        "ask_data_agent",
        (
            "Giao cho Data Agent tra cứu dataset: liệt kê, xem metadata, phân tích cột. Kết quả "
            "phân tích được tự chuyển cho Model Agent."
        ),
        {"task": _TASK, "dataset_id": {**_DATASET_ID, "description": "Bỏ trống nếu chưa biết."}},
        ["task"],
    ),
    _tool(
        "ask_model_agent",
        (
            "Giao cho Model Agent ra quyết định config huấn luyện (target, đặc trưng, metric, "
            "thuật toán tìm kiếm, max_time). Config được kiểm bằng code trước khi trả về "
            "config_id. Model Agent KHÔNG bấm chạy."
        ),
        {"task": _TASK, "dataset_id": _DATASET_ID},
        ["task", "dataset_id"],
    ),
    _tool(
        "ask_operation_agent",
        (
            "Giao cho Operation Agent thực thi: chạy config đã kiểm (config_id), theo dõi job, "
            "xem kết quả, kích hoạt model, dự đoán."
        ),
        {"task": _TASK},
        ["task"],
    ),

    # --- Data Agent ---------------------------------------------------------------
    _tool(
        "list_my_datasets",
        "Liệt kê các dataset của tài khoản đang đăng nhập. Không cần truyền user_id, tool tự lấy.",
    ),
    _tool(
        "get_dataset_info",
        (
            "Xem metadata một dataset (tên, loại bài toán, ngày tạo). "
            "KHÔNG có tên cột - muốn biết các thuộc tính thì dùng get_dataset_schema."
        ),
        {"dataset_id": _DATASET_ID},
        ["dataset_id"],
    ),
    _tool(
        "get_dataset_schema",
        (
            "Lấy danh sách thuộc tính (cột) của một dataset, kèm kiểu dữ liệu, số giá trị "
            "khác nhau, số giá trị thiếu, vài giá trị mẫu, và cột nào dùng được làm biến "
            "mục tiêu."
        ),
        {
            "dataset_id": _DATASET_ID,
            "problem_type": {
                "type": "string",
                "description": "classification hoặc regression. Bỏ trống thì lấy theo dataType của dataset.",
            },
        },
        ["dataset_id"],
    ),

    # --- Model Agent --------------------------------------------------------------
    _tool(
        "list_metrics",
        "Danh sách metric hợp lệ để xếp hạng model, theo loại bài toán.",
        {"problem_type": _PROBLEM_TYPE},
        ["problem_type"],
    ),
    _tool(
        "list_models",
        (
            "Các model engine sẽ huấn luyện (đọc từ system_models/*.yml), kèm số tổ hợp tham "
            "số. Engine luôn train TẤT CẢ các model này rồi xếp hạng."
        ),
        {"problem_type": _PROBLEM_TYPE},
        ["problem_type"],
    ),
    _tool(
        "submit_config",
        (
            "Chốt một config huấn luyện. Config được kiểm bằng code (validate_config.py) dựa "
            "trên schema thật: hợp lệ thì trả config_id cho Operation Agent, không hợp lệ thì "
            "trả errors kèm valid_columns / target_candidates / valid_metrics để sửa."
        ),
        {
            "dataset_id": _DATASET_ID,
            "target": {"type": "string", "description": "Cột mục tiêu, phải nằm trong target_candidates."},
            "list_feature": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Các cột đặc trưng đầu vào. Không được chứa cột mục tiêu.",
            },
            "metric_sort": {"type": "string", "description": "Metric xếp hạng model, lấy từ list_metrics."},
            "problem_type": {**_PROBLEM_TYPE, "description": "Bỏ trống thì lấy theo dataType của dataset."},
            "search_algorithm": {
                "type": "string",
                "enum": ["grid_search", "genetic_algorithm", "bayesian_search"],
                "description": "Mặc định grid_search.",
            },
            "max_time": {
                "type": "integer",
                "description": "Giới hạn thời gian tính bằng giây, 60 đến 86400. Mặc định 900.",
            },
            "rationale": {
                "type": "string",
                "description": "Một hai câu: vì sao chọn target, metric, thuật toán này.",
            },
        },
        ["dataset_id", "target", "list_feature", "metric_sort"],
    ),

    # --- Operation Agent ----------------------------------------------------------
    _tool(
        "start_training",
        (
            "Chạy một config ĐÃ được Model Agent chốt và kiểm hợp lệ. Trả job_id NGAY, job chạy "
            "nền vài phút tới hàng giờ, hệ thống tự theo dõi và báo khi xong."
        ),
        {"config_id": {"type": "string", "description": "config_id do Model Agent trả về."}},
        ["config_id"],
    ),
    _tool(
        "watch_job",
        "Bật theo dõi nền cho một job đang chạy: hệ thống tự báo khi job đổi trạng thái.",
        {"job_id": _JOB_ID},
        ["job_id"],
    ),
    _tool(
        "list_my_jobs",
        "Liệt kê các job huấn luyện của tài khoản đang đăng nhập. Không cần truyền user_id.",
    ),
    _tool(
        "get_job_info",
        "Xem chi tiết một job huấn luyện, gồm trạng thái và kết quả các model.",
        {"job_id": _JOB_ID},
        ["job_id"],
    ),
    _tool(
        "activate_model",
        "Kích hoạt (hoặc tắt) model của một job đã huấn luyện xong để dùng dự đoán.",
        {
            "job_id": _JOB_ID,
            "activate": {"type": "boolean", "description": "true = kích hoạt, false = tắt. Mặc định true."},
        },
        ["job_id"],
    ),
    _tool(
        "predict",
        (
            "Dự đoán cho vài mẫu (tối đa 50) bằng model của một job đã kích hoạt. Mỗi mẫu là "
            "object {tên cột: giá trị} chứa đủ các cột đặc trưng của job."
        ),
        {
            "job_id": _JOB_ID,
            "rows": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Các mẫu cần dự đoán.",
            },
        },
        ["job_id", "rows"],
    ),

    # --- Dùng chung ---------------------------------------------------------------
    _tool(
        "read_reference",
        (
            "Đọc một tài liệu tra cứu của skill. Các tài liệu này không nằm sẵn trong "
            "hướng dẫn, chỉ có tên và mô tả. Dùng khi cần chi tiết mà hướng dẫn không đủ."
        ),
        {"ref_id": {
            "type": "string",
            "description": "Định danh tài liệu, dạng <skill>/<tên>, ví dụ data-agent/dataset_schema.",
        }},
        ["ref_id"],
    ),
]

_SCHEMA_BY_NAME = {schema["function"]["name"]: schema for schema in TOOL_SCHEMAS}

# Tool không cần trạng thái phiên: tên -> hàm trong tools.py, nhận client làm
# tham số đầu. Không có tool xác thực nào ở đây: đăng nhập làm ở tầng phiên,
# LLM không biết tới token.
_DISPATCH = {
    "list_my_datasets": tools.list_my_datasets,
    "get_dataset_info": tools.get_dataset_info,
    "get_dataset_schema": tools.get_dataset_schema,
    "list_metrics": tools.list_metrics,
    "list_models": tools.list_models,
    "list_my_jobs": tools.list_my_jobs,
    "get_job_info": tools.get_job_info,
    "activate_model": tools.activate_model,
    "predict": tools.predict,
    "read_reference": tools.read_reference,
}

# Tool cần trạng thái của phiên (dữ liệu chuyển giữa các agent, job đang theo
# dõi). Hàm thật do agent.team.AgentTeam dựng cho từng phiên.
SESSION_TOOLS = {
    "ask_prompt_agent",
    "ask_data_agent",
    "ask_model_agent",
    "ask_operation_agent",
    "submit_config",
    "start_training",
    "watch_job",
}


def known_tools() -> set[str]:
    return set(_SCHEMA_BY_NAME)


def schemas_for(names: list[str]) -> list[dict]:
    """Schema của đúng các tool một agent được dùng, theo thứ tự khai trong SKILL.md."""
    return [_SCHEMA_BY_NAME[name] for name in names if name in _SCHEMA_BY_NAME]


def _redact(tool_input: dict) -> dict:
    return {
        key: ("***" if key in _SECRET_KEYS else value)
        for key, value in tool_input.items()
    }


def _call_tool(api: HAutoMLClient, dispatch: dict, name: str, arguments: dict) -> dict:
    """Gọi tool và bọc mọi lỗi thành dict, để một tool hỏng không làm chết vòng lặp."""
    handler = dispatch.get(name)
    if handler is None:
        return {"ok": False, "error": f"Tool không tồn tại hoặc agent này không được dùng: {name}"}

    try:
        return handler(api, **arguments)
    except TypeError as error:
        return {"ok": False, "error": f"Tham số không hợp lệ cho {name}: {error}"}


def _assistant_message(message) -> dict:
    """
    Dựng lại assistant message để gửi kèm lượt sau.

    Chỉ lấy các field chuẩn thay vì model_dump() toàn bộ, vì một số provider từ
    chối các field null lạ (annotations, refusal, audio...) khi nhận lại chính
    response của mình.

    NHƯNG phải giữ nguyên các field lạ do provider tự thêm (model_extra):
    Gemini gắn `extra_content.google.thought_signature` vào từng tool call và
    BẮT BUỘC nhận lại nó ở lượt sau - thiếu là lỗi 400 INVALID_ARGUMENT. Provider
    khác không sinh field này nên copy nguyên khối vẫn an toàn.
    """
    payload: dict = {"role": "assistant", "content": message.content or ""}
    payload.update(message.model_extra or {})

    if message.tool_calls:
        calls = []
        for call in message.tool_calls:
            entry = {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            entry.update(call.model_extra or {})
            calls.append(entry)
        payload["tool_calls"] = calls

    return payload


def _new_usage() -> dict:
    return {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _accumulate_usage(total: dict, usage) -> None:
    """
    Cộng dồn token qua các lượt gọi LLM.

    Một lần chạy agent gọi LLM nhiều lần (mỗi vòng lặp một lần, cộng các
    sub-agent), nên con số của lượt cuối không phản ánh chi phí thật.
    """
    if usage is None:
        return

    total["calls"] += 1
    total["prompt_tokens"] += usage.prompt_tokens or 0
    total["completion_tokens"] += usage.completion_tokens or 0
    total["total_tokens"] += usage.total_tokens or 0


def _print_usage(total: dict) -> None:
    if not total["calls"]:
        return

    # Với model có thinking, total lớn hơn prompt + completion vì token suy luận
    # nội bộ được tính riêng. total mới là con số dùng để tính tiền.
    accounted = total["prompt_tokens"] + total["completion_tokens"]
    hidden = total["total_tokens"] - accounted

    line = (
        f"  [cost] {total['calls']} lượt gọi LLM | "
        f"prompt {total['prompt_tokens']} + completion {total['completion_tokens']}"
    )
    if hidden > 0:
        line += f" + thinking {hidden}"
    print(f"{line} = {total['total_tokens']} token")


def _no_event(_type: str, **_data) -> None:
    pass


def run_tool_loop(
    llm,
    model: str,
    messages: list[dict],
    tool_schemas: list,
    dispatch: dict,
    api: HAutoMLClient,
    usage: dict,
    agent: str = "manager",
    emit=None,
    max_steps: int = MAX_STEPS,
) -> str | None:
    """
    Vòng tool-calling: gọi LLM, chạy tool nó yêu cầu, lặp tới khi có câu trả lời.

    `messages` được nối thêm tại chỗ, nên phiên chat giữ được lịch sử còn
    sub-agent thì truyền vào một list mới mỗi lần được giao việc.

    Args:
        agent: Tên agent đang chạy, gắn vào mọi sự kiện để frontend biết bước
            nào thuộc agent nào.
        emit: emit(type, **data) - nhận sự kiện "llm_call" và "tool_call".

    Returns:
        Câu trả lời cuối, hoặc None nếu chạy hết max_steps mà chưa xong.
    """
    emit = emit or _no_event

    for _ in range(max_steps):
        request: dict = {"model": model, "messages": messages}
        if tool_schemas:
            request.update(tools=tool_schemas, tool_choice="auto")

        response = llm.chat.completions.create(**request)
        _accumulate_usage(usage, response.usage)
        if response.usage is not None:
            emit(
                "llm_call",
                agent=agent,
                prompt_tokens=response.usage.prompt_tokens or 0,
                completion_tokens=response.usage.completion_tokens or 0,
                total_tokens=response.usage.total_tokens or 0,
            )

        message = response.choices[0].message
        messages.append(_assistant_message(message))

        # Không gọi tool nữa nghĩa là agent đã có câu trả lời cuối.
        if not message.tool_calls:
            return message.content or ""

        for call in message.tool_calls:
            # Gán trước: nếu json.loads ném lỗi thì nhánh báo sự kiện bên dưới
            # vẫn có biến để dùng, thay vì NameError hoặc lấy nhầm giá trị còn
            # sót của tool trước đó.
            arguments: dict = {}
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError as error:
                result = {"ok": False, "error": f"Tham số tool không phải JSON hợp lệ: {error}"}
            else:
                if not isinstance(arguments, dict):
                    arguments = {}
                emit(
                    "tool_start",
                    agent=agent,
                    name=call.function.name,
                    arguments=_redact(arguments),
                )
                with tracing.observe(
                    call.function.name, as_type="tool", input=_redact(arguments), metadata={"agent": agent},
                ) as observation:
                    result = _call_tool(api, dispatch, call.function.name, arguments)
                    tracing.end(observation, output=result, warning=None if result.get("ok") else result.get("error"))

            emit(
                "tool_call",
                agent=agent,
                name=call.function.name,
                arguments=_redact(arguments),
                ok=bool(result.get("ok")),
                error=result.get("error"),
            )

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    return None


def run_agent(
    prompt: str,
    base_url: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    verbose: bool = True,
    on_event=None,
) -> str:
    """
    Chạy hệ thống agent trên MỘT prompt rồi trả câu trả lời cuối.

    Dựng một phiên chat dùng một lần - cùng đường đi với khung chat trên web,
    nên CLI và benchmark đo đúng thứ người dùng thật nhận được.

    Args:
        prompt: Yêu cầu của người dùng, bằng ngôn ngữ tự nhiên.
        base_url: URL backend HAutoML. None = HAUTOML_BASE_URL hoặc localhost:9996.
        provider: openrouter | google | openai | azure. None = LLM_PROVIDER.
        model: Slug model. None = LLM_MODEL hoặc mặc định của provider.
        verbose: In ra từng bước của các agent và tổng token đã dùng.
        on_event: Hàm nhận từng sự kiện (dict có "type", "agent"...), dùng để
            đo đạc. Xem agent/events.py.
    """
    # Import ở đây: chat.py import ngược lại module này.
    from agent.chat import ChatSession, _flush_tracer

    session = ChatSession(base_url=base_url, provider=provider, model=model, verbose=verbose)
    if on_event is not None:
        session.events.subscribe(on_event)

    try:
        if verbose:
            print(f"  [llm] {session.config.name} / {session.config.model}")
            if not session.auth.get("ok"):
                print(f"  [auth] {session.auth.get('error')}")
        return session.send(prompt)
    finally:
        if verbose:
            _print_usage(session.usage)
            if session.watcher.active():
                print(
                    "  [job] Job vẫn chạy nền trên backend. Hỏi lại sau "
                    "(\"job của tôi tới đâu rồi\") để xem kết quả."
                )
        session.close()
        _flush_tracer()
