from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.deps import get_current_shop, get_db
from app.models.shop import Shop
from app.schemas.purchase import (
    PurchaseOrderCreate,
    PurchaseOrderPage,
    PurchaseOrderResponse,
    PurchaseOrderStatus,
    PurchaseOrderStatusUpdate,
)
from app.services import purchase_service

router = APIRouter(prefix="/shop/purchase-orders", tags=["purchase-orders"])


@router.post("", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    request: PurchaseOrderCreate,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrderResponse:
    return purchase_service.create_purchase_order(db, shop.id, request)


@router.get("", response_model=PurchaseOrderPage)
def purchase_orders(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
    status: PurchaseOrderStatus | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PurchaseOrderPage:
    return purchase_service.list_purchase_orders(
        db, shop.id, status=status, page=page, page_size=page_size
    )


@router.patch("/{po_id}/status", response_model=PurchaseOrderResponse)
def change_purchase_order_status(
    po_id: int,
    request: PurchaseOrderStatusUpdate,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrderResponse:
    return purchase_service.transition_purchase_order(db, shop.id, po_id, request.status)
