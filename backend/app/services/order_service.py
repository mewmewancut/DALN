from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.models.inventory import Inventory
from app.models.order import Order, OrderItem, OrderStatusHistory
from app.models.shop import Shop
from app.models.user import User
from app.schemas.orders import (
    OrderDetailResponse,
    OrderItemResponse,
    OrderPage,
    OrderStatusHistoryResponse,
    OrderSummaryResponse,
)

ALLOWED_TRANSITIONS = {
    "PENDING": frozenset({"CONFIRMED", "CANCELLED"}),
    "CONFIRMED": frozenset({"PREPARING", "CANCELLED"}),
    "PREPARING": frozenset({"SHIPPING"}),
    "SHIPPING": frozenset({"DELIVERED"}),
    "DELIVERED": frozenset(),
    "CANCELLED": frozenset(),
}


def _summary(order: Order) -> OrderSummaryResponse:
    return OrderSummaryResponse(
        id=order.id,
        code=order.code,
        buyer_id=order.buyer_id,
        shop_id=order.shop_id,
        status=order.status,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        total_amount=int(order.total_amount),
        created_at=order.created_at,
    )


def _detail(order: Order) -> OrderDetailResponse:
    return OrderDetailResponse(
        id=order.id,
        code=order.code,
        buyer_id=order.buyer_id,
        shop_id=order.shop_id,
        status=order.status,
        receiver_name=order.receiver_name,
        receiver_phone=order.receiver_phone,
        shipping_address=order.shipping_address,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        total_amount=int(order.total_amount),
        created_at=order.created_at,
        updated_at=order.updated_at,
        delivered_at=order.delivered_at,
        cancelled_at=order.cancelled_at,
        cancel_reason=order.cancel_reason,
        items=[
            OrderItemResponse(
                id=item.id,
                variant_id=item.variant_id,
                product_name=item.product_name,
                size=item.size,
                color=item.color,
                unit_price=int(item.unit_price),
                quantity=item.quantity,
            )
            for item in order.items
        ],
        status_history=[
            OrderStatusHistoryResponse(
                id=entry.id,
                from_status=entry.from_status,
                to_status=entry.to_status,
                changed_by=entry.changed_by,
                note=entry.note,
                created_at=entry.created_at,
            )
            for entry in sorted(order.status_history, key=lambda history: history.id)
        ],
    )


def _order_with_details(db: Session, order_id: int) -> Order | None:
    return db.scalar(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.status_history))
        .where(Order.id == order_id)
        .execution_options(populate_existing=True)
    )


def _list_orders(
    db: Session,
    *,
    owner_filter,
    status: str | None,
    page: int,
    page_size: int,
) -> OrderPage:
    filters = [owner_filter]
    if status is not None:
        filters.append(Order.status == status)
    total = db.scalar(select(func.count()).select_from(Order).where(*filters)) or 0
    orders = list(
        db.scalars(
            select(Order)
            .where(*filters)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return OrderPage(
        items=[_summary(order) for order in orders],
        total=total,
        page=page,
        page_size=page_size,
    )


def list_buyer_orders(
    db: Session,
    buyer_id: int,
    *,
    status: str | None,
    page: int,
    page_size: int,
) -> OrderPage:
    return _list_orders(
        db,
        owner_filter=Order.buyer_id == buyer_id,
        status=status,
        page=page,
        page_size=page_size,
    )


def list_shop_orders(
    db: Session,
    shop_id: int,
    *,
    status: str | None,
    page: int,
    page_size: int,
) -> OrderPage:
    return _list_orders(
        db,
        owner_filter=Order.shop_id == shop_id,
        status=status,
        page=page,
        page_size=page_size,
    )


def get_order_detail(db: Session, order_id: int, actor: User) -> OrderDetailResponse:
    order = _order_with_details(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Đơn hàng không tồn tại")
    if actor.role == "BUYER" and order.buyer_id != actor.id:
        raise HTTPException(status_code=403, detail="Đơn hàng không thuộc tài khoản của bạn")
    if actor.role == "SHOP_OWNER":
        shop_id = db.scalar(select(Shop.id).where(Shop.owner_id == actor.id))
        if shop_id is None or order.shop_id != shop_id:
            raise HTTPException(status_code=403, detail="Đơn hàng không thuộc shop của bạn")
    if actor.role not in {"BUYER", "SHOP_OWNER", "ADMIN"}:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    return _detail(order)


def transition_order(
    db: Session,
    order_id: int,
    new_status: str,
    actor: User,
    *,
    shop_id: int | None = None,
    note: str | None = None,
) -> OrderDetailResponse:
    try:
        order = db.scalar(
            select(Order)
            .where(Order.id == order_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if order is None:
            raise HTTPException(status_code=404, detail="Đơn hàng không tồn tại")

        old_status = order.status
        if actor.role == "BUYER":
            if order.buyer_id != actor.id:
                raise HTTPException(
                    status_code=403, detail="Đơn hàng không thuộc tài khoản của bạn"
                )
            if new_status != "CANCELLED" or old_status != "PENDING":
                raise HTTPException(
                    status_code=400,
                    detail="Buyer chỉ được hủy đơn đang ở trạng thái PENDING",
                )
        elif actor.role == "SHOP_OWNER":
            if shop_id is None or order.shop_id != shop_id:
                raise HTTPException(status_code=403, detail="Đơn hàng không thuộc shop của bạn")
            if new_status == "CANCELLED" and old_status not in {"PENDING", "CONFIRMED"}:
                raise HTTPException(
                    status_code=400,
                    detail="Shop chỉ được hủy đơn PENDING hoặc CONFIRMED",
                )
        else:
            raise HTTPException(status_code=403, detail="Không có quyền đổi trạng thái đơn hàng")

        if new_status not in ALLOWED_TRANSITIONS[old_status]:
            raise HTTPException(
                status_code=400,
                detail=f"Không thể chuyển {old_status} → {new_status}",
            )

        now = datetime.now(timezone.utc)
        if new_status == "CANCELLED":
            order_items = list(db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)))
            for item in order_items:
                result = db.execute(
                    update(Inventory)
                    .where(Inventory.variant_id == item.variant_id)
                    .values(quantity=Inventory.quantity + item.quantity)
                )
                if result.rowcount != 1:
                    raise HTTPException(status_code=409, detail="Không thể hoàn kho cho đơn hàng")
            order.cancelled_at = now
            order.cancel_reason = note
        elif new_status == "DELIVERED":
            order.delivered_at = now
            if order.payment_method == "COD":
                order.payment_status = "PAID"

        order.status = new_status
        db.add(
            OrderStatusHistory(
                order_id=order.id,
                from_status=old_status,
                to_status=new_status,
                changed_by=actor.id,
                note=note,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    completed = _order_with_details(db, order_id)
    if completed is None:
        raise RuntimeError("Đơn hàng vừa cập nhật không còn tồn tại")
    return _detail(completed)
