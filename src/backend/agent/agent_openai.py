"""
Agent xác thực chạy qua API chuẩn OpenAI Chat Completions.

Dùng được với OpenRouter, Google AI Studio và OpenAI - cả ba đều nói cùng một
giao thức, chỉ khác base_url/key/model (xem providers.py).

File này tự viết vòng lặp gọi tool thay vì dùng helper có sẵn của SDK. Dài hơn
nhưng cho phép quan sát và chen vào từng bước - đó là chỗ cắm callback báo tiến
độ cho training, và cũng là lý do ba lỗi khó (thought_signature của Gemini,
max_tokens bị thinking ăn hết) truy ra được.

Chạy:
    cd src/backend
    python -m agent.cli --provider openrouter "Đăng ký tài khoản ... rồi đăng nhập"
"""

# Standard libraries
import json
from contextlib import nullcontext

# Local modules
from agent import providers, tools
from agent.api_client import HAutoMLClient
from agent.prompts import SYSTEM_PROMPT


# Số vòng lặp tối đa, chặn trường hợp model gọi tool luẩn quẩn không dừng.
MAX_STEPS = 12

# Những khoá bị che khi in log, tránh lộ mật khẩu ra terminal.
_SECRET_KEYS = {"password", "new_password", "confirm_password"}


# Schema tool theo định dạng OpenAI function calling.
# Cố ý không dùng "additionalProperties" vì một số provider (Gemini) chỉ nhận
# một tập con của JSON Schema.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "signup",
            "description": "Đăng ký một tài khoản mới trên hệ thống HAutoML.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Tên đăng nhập, tối thiểu 3 ký tự."},
                    "email": {"type": "string", "description": "Địa chỉ email, phải đúng định dạng."},
                    "password": {"type": "string", "description": "Mật khẩu của tài khoản."},
                    "full_name": {"type": "string", "description": "Họ và tên đầy đủ."},
                    "gender": {"type": "string", "description": 'Giới tính, ví dụ "male" hoặc "female".'},
                    "date": {"type": "string", "description": "Ngày sinh dạng dd/mm/yyyy."},
                    "number": {"type": "string", "description": "Số điện thoại, tối thiểu 10 ký tự."},
                },
                "required": ["username", "email", "password", "full_name", "gender", "date", "number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "login",
            "description": "Đăng nhập vào hệ thống HAutoML. Token được lưu lại cho các tool sau.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Tên đăng nhập hoặc email."},
                    "password": {"type": "string", "description": "Mật khẩu."},
                },
                "required": ["username", "password"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_me",
            "description": "Lấy thông tin hồ sơ của tài khoản đang đăng nhập. Phải login trước.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "logout",
            "description": "Đăng xuất tài khoản hiện tại.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resend_verification_email",
            "description": "Yêu cầu hệ thống gửi lại email xác thực cho một tài khoản chưa xác thực.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Email của tài khoản cần gửi lại link xác thực."},
                },
                "required": ["email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_email",
            "description": (
                "Xác thực email của tài khoản bằng token trong link người dùng nhận được. "
                "Xác thực xong là đăng nhập luôn, không cần gọi login nữa."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "token": {
                        "type": "string",
                        "description": (
                            "Token xác thực. Nhận cả token thuần lẫn nguyên link "
                            "dạng https://.../verify-email?token=..."
                        ),
                    },
                },
                "required": ["token"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_my_datasets",
            "description": (
                "Liệt kê các dataset của tài khoản đang đăng nhập. Phải login trước. "
                "Không cần truyền user_id, tool tự lấy."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dataset_info",
            "description": (
                "Xem metadata một dataset (tên, loại bài toán, ngày tạo). "
                "KHÔNG có tên cột - muốn biết các thuộc tính thì dùng get_dataset_schema."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "ID dataset, lấy từ trường _id trong kết quả liệt kê dataset.",
                    },
                },
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dataset_schema",
            "description": (
                "Lấy danh sách thuộc tính (cột) của một dataset, kèm kiểu dữ liệu, số giá trị "
                "khác nhau, số giá trị thiếu, vài giá trị mẫu, và cột nào dùng được làm biến "
                "mục tiêu. Dùng tool này khi người dùng hỏi dataset có những cột/thuộc tính gì."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "ID dataset, lấy từ trường _id trong kết quả liệt kê dataset.",
                    },
                    "problem_type": {
                        "type": "string",
                        "description": (
                            "classification hoặc regression. Bỏ trống thì tự lấy theo "
                            "dataType của dataset."
                        ),
                    },
                },
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_metrics",
            "description": (
                "Danh sách metric hợp lệ để xếp hạng model, theo loại bài toán. "
                "Gọi trước khi huấn luyện để biết metric_sort điền được gì."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "problem_type": {
                        "type": "string",
                        "enum": ["classification", "regression"],
                        "description": "Loại bài toán của dataset.",
                    },
                },
                "required": ["problem_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_training",
            "description": (
                "Khởi tạo job huấn luyện AutoML trên một dataset có sẵn. Trả về job_id NGAY, "
                "job chạy nền vài phút tới hàng giờ - KHÔNG có kết quả ngay. "
                "Bắt buộc gọi get_dataset_schema trước để biết tên cột thật."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "ID dataset, lấy từ list_my_datasets.",
                    },
                    "target": {
                        "type": "string",
                        "description": "Cột mục tiêu. Phải nằm trong target_candidates của schema.",
                    },
                    "list_feature": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Các cột đặc trưng đầu vào. Không được chứa cột mục tiêu.",
                    },
                    "metric_sort": {
                        "type": "string",
                        "description": "Metric xếp hạng model, lấy từ list_metrics.",
                    },
                    "problem_type": {
                        "type": "string",
                        "enum": ["classification", "regression"],
                        "description": "Bỏ trống thì lấy theo dataType của dataset.",
                    },
                    "search_algorithm": {
                        "type": "string",
                        "enum": ["grid_search", "genetic_algorithm", "bayesian_search"],
                        "description": "Mặc định grid_search.",
                    },
                    "max_time": {
                        "type": "integer",
                        "description": "Giới hạn thời gian tính bằng giây, 60 đến 86400. Mặc định 900.",
                    },
                },
                "required": ["dataset_id", "target", "list_feature", "metric_sort"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_reference",
            "description": (
                "Đọc một tài liệu tra cứu của skill. Các tài liệu này không nằm sẵn trong "
                "hướng dẫn, chỉ có tên và mô tả. Dùng khi cần chi tiết mà hướng dẫn không đủ."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ref_id": {
                        "type": "string",
                        "description": "Định danh tài liệu, dạng <skill>/<tên>, ví dụ data-agent/dataset_schema.",
                    },
                },
                "required": ["ref_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_my_jobs",
            "description": (
                "Liệt kê các job huấn luyện của tài khoản đang đăng nhập. Phải login trước. "
                "Không cần truyền user_id, tool tự lấy."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_job_info",
            "description": "Xem chi tiết một job huấn luyện, gồm trạng thái và kết quả các model.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "job_id, lấy từ kết quả liệt kê job.",
                    },
                },
                "required": ["job_id"],
            },
        },
    },
]

# Tool chỉ dành cho môi trường phát triển, bật bằng AGENT_DEV_TOOLS=1.
DEV_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "dev_verify_account",
            "description": (
                "CHỈ DÙNG KHI PHÁT TRIỂN: xác thực ngay một tài khoản mà không cần đọc email. "
                "Dùng khi người dùng muốn thử hết luồng đăng ký -> xác thực -> đăng nhập trên "
                "máy cục bộ. Xác thực xong là đăng nhập luôn."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "ID tài khoản, lấy từ trường user.id mà tool signup trả về.",
                    },
                    "email": {"type": "string", "description": "Email của tài khoản."},
                },
                "required": ["user_id"],
            },
        },
    },
]

# Ánh xạ tên tool -> hàm trong tools.py. Mọi hàm đều nhận client làm tham số đầu.
_DISPATCH = {
    "signup": tools.signup,
    "login": tools.login,
    "get_me": tools.get_me,
    "logout": tools.logout,
    "resend_verification_email": tools.resend_verification_email,
    "verify_email": tools.verify_email,
    "list_my_datasets": tools.list_my_datasets,
    "get_dataset_info": tools.get_dataset_info,
    "get_dataset_schema": tools.get_dataset_schema,
    "read_reference": tools.read_reference,
    "list_metrics": tools.list_metrics,
    "start_training": tools.start_training,
    "list_my_jobs": tools.list_my_jobs,
    "get_job_info": tools.get_job_info,
}

_DEV_DISPATCH = {
    "dev_verify_account": tools.dev_verify_account,
}


def _active_tools() -> tuple[list, dict]:
    """
    Danh sách tool cho lần chạy này.

    Tính lúc chạy chứ không phải lúc import, để đổi AGENT_DEV_TOOLS có tác dụng
    ngay mà không cần import lại module.
    """
    if tools.dev_tools_enabled():
        return TOOL_SCHEMAS + DEV_TOOL_SCHEMAS, {**_DISPATCH, **_DEV_DISPATCH}
    return TOOL_SCHEMAS, _DISPATCH


def _redact(tool_input: dict) -> dict:
    return {
        key: ("***" if key in _SECRET_KEYS else value)
        for key, value in tool_input.items()
    }


def _call_tool(api: HAutoMLClient, dispatch: dict, name: str, arguments: dict) -> dict:
    """Gọi tool và bọc mọi lỗi thành dict, để một tool hỏng không làm chết vòng lặp."""
    handler = dispatch.get(name)
    if handler is None:
        return {"ok": False, "error": f"Tool không tồn tại: {name}"}

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

    Một lần chạy agent gọi LLM nhiều lần (mỗi vòng lặp một lần), nên con số của
    lượt cuối không phản ánh chi phí thật của cả lượt.
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


def _run_loop(
    llm,
    config,
    tool_schemas: list,
    dispatch: dict,
    prompt: str,
    base_url: str | None,
    verbose: bool,
    usage_total: dict,
    on_event=None,
) -> str:
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    with HAutoMLClient(base_url) as api:
        for _ in range(MAX_STEPS):
            response = llm.chat.completions.create(
                model=config.model,
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",
            )
            _accumulate_usage(usage_total, response.usage)
            if on_event is not None and response.usage is not None:
                on_event({
                    "type": "llm_call",
                    "prompt_tokens": response.usage.prompt_tokens or 0,
                    "completion_tokens": response.usage.completion_tokens or 0,
                    "total_tokens": response.usage.total_tokens or 0,
                })

            message = response.choices[0].message
            messages.append(_assistant_message(message))

            # Không gọi tool nữa nghĩa là agent đã có câu trả lời cuối.
            if not message.tool_calls:
                return message.content or ""

            for call in message.tool_calls:
                # Gán trước: nếu json.loads ném lỗi thì nhánh báo sự kiện bên
                # dưới vẫn có biến để dùng, thay vì NameError hoặc lấy nhầm giá
                # trị còn sót của tool trước đó.
                arguments: dict = {}
                try:
                    arguments = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError as error:
                    result = {"ok": False, "error": f"Tham số tool không phải JSON hợp lệ: {error}"}
                else:
                    if verbose:
                        shown = json.dumps(_redact(arguments), ensure_ascii=False)
                        print(f"  [tool] {call.function.name}({shown})")
                    result = _call_tool(api, dispatch, call.function.name, arguments)

                if on_event is not None:
                    on_event({
                        "type": "tool_call",
                        "name": call.function.name,
                        "arguments": _redact(arguments if isinstance(arguments, dict) else {}),
                        "ok": bool(result.get("ok")),
                        "error": result.get("error"),
                    })

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

    raise RuntimeError(
        f"Agent chạy quá {MAX_STEPS} bước mà chưa kết thúc. "
        "Xem lại log tool ở trên để biết nó lặp ở đâu."
    )


def run_agent(
    prompt: str,
    base_url: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    verbose: bool = True,
    on_event=None,
) -> str:
    """
    Chạy agent trên một prompt và trả về câu trả lời cuối cùng.

    Args:
        prompt: Yêu cầu của người dùng, bằng ngôn ngữ tự nhiên.
        base_url: URL backend HAutoML. None = HAUTOML_BASE_URL hoặc localhost:9996.
        provider: openrouter | google | openai | azure. None = LLM_PROVIDER.
        model: Slug model. None = LLM_MODEL hoặc mặc định của provider.
        verbose: In ra từng tool được gọi và tổng token đã dùng.
        on_event: Hàm nhận từng sự kiện trong lúc chạy, dùng để đo đạc hoặc
            hiển thị tiến độ. Mỗi sự kiện là dict có "type":
            "llm_call" (kèm số token) hoặc "tool_call" (kèm tên tool, tham số
            đã che mật khẩu, và ok/error).

    Returns:
        Văn bản trả lời cuối cùng của agent.
    """
    config = providers.resolve(provider, model)
    llm = providers.build_client(config)
    tool_schemas, dispatch = _active_tools()
    tracer = providers.get_tracer()
    usage_total = _new_usage()

    if verbose:
        print(f"  [llm] {config.name} / {config.model}")
        if tools.dev_tools_enabled():
            print("  [llm] tool dev đang BẬT (AGENT_DEV_TOOLS)")

    # Gộp mọi lời gọi LLM của lượt này vào một trace, để Langfuse cộng được
    # tổng chi phí của cả lượt thay vì từng lời gọi rời rạc.
    span_ctx = (
        tracer.start_as_current_observation(
            as_type="span", name="hautoml-agent", input=prompt,
        )
        if tracer is not None
        else nullcontext()
    )

    try:
        with span_ctx as span:
            if tracer is not None and verbose:
                trace_id = tracer.get_current_trace_id()
                if trace_id:
                    print(f"  [cost] Langfuse: {tracer.get_trace_url(trace_id=trace_id)}")

            answer = _run_loop(
                llm, config, tool_schemas, dispatch, prompt, base_url, verbose,
                usage_total, on_event,
            )

            if span is not None:
                span.update(output=answer)

            return answer
    finally:
        if verbose:
            _print_usage(usage_total)
        # Tiến trình CLI thoát ngay sau đây, phải flush không thì trace bị mất.
        if tracer is not None:
            tracer.flush()
