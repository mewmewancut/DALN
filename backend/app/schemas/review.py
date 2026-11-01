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
    shop_reply: str | None = None
    shop_replied_at: datetime | None = None


class ReviewPage(BaseModel):
    items: list[ReviewResponse]
    total: int
    page: int
    page_size: int
    rating_average: float | None


class ShopReviewReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str = Field(min_length=1, max_length=2000)


class ShopReviewResponse(ReviewResponse):
    product_name: str
    shop_review_read_at: datetime | None = None


class ShopReviewPage(BaseModel):
    items: list[ShopReviewResponse]
    total: int
    unread_count: int
    page: int
    page_size: int
