from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.shop import Shop
from app.models.user import User
from app.schemas.admin import AdminShopPage, AdminShopResponse, AdminUserPage, AdminUserResponse
from app.schemas.orders import OrderPage
from app.services import order_service


def _user_response(user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def list_users(
    db: Session,
    *,
    role: str | None,
    keyword: str | None,
    page: int,
    page_size: int,
) -> AdminUserPage:
    filters = []
    if role is not None:
        filters.append(User.role == role)
    if keyword:
        filters.append(User.email.ilike(f"%{keyword}%") | User.full_name.ilike(f"%{keyword}%"))
    total = db.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    users = list(
        db.scalars(
            select(User)
            .where(*filters)
            .order_by(User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return AdminUserPage(
        items=[_user_response(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
    )


def update_user_status(
    db: Session, actor: User, user_id: int, is_active: bool
) -> AdminUserResponse:
    if user_id == actor.id and not is_active:
        raise HTTPException(status_code=400, detail="Không thể tự khóa chính mình")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return _user_response(user)


def _shop_response(shop: Shop) -> AdminShopResponse:
    return AdminShopResponse(
        id=shop.id,
        owner_id=shop.owner_id,
        name=shop.name,
        description=shop.description,
        is_active=shop.is_active,
        created_at=shop.created_at,
    )


def list_shops(
    db: Session,
    *,
    keyword: str | None,
    is_active: bool | None,
    page: int,
    page_size: int,
) -> AdminShopPage:
    filters = []
    if keyword and (normalized_keyword := keyword.strip()):
        filters.append(Shop.name.ilike(f"%{normalized_keyword}%"))
    if is_active is not None:
        filters.append(Shop.is_active == is_active)
    total = db.scalar(select(func.count()).select_from(Shop).where(*filters)) or 0
    shops = list(
        db.scalars(
            select(Shop)
            .where(*filters)
            .order_by(Shop.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return AdminShopPage(
        items=[_shop_response(shop) for shop in shops],
        total=total,
        page=page,
        page_size=page_size,
    )


def update_shop_status(db: Session, shop_id: int, is_active: bool) -> AdminShopResponse:
    shop = db.get(Shop, shop_id)
    if shop is None:
        raise HTTPException(status_code=404, detail="Shop không tồn tại")
    shop.is_active = is_active
    db.commit()
    db.refresh(shop)
    return _shop_response(shop)


def list_orders(
    db: Session,
    *,
    shop_id: int | None,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
) -> OrderPage:
    return order_service.list_all_orders(
        db,
        shop_id=shop_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
