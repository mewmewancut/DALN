from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def discard_client_total(cls, value):
        if isinstance(value, dict) and "total_amount" in value:
            value = {key: item for key, item in value.items() if key != "total_amount"}
        return value

    receiver_name: str = Field(min_length=1, max_length=255)
    receiver_phone: str = Field(min_length=1, max_length=20)
    shipping_address: str = Field(min_length=1)
    payment_method: Literal["COD", "MOCK_CARD"]


class OrderItemResponse(BaseModel):
    id: int
    variant_id: int
    product_name: str
    size: str
    color: str
    unit_price: int
    quantity: int
    review_id: int | None


class OrderResponse(BaseModel):
    id: int
    code: str
    shop_id: int
    status: str
    receiver_name: str
    receiver_phone: str
    shipping_address: str
    payment_method: str
    payment_status: str
    total_amount: int
    items: list[OrderItemResponse]


OrderStatus = Literal[
    "PENDING",
    "CONFIRMED",
    "PREPARING",
    "SHIPPING",
    "DELIVERED",
    "CANCELLED",
]


class OrderStatusChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OrderStatus
    note: str | None = Field(default=None, max_length=1000)


class OrderCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=1000)


class OrderStatusHistoryResponse(BaseModel):
    id: int
    from_status: str | None
    to_status: str
    changed_by: int
    note: str | None
    created_at: datetime


class OrderSummaryResponse(BaseModel):
    id: int
    code: str
    buyer_id: int
    shop_id: int
    status: str
    payment_method: str
    payment_status: str
    total_amount: int
    created_at: datetime


class OrderPage(BaseModel):
    items: list[OrderSummaryResponse]
    total: int
    page: int
    page_size: int


class OrderDetailResponse(OrderResponse):
    buyer_id: int
    created_at: datetime
    updated_at: datetime
    delivered_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    status_history: list[OrderStatusHistoryResponse]
