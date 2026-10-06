from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.shop_stats import RevenueByDayItem, ShopStatsOverview, TopProductItem


class StatusCount(BaseModel):
    status: str
    count: int


class DashboardProduct(TopProductItem):
    shop_name: str


class StockPriority(BaseModel):
    variant_id: int
    product_name: str
    shop_name: str
    size: str
    color: str
    quantity: int
    threshold: int
    sold_quantity: int


class StockSummary(BaseModel):
    tracked_variants: int
    out_of_stock: int
    low_stock: int
    priorities: list[StockPriority]


class ShopPerformance(ShopStatsOverview):
    shop_id: int
    shop_name: str


class DashboardResponse(BaseModel):
    from_date: date
    to_date: date
    previous_from: date
    previous_to: date
    generated_at: datetime
    overview: ShopStatsOverview
    previous: ShopStatsOverview
    revenue_daily: list[RevenueByDayItem]
    order_statuses: list[StatusCount]
    top_products: list[DashboardProduct]
    work_queue: list[StatusCount]
    stock: StockSummary
    shops: list[ShopPerformance]
