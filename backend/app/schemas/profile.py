from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


def _strip_required(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Không được để trống")
    return value


RequiredText = Annotated[str, AfterValidator(_strip_required)]


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str | None
    avatar_url: str | None
    role: str
    is_active: bool
    email_verified_at: datetime | None


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: RequiredText | None = Field(default=None, max_length=255)
    phone: RequiredText | None = Field(default=None, max_length=20)
    avatar_url: AnyHttpUrl | None = None


class LocationResponse(BaseModel):
    code: str
    name: str


class AddressFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: RequiredText = Field(max_length=50)
    receiver_name: RequiredText = Field(max_length=255)
    receiver_phone: RequiredText = Field(max_length=20)
    province_code: str = Field(pattern=r"^\d{2}$")
    commune_code: str = Field(pattern=r"^\d{5}$")
    address_detail: RequiredText = Field(max_length=500)

    @field_validator("province_code", "commune_code", mode="before")
    @classmethod
    def strip_code(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AddressCreate(AddressFields):
    is_default: bool = False


class AddressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: RequiredText | None = Field(default=None, max_length=50)
    receiver_name: RequiredText | None = Field(default=None, max_length=255)
    receiver_phone: RequiredText | None = Field(default=None, max_length=20)
    province_code: str | None = Field(default=None, pattern=r"^\d{2}$")
    commune_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    address_detail: RequiredText | None = Field(default=None, max_length=500)

    @field_validator("province_code", "commune_code", mode="before")
    @classmethod
    def strip_code(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AddressResponse(AddressFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    province_name: str
    commune_name: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


class DeleteAddressResponse(BaseModel):
    message: str
