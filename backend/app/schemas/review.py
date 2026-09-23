from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_item_id: int
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewResponse(BaseModel):
    id: int
    order_item_id: int
    product_id: int
    buyer_id: int
    rating: int
    comment: str | None
    created_at: datetime


class ReviewPage(BaseModel):
    items: list[ReviewResponse]
    total: int
    page: int
    page_size: int
    rating_average: float | None
