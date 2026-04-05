"""
HAgent Bridge — Xác thực JWT

Sử dụng chung SECRET_KEY và ALGORITHM với HAutoML backend.
Cấu hình tải từ hagent.yaml — KHÔNG hard-code.
"""

from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import decode, PyJWTError
import logging

logger = logging.getLogger(__name__)

from .config import get_auth_config

security = HTTPBearer(auto_error=False)


class TokenPayload:
    """Dữ liệu đã giải mã từ JWT token."""

    def __init__(self, payload: dict, raw_token: str = ""):
        self.user_id: str = payload.get("sub", payload.get("user_id", ""))
        self.email: str = payload.get("email", "")
        self.exp: float = payload.get("exp", 0)
        self.token_type: str = payload.get("type", "access")
        self.raw: dict = payload
        self.raw_token: str = raw_token  # Lưu raw JWT token string

    @property
    def is_expired(self) -> bool:
        """Kiểm tra token đã hết hạn chưa."""
        return datetime.now(timezone.utc).timestamp() > self.exp


def verify_jwt_token(token: str) -> TokenPayload:
    """
    Xác thực JWT token dùng secret từ hagent.yaml.
    Ném HTTPException nếu token không hợp lệ hoặc đã hết hạn.
    """
    auth_cfg = get_auth_config()

    if not auth_cfg["secret_key"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SECRET_KEY chưa được cấu hình trong hagent.yaml hoặc biến môi trường",
        )

    try:
        payload = decode(
            token,
            auth_cfg["secret_key"],
            algorithms=[auth_cfg["algorithm"]],
        )
    except PyJWTError as e:
        logger.warning(f"Lỗi JWT: {e}, secret_key length: {len(auth_cfg['secret_key']) if auth_cfg['secret_key'] else 0}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token không hợp lệ: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_payload = TokenPayload(payload, token)

    if token_payload.is_expired:
        logger.debug(f"Token expired: exp={token_payload.exp}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token_payload.token_type != "access":
        logger.debug(f"Token type invalid: expected access, got {token_payload.token_type}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Loại token không hợp lệ — yêu cầu access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_payload


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> TokenPayload:
    logger.debug(f"ALL INCOMING HEADERS IN AUTH: {request.headers}")
    if credentials is None:
        logger.debug("Missing credentials/Authorization header!")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thiếu header Authorization",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_jwt_token(credentials.credentials)


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> TokenPayload | None:
    """
    FastAPI dependency: trích xuất JWT tùy chọn (không bắt buộc).
    Trả về None nếu không có token (dùng cho endpoint công khai).
    """
    if credentials is None:
        return None
    try:
        return verify_jwt_token(credentials.credentials)
    except HTTPException:
        return None
