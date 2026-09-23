from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _validate_bcrypt_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Mật khẩu không được vượt quá 72 byte")
    return password


BcryptPassword = Annotated[
    str,
    Field(min_length=1),
    AfterValidator(_validate_bcrypt_password),
]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=255)
    password: BcryptPassword
    full_name: str = Field(min_length=1, max_length=255)
    role: str


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=255)
    password: BcryptPassword


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    is_active: bool


class LoginResponse(BaseModel):
    access_token: str
    role: str
    shop_id: int | None
