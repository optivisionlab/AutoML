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
