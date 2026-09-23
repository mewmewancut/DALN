from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AdminUserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class AdminUserPage(BaseModel):
    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int


class UserStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


class AdminShopResponse(BaseModel):
    id: int
    owner_id: int
    name: str
    description: str | None
    is_active: bool
    created_at: datetime


class AdminShopPage(BaseModel):
    items: list[AdminShopResponse]
    total: int
    page: int
    page_size: int


class ShopStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool
