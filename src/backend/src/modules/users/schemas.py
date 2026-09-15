# Third-party Libraries
from pydantic import BaseModel, Field, EmailStr


class UserResponse(BaseModel):
    id: str = Field(alias="_id")
    username: str
    email: EmailStr
    fullName: str | None = None
    role: str
    avatar: str | None = None
    is_verified: bool

    class Config:
        populate_by_name = True


class UserDetailResponse(UserResponse):
    gender: str | None = None
    date: str | None = None
    number: str | None= None
    created_at: float | None = None


class UpdateUserRequest(BaseModel):
    fullName: str | None = Field(None, max_length=100, description="Full name")
    gender: str | None = Field(None, pattern="^(male|female|other)$", description="Sex") 
    date: str | None = Field(None, description="Date of birth")
    number: str | None = Field(None, max_length=15, description="Phone number")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=6, description="New password (minimum 6 characters)")
