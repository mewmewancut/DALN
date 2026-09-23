from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_current_shop, get_current_user, get_db, require_role
from app.models.shop import Shop
from app.models.user import User
from app.schemas.orders import (
    CheckoutRequest,
    OrderCancelRequest,
    OrderDetailResponse,
    OrderPage,
    OrderResponse,
    OrderStatus,
    OrderStatusChangeRequest,
)
from app.services import checkout_service, order_service

router = APIRouter(prefix="/orders", tags=["orders"])
shop_router = APIRouter(prefix="/shop/orders", tags=["orders"])
Buyer = Annotated[User, Depends(require_role("BUYER"))]
Database = Annotated[Session, Depends(get_db)]


@router.post("/checkout", response_model=OrderResponse)
def checkout(request: CheckoutRequest, buyer: Buyer, db: Database):
    return checkout_service.checkout(db, buyer, request)


@router.get("/my", response_model=OrderPage)
def buyer_orders(
    buyer: Buyer,
    db: Database,
    status: OrderStatus | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrderPage:
    return order_service.list_buyer_orders(
        db,
        buyer.id,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.get("/{order_id}", response_model=OrderDetailResponse)
def order_detail(
    order_id: int,
    actor: Annotated[User, Depends(get_current_user)],
    db: Database,
) -> OrderDetailResponse:
    return order_service.get_order_detail(db, order_id, actor)


@router.patch("/{order_id}/status", response_model=OrderDetailResponse)
def change_status(
    order_id: int,
    request: OrderStatusChangeRequest,
    actor: Annotated[User, Depends(require_role("SHOP_OWNER"))],
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Database,
) -> OrderDetailResponse:
    return order_service.transition_order(
        db,
        order_id,
        request.status,
        actor,
        shop_id=shop.id,
        note=request.note,
    )


@router.post("/{order_id}/cancel", response_model=OrderDetailResponse)
def cancel_order(
    order_id: int,
    request: OrderCancelRequest,
    buyer: Buyer,
    db: Database,
) -> OrderDetailResponse:
    return order_service.transition_order(
        db,
        order_id,
        "CANCELLED",
        buyer,
        note=request.reason,
    )


@shop_router.get("", response_model=OrderPage)
def shop_orders(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Database,
    status: OrderStatus | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrderPage:
    return order_service.list_shop_orders(
        db,
        shop.id,
        status=status,
        page=page,
        page_size=page_size,
    )
