"""
Cấu hình nhà cung cấp LLM.

OpenRouter, Google AI Studio, OpenAI và Azure OpenAI đều nói chuẩn OpenAI Chat
Completions, nên dùng chung một code path (agent_openai.py).

Ba provider đầu chỉ khác nhau base_url + tên biến chứa key. Azure là ngoại lệ:
xác thực bằng header `api-key`, cần `api-version`, và "model" thực chất là TÊN
DEPLOYMENT do bạn đặt trên portal chứ không phải tên model. Vì vậy nó cần một
class client riêng (`AzureOpenAI`) - xem build_client().

Thứ tự ưu tiên khi chọn provider: tham số hàm > biến LLM_PROVIDER > openrouter.
"""

# Standard libraries
import os
from dataclasses import dataclass

# Third party libraries
from dotenv import load_dotenv


# Load file .env
load_dotenv()


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
}

SUPPORTED = tuple(sorted(_PROVIDERS))


def _first_env(*names: str) -> str | None:
    return next((os.getenv(name) for name in names if os.getenv(name)), None)


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
        return ProviderConfig(
            name=name,
            kind=spec["kind"],
            api_key=api_key,
            model=resolved_model,
            base_url=spec["base_url"],
        )

    # Azure cần thêm endpoint và tên deployment, không có giá trị mặc định hợp lý.
    endpoint = _first_env("AZURE_OPENAI_ENDPOINT", "AZURE_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "Provider 'azure' cần AZURE_OPENAI_ENDPOINT, "
            "dạng https://<tên-resource>.openai.azure.com/"
        )

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


def build_client(config: ProviderConfig, max_retries: int = 5):
    """
    Dựng client SDK phù hợp với provider.

    Mọi class ở đây đều phơi cùng một giao diện `client.chat.completions.create()`,
    nên tầng agent không cần biết đang nói với provider nào.

    Khi Langfuse được cấu hình, import từ langfuse.openai thay vì openai gốc.
    Lưu ý: langfuse.openai KHÔNG trả về class con - nó monkey-patch phương thức
    `chat.completions.create` của chính thư viện openai ngay lúc import. Class
    nhận được vẫn là openai.OpenAI, nhưng lời gọi đã được ghi lại. Vì thế phải
    import có điều kiện: không cấu hình Langfuse thì không patch gì cả.

    max_retries cao hơn mặc định (2) vì tier miễn phí của Gemini/OpenRouter hay
    trả 503 UNAVAILABLE khi quá tải - lỗi tạm thời, retry là hết.
    """
    if tracing_enabled():
        from langfuse.openai import AzureOpenAI, OpenAI
    else:
        from openai import AzureOpenAI, OpenAI

    if config.kind == "azure":
        return AzureOpenAI(
            api_key=config.api_key,
            azure_endpoint=config.endpoint,
            api_version=config.api_version,
            max_retries=max_retries,
        )

    return OpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        max_retries=max_retries,
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
