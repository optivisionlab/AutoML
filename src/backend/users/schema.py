# Third party libraries
from pydantic import BaseModel, EmailStr, Field, SecretStr
from users.utils.types import StrongPassword

class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3)
    email: str = Field(pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    gender: str
    date: str
    number: str = Field(..., min_length=10)
    fullName: str
    password: StrongPassword

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "username": "holmes",
                    "email": "user@example.com",
                    "gender": "male",
                    "date": "01/01/2026",
                    "number": "486909281",
                    "fullName": "Sherlock Holmes",
                    "password": "abc@123"
                }
            ]
        }
    }


class UserLoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str = Field(..., alias="_id")
    username: str
    email: str = Field(pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    gender: str
    date: str
    number: str = Field(..., min_length=10)
    fullName: str
    avatar: str | None = None
    role: str
    qrCode: str | None = None

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "4983204280djias",
                    "username": "xuandong",
                    "email": "user@example.com",
                    "gender": "male",
                    "date": "01/01/2026",
                    "number": "486909281",
                    "fullName": "Sherlock Holmes",
                    "avatar": "https://...",
                    "role": "user"
                }
            ]
        }
    }


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'


class RefreshRequest(BaseModel):
    refresh_token: str


class ResendEmailRequest(BaseModel):
    email: EmailStr


class VerifyEmailRequest(BaseModel):
    token: str
