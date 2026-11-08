"""
Ghi các bước của hệ thống agent lên Langfuse - cùng những gì terminal in ra.

Không có file này, Langfuse chỉ thấy các lời gọi LLM nằm phẳng trong một span
(do langfuse.openai tự ghi). Với 5 agent thì không đọc được: lời gọi nào của
agent nào, tool nào chạy, trả gì, config bị chặn vì sao. Ở đây mỗi bước thành
một observation lồng đúng cấu trúc:

    agent-manager                      (agent)   một lượt chat
    ├── OpenAI-generation              (generation, langfuse.openai tự ghi)
    ├── ask_model_agent                (tool)
    │   └── model-agent                (agent)
    │       ├── OpenAI-generation
    │       ├── submit_config          (tool)
    │       │   └── validate_config    (guardrail)   kiểm bằng CODE
    │       └── ...
    └── ask_operation_agent            (tool)
        └── operation-agent            (agent)
            └── start_training         (tool)
                ├── job_status         (event)   watcher ghi từ thread nền,
                └── job_done           (event)   gắn vào đúng tool đã tạo job

Lượt chat cùng phiên được gom bằng session_id (tab Sessions trên Langfuse).

Mọi hàm đều không làm gì khi chưa cấu hình Langfuse, và không bao giờ raise -
ghi log hỏng không được làm hỏng agent.
"""

# Standard libraries
from contextlib import contextmanager

# Local modules
from agent import providers


@contextmanager
def observe(name: str, as_type: str = "span", input=None, metadata: dict | None = None):
    """Mở một observation con của observation hiện tại. Yield None khi tắt tracing."""
    tracer = providers.get_tracer()
    if tracer is None:
        yield None
        return

    with tracer.start_as_current_observation(
        name=name, as_type=as_type, input=input, metadata=metadata,
    ) as observation:
        yield observation


@contextmanager
def turn(name: str, input, session_id: str | None, user_id: str | None):
    """
    Observation gốc của một lượt chat, gắn session_id/user_id cho cả trace.

    propagate_attributes phải bọc NGOÀI observation gốc thì thuộc tính mới lan
    xuống mọi observation con, kể cả generation của langfuse.openai.
    """
    tracer = providers.get_tracer()
    if tracer is None:
        yield None
        return

    from langfuse import propagate_attributes

    with propagate_attributes(session_id=session_id, user_id=user_id, trace_name="hautoml-agent"):
        with tracer.start_as_current_observation(name=name, as_type="agent", input=input) as observation:
            yield observation


def end(observation, output=None, error: str | None = None, warning: str | None = None) -> None:
    """Ghi kết quả. error → level ERROR, warning → level WARNING (lọc được trên Langfuse)."""
    if observation is None:
        return
    level, message = None, None
    if error:
        level, message = "ERROR", error
    elif warning:
        level, message = "WARNING", warning
    try:
        observation.update(output=output, level=level, status_message=message)
    except Exception:  # noqa: BLE001
        pass


def current_context() -> dict | None:
    """
    Vị trí hiện tại trong trace: {"trace_id", "parent_span_id"}.

    Phải có CẢ parent_span_id: chỉ truyền trace_id thì Langfuse gắn sự kiện vào
    một observation cha không tồn tại, và nó không hiện trong cây trace.
    """
    tracer = providers.get_tracer()
    if tracer is None:
        return None
    try:
        trace_id = tracer.get_current_trace_id()
        span_id = tracer.get_current_observation_id()
    except Exception:  # noqa: BLE001
        return None
    if not trace_id or not span_id:
        return None
    return {"trace_id": trace_id, "parent_span_id": span_id}


def log_event(name: str, context: dict | None, payload: dict, level: str | None = None) -> None:
    """
    Ghi một sự kiện rời vào một chỗ có sẵn trong trace.

    Dùng cho watcher: nó chạy ở thread nền, sau khi lượt chat tạo job đã kết
    thúc từ lâu, nên không có observation hiện tại để lồng vào - phải chỉ đích
    danh vị trí (lấy bằng current_context() lúc tạo job).
    """
    tracer = providers.get_tracer()
    if tracer is None:
        return
    try:
        tracer.create_event(
            trace_context=context,
            name=name,
            output=payload,
            level=level,
        )
    except Exception:  # noqa: BLE001
        pass
