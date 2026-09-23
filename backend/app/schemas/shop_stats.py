from datetime import date

from pydantic import BaseModel


class ShopStatsOverview(BaseModel):
    revenue: int
    order_count: int
    cancelled_count: int
    cancel_rate: float | None
    aov: float | None


class RevenueByDayItem(BaseModel):
    date: date
    revenue: int
    order_count: int


class TopProductItem(BaseModel):
    product_id: int
    product_name: str
    total_quantity_sold: int
    total_revenue: int
