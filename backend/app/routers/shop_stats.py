from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_current_shop, get_db
from app.models.shop import Shop
from app.schemas.shop_stats import RevenueByDayItem, ShopStatsOverview, TopProductItem
from app.services import shop_stats_service

router = APIRouter(prefix="/shop/stats", tags=["shop-stats"])
CurrentShop = Annotated[Shop, Depends(get_current_shop)]
Database = Annotated[Session, Depends(get_db)]


@router.get("/overview", response_model=ShopStatsOverview)
def overview(
    shop: CurrentShop,
    db: Database,
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
) -> ShopStatsOverview:
    return shop_stats_service.get_overview(db, from_date, to_date, shop_id=shop.id)


@router.get("/revenue-by-day", response_model=list[RevenueByDayItem])
def revenue_by_day(
    shop: CurrentShop,
    db: Database,
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
) -> list[RevenueByDayItem]:
    return shop_stats_service.get_revenue_by_day(db, shop.id, from_date, to_date)


@router.get("/top-products", response_model=list[TopProductItem])
def top_products(
    shop: CurrentShop,
    db: Database,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[TopProductItem]:
    return shop_stats_service.get_top_products(db, shop.id, limit)
