"""
HAgent Bridge — Pydantic schemas

Định nghĩa các schema cho request/response của API.
Tất cả giá trị mặc định được tải từ hagent.yaml thông qua config.py.
"""

from datetime import datetime
from pydantic import BaseModel, Field


# ─── Chat ────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Schema cho request chat — provider và model là tùy chọn."""
    message: str = Field(..., description="Nội dung tin nhắn")
    conversation_id: str | None = Field(None, description="ID cuộc hội thoại (tạo mới nếu null)")
    context: dict | None = Field(None, description="Ngữ cảnh bổ sung")
    provider: str | None = Field(None, description="Provider LLM — xem hagent.yaml")
    model: str | None = Field(None, description="Model cụ thể — xem hagent.yaml")


class ChatResponse(BaseModel):
    """Schema cho response chat."""
    message: str
    conversation_id: str
    sources: list[str] = []
    suggestions: list[str] = []
    provider: str = ""
    model: str = ""


# ─── Health ──────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Schema cho health check — tất cả giá trị từ YAML."""
    hagent_url: str
    connected: bool
    hautoml_connected: bool
    mode: str  # "hagent" hoặc "direct"
    active_provider: str
    active_model: str
    available_providers: list[str]


# ─── Suggestions ─────────────────────────────────────────


class SuggestionsResponse(BaseModel):
    """Schema cho gợi ý chat ban đầu."""
    suggestions: list[str]


# ─── Providers ───────────────────────────────────────────


class ProviderInfo(BaseModel):
    """Thông tin một provider — dữ liệu từ YAML."""
    name: str
    provider_id: str
    models: list[str]
    available: bool
    description: str = ""


class ProvidersResponse(BaseModel):
    """Danh sách tất cả providers — dữ liệu từ YAML."""
    default_provider: str
    default_model: str
    providers: list[ProviderInfo]


# ─── Conversation (MongoDB) ─────────────────────────────


class ConversationMessage(BaseModel):
    """Một tin nhắn trong cuộc hội thoại."""
    role: str
    content: str
    timestamp: datetime | None = None
    provider: str = ""
    model: str = ""


class Conversation(BaseModel):
    """Một cuộc hội thoại đầy đủ."""
    conversation_id: str
    user_id: str
    messages: list[ConversationMessage] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None
    provider: str = ""
    model: str = ""
