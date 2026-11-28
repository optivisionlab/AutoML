"""
Cấu hình nhà cung cấp LLM.

OpenRouter, Google AI Studio, OpenAI, FPT AI và Azure OpenAI đều nói chuẩn
OpenAI Chat Completions, nên dùng chung một code path (agent_openai.py).

Các provider ngoài Azure chỉ khác nhau base_url + tên biến chứa key. Azure là ngoại lệ:
xác thực bằng header `api-key`, cần `api-version`, và "model" thực chất là TÊN
DEPLOYMENT do bạn đặt trên portal chứ không phải tên model. Vì vậy nó cần một
class client riêng (`AzureOpenAI`) - xem build_client().

Thứ tự ưu tiên khi chọn provider: tham số hàm > biến LLM_PROVIDER > openrouter.
"""

# Standard libraries
import os
import re
from dataclasses import dataclass

# Third party libraries
from dotenv import load_dotenv


# Load file .env
load_dotenv()


# Thời gian chờ MỘT lời gọi LLM (giây). SDK mặc định 600 giây và còn thử lại
# tới max_retries lần, nên provider treo có thể giữ lượt chat gần một giờ. Lời
# gọi chậm nhất đo được trong benchmark là ~169 giây (p99 ~37 giây).
DEFAULT_LLM_TIMEOUT = 300.0


def llm_timeout() -> float:
    """AGENT_LLM_TIMEOUT trong .env (giây), không đặt hoặc sai thì dùng mặc định."""
    try:
        value = float(os.getenv("AGENT_LLM_TIMEOUT", "").strip() or DEFAULT_LLM_TIMEOUT)
    except ValueError:
        return DEFAULT_LLM_TIMEOUT
    return value if value > 0 else DEFAULT_LLM_TIMEOUT


# api-version GA của Azure, dùng khi không khai báo gì.
# Model mới có thể cần bản mới hơn - xem ghi chú trong README.
DEFAULT_AZURE_API_VERSION = "2024-10-21"


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    kind: str                       # "openai" | "azure" - quyết định class client
    api_key: str
    model: str                      # với azure: TÊN DEPLOYMENT, không phải tên model
    base_url: str | None = None     # provider chuẩn OpenAI
    endpoint: str | None = None     # azure: endpoint của resource
    api_version: str | None = None  # azure: api-version


# Slug model thay đổi theo thời gian. Tra tên chính xác tại:
#   OpenRouter -> https://openrouter.ai/models
#   Google     -> https://ai.google.dev/gemini-api/docs/models
#   Azure      -> tên deployment trong Azure AI Foundry / portal của bạn
_PROVIDERS = {
    "openrouter": {
        "kind": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": ("OPENROUTER_API_KEY",),
        "default_model": "anthropic/claude-sonnet-4.6",
    },
    "google": {
        "kind": "openai",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "default_model": "gemini-3.8-flash",
    },
    "openai": {
        "kind": "openai",
        "base_url": "https://api.openai.com/v1",
        "key_env": ("OPENAI_API_KEY",),
        "default_model": "gpt-5.2",
    },
    "azure": {
        "kind": "azure",
        "base_url": None,
        "key_env": ("AZURE_OPENAI_API_KEY", "AZURE_API_KEY"),
        # Không có mặc định: tên deployment do bạn tự đặt, không đoán được.
        "default_model": None,
    },
    # FPT AI Marketplace / AI Factory - cũng theo chuẩn OpenAI. URL đổi theo sản
    # phẩm FPT bạn đăng ký, nên đặt FPT_BASE_URL đúng như trang lấy key ghi.
    "fpt": {
        "kind": "openai",
        "base_url": "https://token-api.fpt.ai/v1",
        "base_url_env": "FPT_BASE_URL",
        "key_env": ("FPT_API_KEY",),
        # Danh mục model FPT thay đổi theo gói, không đoán - đặt LLM_MODEL.
        "default_model": None,
    },
}

SUPPORTED = tuple(sorted(_PROVIDERS))

# Biến môi trường chứa bí mật: giá trị THẬT của chúng bị che trong log và lỗi.
_SECRET_ENVS = tuple(dict.fromkeys(
    [name for spec in _PROVIDERS.values() for name in spec["key_env"]]
    + ["ANTHROPIC_API_KEY", "LANGFUSE_SECRET_KEY", "AGENT_PASSWORD"]
))
# Dạng bí mật hay gặp, kể cả bản provider in lại một phần: key OpenAI/OpenRouter
# (sk-...), key Google (AIza...), header Bearer và JWT (access token của người dùng).
_SECRET_PATTERNS = re.compile(
    r"sk-[A-Za-z0-9_\-*]{6,}|AIza[0-9A-Za-z_\-]{10,}|Bearer\s+[A-Za-z0-9._~+/=\-]+"
    r"|eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"
)


def redact_secrets(text) -> str:
    """Che API key, token và mật khẩu trong một đoạn chữ."""
    text = str(text)
    for name in _SECRET_ENVS:
        value = os.getenv(name)
        if value and len(value) >= 6:
            text = text.replace(value, "***")
    return _SECRET_PATTERNS.sub("***", text)


def _redact_value(value):
    """redact_secrets cho body lỗi của provider (chuỗi, dict, list lồng nhau)."""
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _sanitized(client_class):
    """
    Lớp con của OpenAI / AzureOpenAI che bí mật trong lỗi HTTP NGAY lúc SDK tạo lỗi.

    Lỗi xác thực của provider có thể in lại (một phần) API key. Che ở đây - nơi
    mọi lỗi HTTP của SDK được dựng (_make_status_error) - thì mọi thứ phía sau chỉ
    thấy bản đã che: wrapper langfuse.openai (nó ghi log và gửi str(lỗi) lên
    Langfuse làm status_message TRƯỚC khi code agent bắt được lỗi), log server, và
    describe_error. Che bằng mask của Langfuse không đủ: mask không áp cho status_message.
    """

    class Sanitized(client_class):
        def _make_status_error(self, err_msg, *, body, response):
            return super()._make_status_error(redact_secrets(err_msg), body=_redact_value(body), response=response)

    Sanitized.__name__ = Sanitized.__qualname__ = client_class.__name__
    return Sanitized


def _first_env(*names: str) -> str | None:
    return next((os.getenv(name) for name in names if os.getenv(name)), None)


def _azure_base(endpoint: str) -> str:
    """
    Chỉ giữ scheme + host của endpoint Azure.

    Portal Azure hiện hiển thị URL dạng `https://<resource>.cognitiveservices.azure.com/openai/v1`.
    Dán nguyên vào thì SDK AzureOpenAI nối thêm `/openai/deployments/...` thành
    `/openai/v1/openai/deployments/...` và nhận 404 "Resource not found" - trông
    như sai key nhưng thực ra key vẫn đúng.
    """
    from urllib.parse import urlparse

    parsed = urlparse(endpoint.strip())
    if not parsed.scheme or not parsed.netloc:
        return endpoint
    return f"{parsed.scheme}://{parsed.netloc}/"


def resolve(provider: str | None = None, model: str | None = None) -> ProviderConfig:
    """
    Dựng cấu hình provider từ tham số và biến môi trường.

    Raises:
        ValueError: provider không nằm trong danh sách hỗ trợ.
        RuntimeError: thiếu API key, hoặc thiếu cấu hình bắt buộc của Azure.
    """
    name = (provider or os.getenv("LLM_PROVIDER") or "openrouter").lower()

    if name not in _PROVIDERS:
        raise ValueError(f"Provider không hỗ trợ: {name!r}. Chọn một trong {SUPPORTED}")

    spec = _PROVIDERS[name]

    api_key = _first_env(*spec["key_env"])
    if not api_key:
        raise RuntimeError(
            f"Chưa có API key cho provider {name!r}. "
            f"Đặt một trong các biến môi trường: {', '.join(spec['key_env'])}"
        )

    resolved_model = model or os.getenv("LLM_MODEL") or spec["default_model"]

    if spec["kind"] != "azure":
        if not resolved_model:
            raise RuntimeError(
                f"Provider {name!r} không có model mặc định. Đặt LLM_MODEL "
                "(hoặc truyền --model) bằng tên model trong trang quản lý của provider."
            )
        base_url = os.getenv(spec.get("base_url_env") or "") or spec["base_url"]
        return ProviderConfig(
            name=name,
            kind=spec["kind"],
            api_key=api_key,
            model=resolved_model,
            base_url=base_url,
        )

    # Azure cần thêm endpoint và tên deployment, không có giá trị mặc định hợp lý.
    endpoint = _first_env("AZURE_OPENAI_ENDPOINT", "AZURE_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "Provider 'azure' cần AZURE_OPENAI_ENDPOINT, "
            "dạng https://<tên-resource>.openai.azure.com/"
        )
    endpoint = _azure_base(endpoint)

    deployment = resolved_model or _first_env("AZURE_OPENAI_DEPLOYMENT")
    if not deployment:
        raise RuntimeError(
            "Provider 'azure' cần tên deployment. Đặt AZURE_OPENAI_DEPLOYMENT "
            "(hoặc LLM_MODEL, hoặc truyền --model). Đây là tên bạn đặt khi deploy "
            "model trên Azure, không phải tên model."
        )

    return ProviderConfig(
        name=name,
        kind="azure",
        api_key=api_key,
        model=deployment,
        endpoint=endpoint,
        api_version=(
            _first_env("AZURE_OPENAI_API_VERSION", "OPENAI_API_VERSION")
            or DEFAULT_AZURE_API_VERSION
        ),
    )


def tracing_enabled() -> bool:
    """
    Bật Langfuse khi có đủ cặp key.

    Không có key thì agent chạy y như cũ và không cần cài langfuse - việc theo
    dõi là tuỳ chọn, không phải phụ thuộc bắt buộc.
    """
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def build_client(config: ProviderConfig, max_retries: int = 0):
    """
    Dựng client SDK phù hợp với provider.

    Mọi class ở đây đều phơi cùng một giao diện `client.chat.completions.create()`,
    nên tầng agent không cần biết đang nói với provider nào.

    Khi Langfuse được cấu hình, import từ langfuse.openai thay vì openai gốc.
    Lưu ý: langfuse.openai KHÔNG trả về class con - nó monkey-patch phương thức
    `chat.completions.create` của chính thư viện openai ngay lúc import. Class
    nhận được vẫn là openai.OpenAI, nhưng lời gọi đã được ghi lại. Vì thế phải
    import có điều kiện: không cấu hình Langfuse thì không patch gì cả.

    max_retries = 0: SDK KHÔNG tự thử lại. Vòng thử lại nằm ở agent_openai.create_completion (audit AG-03):
    SDK dùng cùng một timeout cho mọi lần thử và không có trần tổng thời gian, nên provider treo từng giữ lượt
    chat tới ~30 phút. Ở đó mỗi lần thử bị kẹp theo thời gian còn lại của lượt (AGENT_TURN_DEADLINE_SECONDS),
    vẫn thử lại 503 / 429 nhiều lần (AGENT_LLM_MAX_RETRIES) cho tier miễn phí của Gemini / OpenRouter.
    """
    if tracing_enabled():
        from langfuse.openai import AzureOpenAI, OpenAI
    else:
        from openai import AzureOpenAI, OpenAI

    if config.kind == "azure":
        return _sanitized(AzureOpenAI)(
            api_key=config.api_key,
            azure_endpoint=config.endpoint,
            api_version=config.api_version,
            max_retries=max_retries,
            timeout=llm_timeout(),
        )

    return _sanitized(OpenAI)(
        base_url=config.base_url,
        api_key=config.api_key,
        max_retries=max_retries,
        timeout=llm_timeout(),
    )


def get_tracer():
    """
    Client Langfuse, hoặc None nếu chưa cấu hình.

    Dùng để gộp toàn bộ lời gọi LLM của một lượt agent vào chung một trace -
    nếu không, mỗi lời gọi thành một trace rời và không thấy được tổng chi phí
    của cả lượt.
    """
    if not tracing_enabled():
        return None

    from langfuse import get_client

    return get_client()
