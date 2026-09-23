from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InventoryItemResponse(BaseModel):
    variant_id: int
    product_id: int
    product_name: str
    size: str
    color: str
    sku: str
    quantity: int
    low_stock_threshold: int
    is_low: bool


class ThresholdUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    low_stock_threshold: int = Field(ge=0)


class LowStockAlertResponse(BaseModel):
    id: int
    variant_id: int
    product_name: str
    size: str
    color: str
    quantity_at_alert: int
    is_resolved: bool
    created_at: datetime
