from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field


def _validate_bcrypt_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Mật khẩu không được vượt quá 72 byte")
    return password


BcryptPassword = Annotated[
    str,
    Field(min_length=8),
    AfterValidator(_validate_bcrypt_password),
]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=255)
    password: BcryptPassword
    full_name: str = Field(min_length=1, max_length=255)
    role: str


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=255)
    password: BcryptPassword


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    email_verified_at: datetime | None


class LoginResponse(BaseModel):
    access_token: str
    role: str
    shop_id: int | None


class TokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=32, max_length=255)


class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=255)


class ResetPasswordRequest(TokenRequest):
    new_password: BcryptPassword


class MessageResponse(BaseModel):
    message: str
