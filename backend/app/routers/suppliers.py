from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import get_current_shop, get_db
from app.models.shop import Shop
from app.schemas.supplier import SupplierCreate, SupplierResponse, SupplierUpdate
from app.services import supplier_service

router = APIRouter(prefix="/shop/suppliers", tags=["suppliers"])


@router.get("", response_model=list[SupplierResponse])
def suppliers(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SupplierResponse]:
    return supplier_service.list_suppliers(db, shop.id)


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(
    request: SupplierCreate,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
) -> SupplierResponse:
    return supplier_service.create_supplier(db, shop.id, request)


@router.put("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: int,
    request: SupplierUpdate,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
) -> SupplierResponse:
    return supplier_service.update_supplier(db, shop.id, supplier_id, request)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_supplier(
    supplier_id: int,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    supplier_service.remove_supplier(db, shop.id, supplier_id)
