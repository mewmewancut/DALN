from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.supplier import Supplier
from app.schemas.supplier import SupplierCreate, SupplierResponse, SupplierUpdate


def _response(supplier: Supplier) -> SupplierResponse:
    return SupplierResponse(
        id=supplier.id,
        name=supplier.name,
        phone=supplier.phone,
        address=supplier.address,
        is_active=supplier.is_active,
    )


def list_suppliers(db: Session, shop_id: int) -> list[SupplierResponse]:
    suppliers = list(
        db.scalars(select(Supplier).where(Supplier.shop_id == shop_id).order_by(Supplier.id))
    )
    return [_response(supplier) for supplier in suppliers]


def get_owned_supplier_or_403(
    db: Session,
    supplier_id: int,
    shop_id: int,
    *,
    require_active: bool = False,
) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Nhà cung cấp không tồn tại")
    if supplier.shop_id != shop_id:
        raise HTTPException(status_code=403, detail="Nhà cung cấp không thuộc shop của bạn")
    if require_active and not supplier.is_active:
        raise HTTPException(status_code=400, detail="Nhà cung cấp đã ngừng hoạt động")
    return supplier


def create_supplier(db: Session, shop_id: int, request: SupplierCreate) -> SupplierResponse:
    supplier = Supplier(shop_id=shop_id, **request.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return _response(supplier)


def update_supplier(
    db: Session, shop_id: int, supplier_id: int, request: SupplierUpdate
) -> SupplierResponse:
    supplier = get_owned_supplier_or_403(db, supplier_id, shop_id)
    changes = request.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise HTTPException(status_code=400, detail="Tên nhà cung cấp không được để trống")
    for field, value in changes.items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return _response(supplier)


def remove_supplier(db: Session, shop_id: int, supplier_id: int) -> None:
    supplier = get_owned_supplier_or_403(db, supplier_id, shop_id)
    supplier.is_active = False
    db.commit()
