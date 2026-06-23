"""
HAgent Bridge — Cấu hình hệ thống

Tải TẤT CẢ cấu hình từ file hagent.yaml.
KHÔNG có giá trị nào bị hard-code trong mã nguồn Python.
Biến môi trường có thể ghi đè giá trị trong YAML.
"""

import os
from pathlib import Path
from functools import lru_cache
from typing import Any

import yaml


# ── Đường dẫn ────────────────────────────────────────────

# Tìm file hagent.yaml — ưu tiên biến môi trường, sau đó tìm tự động
_DEFAULT_CONFIG_PATHS = [
    Path(__file__).parent.parent / "hagent.yaml",            # hagent/hagent.yaml
    Path(__file__).parent.parent.parent / "hagent.yaml",     # backend/hagent.yaml
    Path.home() / ".hagent" / "hagent.yaml",               # ~/.hagent/hagent.yaml
]


def _find_config_path() -> Path:
    """Tìm file cấu hình hagent.yaml theo thứ tự ưu tiên."""
    # Ưu tiên biến môi trường
    env_path = os.getenv("HAGENT_CONFIG")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"HAGENT_CONFIG trỏ tới file không tồn tại: {env_path}")

    # Tìm tự động
    for p in _DEFAULT_CONFIG_PATHS:
        if p.exists():
            return p

    raise FileNotFoundError(
        "Không tìm thấy hagent.yaml. "
        "Đặt biến HAGENT_CONFIG hoặc đặt file tại: "
        + ", ".join(str(p) for p in _DEFAULT_CONFIG_PATHS)
    )


def _resolve_env_vars(value: Any) -> Any:
    """
    Thay thế chuỗi dạng ${VAR_NAME} bằng giá trị biến môi trường.
    Hỗ trợ cả giá trị mặc định: ${VAR_NAME:-default}.
    """
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        inner = value[2:-1]
        if ":-" in inner:
            var_name, default = inner.split(":-", 1)
            return os.getenv(var_name, default)
        return os.getenv(inner, "")
    return value


def _deep_resolve(data: Any) -> Any:
    """Đệ quy thay thế tất cả biến môi trường trong cấu trúc dữ liệu."""
    if isinstance(data, dict):
        return {k: _deep_resolve(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_deep_resolve(item) for item in data]
    else:
        return _resolve_env_vars(data)


# ── Tải cấu hình ────────────────────────────────────────

@lru_cache()
def load_config() -> dict:
    """
    Tải và cache cấu hình từ hagent.yaml.
    Tự động resolve các biến môi trường dạng ${VAR}.
    """
    config_path = _find_config_path()

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return _deep_resolve(raw)


# ── Các hàm truy xuất cấu hình ──────────────────────────


def get_bridge_config() -> dict:
    """Lấy cấu hình Bridge service."""
    cfg = load_config()
    bridge = cfg.get("bridge", {})
    # Cho phép ghi đè qua biến môi trường
    bridge["host"] = os.getenv("BRIDGE_HOST", bridge.get("host", "0.0.0.0"))
    bridge["port"] = int(os.getenv("BRIDGE_PORT", bridge.get("port", 9900)))
    bridge["cors_origins"] = bridge.get("cors_origins", ["http://localhost:3000"])
    return bridge


def get_gateway_config() -> dict:
    """Lấy cấu hình HAgent Gateway."""
    cfg = load_config()
    gw = cfg.get("gateway", {})
    gw["host"] = os.getenv("GATEWAY_HOST", gw.get("host", "0.0.0.0"))
    gw["port"] = int(os.getenv("GATEWAY_PORT", gw.get("port", 18789)))
    return gw


def get_hautoml_config() -> dict:
    """Lấy cấu hình HAutoML backend."""
    cfg = load_config()
    h = cfg.get("hautoml", {})
    h["base_url"] = os.getenv("HAUTOML_BASE_URL", h.get("base_url", "http://localhost:8080"))
    return h


def get_mongodb_config() -> dict:
    """Lấy cấu hình MongoDB."""
    cfg = load_config()
    m = cfg.get("mongodb", {})
    m["connect"] = os.getenv("MONGODB_CONNECT", m.get("connect", "localhost:27017"))
    m["db_name"] = os.getenv("MONGODB_DB_NAME", m.get("db_name", "hagent"))
    m["conversation_ttl_hours"] = int(
        os.getenv("CONVERSATION_TTL_HOURS", m.get("conversation_ttl_hours", 24))
    )
    return m


def get_auth_config() -> dict:
    """Lấy cấu hình JWT authentication."""
    cfg = load_config()
    a = cfg.get("auth", {})
    a["secret_key"] = os.getenv("SECRET_KEY", a.get("secret_key", ""))
    a["algorithm"] = os.getenv("ALGORITHM", a.get("algorithm", "HS256"))
    return a


def get_hooks_config() -> dict:
    """Lấy cấu hình webhook hooks."""
    cfg = load_config()
    h = cfg.get("hooks", {})
    h["token"] = os.getenv("HAGENT_HOOKS_TOKEN", h.get("token", ""))
    return h


def get_world_state_config() -> dict:
    """Lấy cấu hình World State."""
    cfg = load_config()
    ws = cfg.get("world_state", {}) or {}
    ws["collection_name"] = os.getenv(
        "WORLD_STATE_COLLECTION", ws.get("collection_name", "world_states")
    )
    ws["ttl_seconds"] = int(
        os.getenv("WORLD_STATE_TTL_SECONDS", ws.get("ttl_seconds", 86400))
    )
    ws["snapshot_size_limit"] = int(
        os.getenv("WORLD_STATE_SNAPSHOT_SIZE_LIMIT", ws.get("snapshot_size_limit", 16384))
    )
    return ws


# ── DeerFlow-AutoML config accessors ────────────────────


def get_llm_config() -> dict:
    """Lấy cấu hình LLM providers."""
    cfg = load_config()
    llm = cfg.get("llm", {}) or {}
    llm["default_model"] = os.getenv("LLM_DEFAULT_MODEL", llm.get("default_model", ""))
    return llm


def get_llm_models() -> list[dict]:
    """Lấy danh sách model configs đã resolve env vars."""
    llm = get_llm_config()
    return llm.get("models", [])


def get_agent_config() -> dict:
    """Lấy cấu hình agent orchestration."""
    cfg = load_config()
    agent = cfg.get("agent", {}) or {}
    agent["max_iterations"] = int(
        os.getenv("AGENT_MAX_ITERATIONS", agent.get("max_iterations", 10))
    )
    agent["timeout_seconds"] = int(
        os.getenv("AGENT_TIMEOUT_SECONDS", agent.get("timeout_seconds", 120))
    )
    return agent


def get_routing_config() -> dict[str, list[str]]:
    """
    Lấy routing keywords cho từng sub-agent.

    Returns:
        Dict[agent_name, list[keyword]], ví dụ:
        {"data_analyst": ["dataset", "data", ...], ...}
    """
    agent = get_agent_config()
    routing_raw = agent.get("routing", {}) or {}
    result = {}
    for agent_name, conf in routing_raw.items():
        if isinstance(conf, dict):
            result[agent_name] = conf.get("keywords", [])
        elif isinstance(conf, list):
            result[agent_name] = conf
    return result


def get_suggestions() -> list[str]:
    """Lấy danh sách gợi ý chat mặc định."""
    agent = get_agent_config()
    return agent.get("suggestions", [])


def get_cache_config() -> dict:
    """Lấy cấu hình cache cho tool results."""
    agent = get_agent_config()
    cache = agent.get("cache", {}) or {}
    cache["enabled"] = os.getenv("AGENT_CACHE_ENABLED", str(cache.get("enabled", True))).lower() in ("true", "1", "yes")
    cache["ttl_seconds"] = int(os.getenv("AGENT_CACHE_TTL", cache.get("ttl_seconds", 300)))
    cache["max_entries"] = int(os.getenv("AGENT_CACHE_MAX_ENTRIES", cache.get("max_entries", 100)))
    return cache


def get_error_messages() -> dict[str, str]:
    """Lấy cấu hình thông báo lỗi."""
    cfg = load_config()
    # Gộp từ cả proxy.error_messages (legacy) và error_messages (mới)
    proxy = cfg.get("proxy", {}) or {}
    legacy = proxy.get("error_messages", {}) or {}
    new = cfg.get("error_messages", {}) or {}
    # Mới ghi đè cũ
    merged = {**legacy, **new}
    return merged


def load_prompt_file(relative_path: str | None = None) -> str:
    """
    Đọc nội dung file prompt (.md) — tương đối so với thư mục hagent/.

    Args:
        relative_path: Đường dẫn tương đối từ thư mục chứa hagent.yaml.
                       Nếu None, lấy từ agent.system_prompt_path trong config.

    Returns:
        Nội dung file prompt dạng string.
    """
    if not relative_path:
        agent = get_agent_config()
        relative_path = agent.get("system_prompt_path", "./prompts/coordinator.md")

    # Resolve đường dẫn tương đối so với thư mục chứa config
    config_dir = _find_config_path().parent
    prompt_path = config_dir / relative_path

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file prompt tại {prompt_path}. "
            f"Kiểm tra agent.system_prompt_path trong hagent.yaml."
        )

    return prompt_path.read_text(encoding="utf-8")

