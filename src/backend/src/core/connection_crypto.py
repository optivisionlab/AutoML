"""
Mã hoá mật khẩu của kết nối database đã lưu (Fernet, khoá từ DB_CONNECTION_ENCRYPTION_KEY).

Mật khẩu chỉ được giải mã ngay lúc dựng adapter; không bao giờ trả ra API, log hay LLM.
"""
# Third-party Libraries
from cryptography.fernet import Fernet, InvalidToken

# Local Libraries
from src.config import settings


KEY_VERSION = 1


class ConnectionCryptoError(Exception):
    """Thiếu / sai khoá mã hoá, hoặc bản mã không giải được."""


def _fernet() -> Fernet:
    key = settings.DATABASE_SOURCES.ENCRYPTION_KEY
    if not key:
        raise ConnectionCryptoError(
            "Chưa cấu hình DB_CONNECTION_ENCRYPTION_KEY - tính năng kết nối database đang tắt."
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as error:
        raise ConnectionCryptoError("DB_CONNECTION_ENCRYPTION_KEY không phải khoá Fernet hợp lệ.") from error


def ensure_configured() -> None:
    """Báo lỗi sớm khi tính năng chưa bật (không có khoá)."""
    _fernet()


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as error:
        raise ConnectionCryptoError("Không giải mã được mật khẩu kết nối (khoá đã đổi?).") from error
