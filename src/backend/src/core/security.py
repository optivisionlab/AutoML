# Standard Libraries
from datetime import datetime, timedelta, timezone

# Third-party Libraries
from jwt import encode, decode, PyJWTError
from passlib.context import CryptContext

# Local Libraries
from src.config import settings


# Initialize the password hashing context
pwd_context = CryptContext(schemes=['argon2'], deprecated="auto")

class HashHelper:
    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(
            plain_password,
            hashed_password
        )

    @classmethod
    def get_password_hash(cls, password: str) -> str:
        return pwd_context.hash(password)


class JWTService:
    def __init__(self) -> None:
        self.__secret_key: str = settings.JWT.SECRET_KEY
        self.__algorithm: str = settings.JWT.ALGORITHM
        self.__access_exp: timedelta = timedelta(minutes=settings.JWT.ACCESS_EXPIRE)
        self.__refresh_exp: timedelta = timedelta(days=settings.JWT.REFRESH_EXPIRE)

        self.__verify_exp: timedelta = timedelta(minutes=5) # verification email expire
        self.__reset_exp: timedelta = timedelta(minutes=15) # password change deadline

    def create_access_token(self, data: dict) -> str:
        """
        Create access token
        """
        to_encode = data.copy()
        exp = datetime.now(timezone.utc) + self.__access_exp

        to_encode.update({
            'exp': exp,
            'type': 'access'
        })

        return encode(to_encode, self.__secret_key, self.__algorithm)
    
    def create_refresh_token(self, data: dict) -> str:
        """
        Create refresh token
        """
        to_encode = data.copy()
        exp = datetime.now(timezone.utc) + self.__refresh_exp
        to_encode.update({
            'exp': exp,
            'type': 'refresh'
        })

        return encode(to_encode, self.__secret_key, self.__algorithm)

    def create_verification_token(self, data: dict) -> str:
        """
        Create email verification token
        """
        to_encode = data.copy()
        exp = datetime.now(timezone.utc) + self.__verify_exp
        
        to_encode.update({
            'exp': exp,
            'type': 'verification'
        })

        return encode(to_encode, self.__secret_key, self.__algorithm)

    def verify_token(self, token: str) -> dict | None:
        """
        Verify token
        """
        try:
            payload = decode(token, self.__secret_key, algorithms=[self.__algorithm])

            return payload
        except PyJWTError:
            return None

    def create_reset_token(self, data: dict) -> str:
        """
        Create password reset token
        """
        to_encode = data.copy()
        exp = datetime.now(timezone.utc) + self.__reset_exp

        to_encode.update({
            'exp': exp,
            'type': 'reset'
        })

        return encode(to_encode, self.__secret_key, self.__algorithm)


# Instantiate the JWT object
jwt_service = JWTService()
