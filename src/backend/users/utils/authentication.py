# Standard libraries
import os
from datetime import datetime, timedelta, timezone


# Third party libraries
from jwt import encode, decode, PyJWTError
from dotenv import load_dotenv


# Load .env file
load_dotenv()


class JWTService:
    def __init__(self) -> None:
        self.__secret_key: str = os.getenv('SECRET_KEY', '')
        self.__algorithm: str = os.getenv('ALGORITHM', 'HS256')
        self.__access_exp: timedelta = timedelta(minutes=int(os.getenv('ACCESS_EXPIRE', 1)))
        self.__refresh_exp: timedelta = timedelta(days=int(os.getenv('REFRESH_EXPIRE', 1)))

    def create_access_token(self, data: dict) -> str:
        """
        Create access token
        """
        to_encode = data.copy()
        exp = datetime.now(timezone.utc) + self.__access_exp

        to_encode.update({
            'exp': exp.timestamp(), 
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
            'exp': exp.timestamp(), 
            'type': 'refresh'
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
        

jwt_service = JWTService()