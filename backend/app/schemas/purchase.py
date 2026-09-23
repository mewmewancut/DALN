from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PurchaseOrderStatus = Literal["DRAFT", "ORDERED", "RECEIVED", "CANCELLED"]


class PurchaseOrderItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_id: int
    quantity: int = Field(gt=0)
    unit_cost: int = Field(ge=0)


class PurchaseOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: int
    note: str | None = None
    items: list[PurchaseOrderItemCreate] = Field(min_length=1)

    @field_validator("items")
    @classmethod
    def unique_variants(cls, items: list[PurchaseOrderItemCreate]) -> list[PurchaseOrderItemCreate]:
        variant_ids = [item.variant_id for item in items]
        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError("Biến thể bị trùng trong phiếu nhập")
        return items


class PurchaseOrderStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PurchaseOrderStatus


class PurchaseOrderItemResponse(BaseModel):
    id: int
    variant_id: int
    quantity: int
    unit_cost: int


class PurchaseOrderResponse(BaseModel):
    id: int
    shop_id: int
    supplier_id: int
    status: str
    note: str | None
    received_at: datetime | None
    created_at: datetime
    items: list[PurchaseOrderItemResponse]


class PurchaseOrderPage(BaseModel):
    items: list[PurchaseOrderResponse]
    total: int
    page: int
    page_size: int
