from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_shop, get_db
from app.models.shop import Shop
from app.schemas.inventory import (
    InventoryItemResponse,
    LowStockAlertResponse,
    ThresholdUpdateRequest,
)
from app.services import inventory_service

router = APIRouter(prefix="/shop", tags=["inventory"])


@router.get("/inventory", response_model=list[InventoryItemResponse])
def shop_inventory(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
) -> list[InventoryItemResponse]:
    return inventory_service.list_shop_inventory(db, shop.id)


@router.put("/inventory/{variant_id}/threshold", response_model=InventoryItemResponse)
def update_inventory_threshold(
    variant_id: int,
    request: ThresholdUpdateRequest,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
) -> InventoryItemResponse:
    return inventory_service.update_threshold(db, shop.id, variant_id, request.low_stock_threshold)


@router.get("/alerts", response_model=list[LowStockAlertResponse])
def shop_alerts(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
) -> list[LowStockAlertResponse]:
    return inventory_service.list_shop_alerts(db, shop.id)
