# Third-party Libraries
from pydantic import BaseModel, Field, EmailStr


class UserResponse(BaseModel):
    id: str = Field(..., alias="_id")
    username: str | None = None
    email: str = Field(pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    gender: str | None = None
    date: str | None = None
    number: str | None = Field(default=None, min_length=10)
    fullName: str | None = None
    avatar: str | None = None
    role: str

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "4983204280djias",
                    "username": "user123",
                    "email": "user@example.com",
                    "gender": "male",
                    "date": "01/01/2026",
                    "number": "486909281",
                    "fullName": "User Name",
                    "avatar": "https://...",
                    "role": "user"
                }
            ]
        }
    }


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3)
    email: str = Field(pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    gender: str
    date: str
    number: str = Field(..., min_length=10)
    fullName: str
    password: str

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


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'


class RefreshRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    token: str


class ResendEmailRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6, description="The new password must be at least 6 characters long")
    confirm_password: str
