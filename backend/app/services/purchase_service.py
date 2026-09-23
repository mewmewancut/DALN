from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import ProductVariant
from app.models.inventory import Inventory
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.schemas.purchase import (
    PurchaseOrderCreate,
    PurchaseOrderItemResponse,
    PurchaseOrderPage,
    PurchaseOrderResponse,
)
from app.services import inventory_service
from app.services.supplier_service import get_owned_supplier_or_403

ALLOWED_TRANSITIONS = {
    "DRAFT": frozenset({"ORDERED", "CANCELLED"}),
    "ORDERED": frozenset({"RECEIVED", "CANCELLED"}),
    "RECEIVED": frozenset(),
    "CANCELLED": frozenset(),
}


def _response(purchase_order: PurchaseOrder) -> PurchaseOrderResponse:
    return PurchaseOrderResponse(
        id=purchase_order.id,
        shop_id=purchase_order.shop_id,
        supplier_id=purchase_order.supplier_id,
        status=purchase_order.status,
        note=purchase_order.note,
        received_at=purchase_order.received_at,
        created_at=purchase_order.created_at,
        items=[
            PurchaseOrderItemResponse(
                id=item.id,
                variant_id=item.variant_id,
                quantity=item.quantity,
                unit_cost=int(item.unit_cost),
            )
            for item in purchase_order.items
        ],
    )


def _with_items(db: Session, po_id: int) -> PurchaseOrder | None:
    return db.scalar(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(PurchaseOrder.id == po_id)
        .execution_options(populate_existing=True)
    )


def create_purchase_order(
    db: Session, shop_id: int, request: PurchaseOrderCreate
) -> PurchaseOrderResponse:
    supplier = get_owned_supplier_or_403(
        db,
        request.supplier_id,
        shop_id,
        require_active=True,
    )

    variant_ids = [item.variant_id for item in request.items]
    variants_by_id = {
        variant.id: variant
        for variant in db.scalars(select(ProductVariant).where(ProductVariant.id.in_(variant_ids)))
    }
    inventory_shop_by_variant = {
        inventory.variant_id: inventory.shop_id
        for inventory in db.scalars(select(Inventory).where(Inventory.variant_id.in_(variant_ids)))
    }
    for variant_id in variant_ids:
        if variant_id not in variants_by_id:
            raise HTTPException(status_code=404, detail="Biến thể không tồn tại")
        if inventory_shop_by_variant.get(variant_id) != shop_id:
            raise HTTPException(status_code=403, detail="Biến thể không thuộc shop của bạn")

    try:
        purchase_order = PurchaseOrder(shop_id=shop_id, supplier_id=supplier.id, note=request.note)
        db.add(purchase_order)
        db.flush()
        for item in request.items:
            db.add(
                PurchaseOrderItem(
                    purchase_order_id=purchase_order.id,
                    variant_id=item.variant_id,
                    quantity=item.quantity,
                    unit_cost=item.unit_cost,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    completed = _with_items(db, purchase_order.id)
    return _response(completed)


def list_purchase_orders(
    db: Session,
    shop_id: int,
    *,
    status: str | None,
    page: int,
    page_size: int,
) -> PurchaseOrderPage:
    filters = [PurchaseOrder.shop_id == shop_id]
    if status is not None:
        filters.append(PurchaseOrder.status == status)
    total = db.scalar(select(func.count()).select_from(PurchaseOrder).where(*filters)) or 0
    purchase_orders = list(
        db.scalars(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.items))
            .where(*filters)
            .order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return PurchaseOrderPage(
        items=[_response(purchase_order) for purchase_order in purchase_orders],
        total=total,
        page=page,
        page_size=page_size,
    )


def transition_purchase_order(
    db: Session, shop_id: int, po_id: int, new_status: str
) -> PurchaseOrderResponse:
    received_variant_ids: list[int] = []
    try:
        purchase_order = db.scalar(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == po_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if purchase_order is None:
            raise HTTPException(status_code=404, detail="Phiếu nhập không tồn tại")
        if purchase_order.shop_id != shop_id:
            raise HTTPException(status_code=403, detail="Phiếu nhập không thuộc shop của bạn")

        old_status = purchase_order.status
        if new_status not in ALLOWED_TRANSITIONS[old_status]:
            raise HTTPException(
                status_code=400,
                detail=f"Không thể chuyển {old_status} → {new_status}",
            )

        if new_status == "RECEIVED":
            items = list(
                db.scalars(
                    select(PurchaseOrderItem).where(
                        PurchaseOrderItem.purchase_order_id == purchase_order.id
                    )
                )
            )
            for item in items:
                # ⚠️ RECEIVED là trạng thái cuối và transition chỉ chạy một lần
                # từ ORDERED, nên không thể cộng kho 2 lần cho cùng phiếu nhập.
                result = db.execute(
                    update(Inventory)
                    .where(Inventory.variant_id == item.variant_id)
                    .values(quantity=Inventory.quantity + item.quantity)
                )
                if result.rowcount != 1:
                    raise HTTPException(status_code=409, detail="Không thể cộng kho cho phiếu nhập")
                received_variant_ids.append(item.variant_id)
            purchase_order.received_at = datetime.now(timezone.utc)

        purchase_order.status = new_status
        db.commit()
    except Exception:
        db.rollback()
        raise

    # Giải quyết cảnh báo SAU khi cộng kho và commit — cùng nguyên tắc C6.
    for variant_id in received_variant_ids:
        inventory_service.resolve_alerts_if_ok(db, variant_id)

    completed = _with_items(db, po_id)
    if completed is None:
        raise RuntimeError("Phiếu nhập vừa cập nhật không còn tồn tại")
    return _response(completed)
