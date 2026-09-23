from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.models.user import User
from app.schemas.admin import (
    AdminShopPage,
    AdminShopResponse,
    AdminUserPage,
    AdminUserResponse,
    ShopStatusUpdate,
    UserStatusUpdate,
)
from app.schemas.orders import OrderPage, OrderStatus
from app.schemas.shop_stats import ShopStatsOverview
from app.services import admin_service, shop_stats_service

router = APIRouter(prefix="/admin", tags=["admin"])
Admin = Annotated[User, Depends(require_role("ADMIN"))]
Database = Annotated[Session, Depends(get_db)]


@router.get("/users", response_model=AdminUserPage)
def users(
    admin: Admin,
    db: Database,
    role: Literal["BUYER", "SHOP_OWNER", "ADMIN"] | None = None,
    keyword: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminUserPage:
    return admin_service.list_users(db, role=role, keyword=keyword, page=page, page_size=page_size)


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_user(
    user_id: int,
    request: UserStatusUpdate,
    admin: Admin,
    db: Database,
) -> AdminUserResponse:
    return admin_service.update_user_status(db, admin, user_id, request.is_active)


@router.get("/shops", response_model=AdminShopPage)
def shops(
    admin: Admin,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminShopPage:
    return admin_service.list_shops(db, page=page, page_size=page_size)


@router.patch("/shops/{shop_id}", response_model=AdminShopResponse)
def update_shop(
    shop_id: int,
    request: ShopStatusUpdate,
    admin: Admin,
    db: Database,
) -> AdminShopResponse:
    return admin_service.update_shop_status(db, shop_id, request.is_active)


@router.get("/orders", response_model=OrderPage)
def orders(
    admin: Admin,
    db: Database,
    shop_id: int | None = None,
    status: OrderStatus | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrderPage:
    return admin_service.list_orders(
        db,
        shop_id=shop_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.get("/stats/overview", response_model=ShopStatsOverview)
def stats_overview(
    admin: Admin,
    db: Database,
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
) -> ShopStatsOverview:
    return shop_stats_service.get_overview(db, from_date, to_date)
