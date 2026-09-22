# Third-party Libraries
from fastapi import Response

# Local Libraries
from src.config import settings


class CookieManager:
    """
    Manage HTTP operations and use standard cookies to ensure application security
    """
    def __init__(self, key: str = 'refresh_token'):
        self.key = key
        self.httponly = True
        self.samesite = 'lax'
        self.secure = settings.PROJECT.ENVIRONMENT != 'development'

    def set_token(self, response: Response, token_value: str, expire_days: int = settings.JWT.REFRESH_EXPIRE):
        response.set_cookie(
            key=self.key,
            value=token_value,
            httponly=self.httponly,
            max_age=expire_days * 24 * 60 * 60,
            samesite=self.samesite,
            secure=self.secure
        )

    def delete_token(self, response: Response):
        response.delete_cookie(
            key=self.key,
            httponly=self.httponly,
            samesite=self.samesite,
            secure=self.secure
        )


# Instantiate the cookie
refresh_token_cookie = CookieManager(key="refresh_token")
