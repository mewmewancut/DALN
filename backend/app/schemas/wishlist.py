from datetime import datetime

from pydantic import BaseModel


class WishlistItemResponse(BaseModel):
    id: int
    product_id: int
    name: str
    image_url: str | None
    shop_name: str
    price_from: int | None
    rating_average: float | None
    is_available: bool
    has_stock: bool
    created_at: datetime
