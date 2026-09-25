import logging

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.catalog import Product, ProductVariant
from app.models.inventory import Inventory, LowStockAlert
from app.schemas.inventory import InventoryItemResponse, LowStockAlertResponse

logger = logging.getLogger(__name__)


def _locked_inventory(db: Session, variant_id: int) -> Inventory | None:
    return db.scalar(
        select(Inventory)
        .where(Inventory.variant_id == variant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _inventory_item(
    inventory: Inventory, variant: ProductVariant, product: Product
) -> InventoryItemResponse:
    return InventoryItemResponse(
        variant_id=variant.id,
        product_id=product.id,
        product_name=product.name,
        size=variant.size,
        color=variant.color,
        sku=variant.sku,
        quantity=inventory.quantity,
        low_stock_threshold=inventory.low_stock_threshold,
        is_low=inventory.quantity < inventory.low_stock_threshold,
    )


def list_shop_inventory(db: Session, shop_id: int) -> list[InventoryItemResponse]:
    rows = db.execute(
        select(Inventory, ProductVariant, Product)
        .join(ProductVariant, Inventory.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .where(Inventory.shop_id == shop_id)
        .order_by(Product.name, ProductVariant.size, ProductVariant.color)
    ).all()
    return [_inventory_item(inventory, variant, product) for inventory, variant, product in rows]


def _get_owned_inventory(db: Session, variant_id: int, shop_id: int) -> Inventory:
    inventory = db.scalar(select(Inventory).where(Inventory.variant_id == variant_id))
    if inventory is None:
        raise HTTPException(status_code=404, detail="Biến thể không tồn tại")
    if inventory.shop_id != shop_id:
        raise HTTPException(status_code=403, detail="Biến thể không thuộc shop của bạn")
    return inventory


def update_threshold(
    db: Session, shop_id: int, variant_id: int, threshold: int
) -> InventoryItemResponse:
    inventory = _get_owned_inventory(db, variant_id, shop_id)
    inventory.low_stock_threshold = threshold
    db.commit()
    db.refresh(inventory)

    # Đồng bộ cảnh báo khi Shop Owner thay đổi ngưỡng tồn kho.
    if inventory.quantity < inventory.low_stock_threshold:
        check_low_stock(db, variant_id)
    else:
        resolve_alerts_if_ok(db, variant_id)

    db.refresh(inventory)
    variant = db.get(ProductVariant, variant_id)
    product = db.get(Product, variant.product_id)
    return _inventory_item(inventory, variant, product)


def list_shop_alerts(db: Session, shop_id: int) -> list[LowStockAlertResponse]:
    rows = db.execute(
        select(LowStockAlert, ProductVariant, Product)
        .join(ProductVariant, LowStockAlert.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .where(LowStockAlert.shop_id == shop_id, LowStockAlert.is_resolved.is_(False))
        .order_by(LowStockAlert.created_at.desc())
    ).all()
    return [
        LowStockAlertResponse(
            id=alert.id,
            variant_id=variant.id,
            product_name=product.name,
            size=variant.size,
            color=variant.color,
            quantity_at_alert=alert.quantity_at_alert,
            is_resolved=alert.is_resolved,
            created_at=alert.created_at,
        )
        for alert, variant, product in rows
    ]


def check_low_stock(db: Session, variant_id: int) -> None:
    """Gọi SAU KHI đã trừ kho và commit (checkout). Không bao giờ raise để không làm
    fail đơn đã đặt thành công — mọi lỗi ở đây chỉ được log lại."""
    try:
        _check_low_stock(db, variant_id)
    except Exception:
        db.rollback()
        logger.exception("check_low_stock thất bại cho variant_id=%s", variant_id)


def _check_low_stock(db: Session, variant_id: int) -> None:
    inventory = _locked_inventory(db, variant_id)
    if inventory is None or inventory.quantity >= inventory.low_stock_threshold:
        return
    exists = db.scalar(
        select(LowStockAlert.id).where(
            LowStockAlert.variant_id == variant_id,
            LowStockAlert.is_resolved.is_(False),
        )
    )
    if exists is not None:
        return
    try:
        db.add(
            LowStockAlert(
                variant_id=variant_id,
                shop_id=inventory.shop_id,
                quantity_at_alert=inventory.quantity,
            )
        )
        db.commit()
    except IntegrityError:
        # ⚠️ Race: checkout khác đã tạo alert đang mở cho variant này trước khi
        # commit ở đây chạy tới — DB unique index chặn trùng, coi như đã có alert.
        db.rollback()


def resolve_alerts_if_ok(db: Session, variant_id: int) -> None:
    """Gọi SAU KHI đã cộng kho và commit (hủy đơn, nhận hàng). Không bao giờ raise
    để không làm fail thao tác cộng kho đã thành công — mọi lỗi ở đây chỉ được log lại."""
    try:
        _resolve_alerts_if_ok(db, variant_id)
    except Exception:
        db.rollback()
        logger.exception("resolve_alerts_if_ok thất bại cho variant_id=%s", variant_id)


def _resolve_alerts_if_ok(db: Session, variant_id: int) -> None:
    inventory = _locked_inventory(db, variant_id)
    if inventory is None or inventory.quantity < inventory.low_stock_threshold:
        return
    db.execute(
        update(LowStockAlert)
        .where(LowStockAlert.variant_id == variant_id, LowStockAlert.is_resolved.is_(False))
        .values(is_resolved=True)
    )
    db.commit()
