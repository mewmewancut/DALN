from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.cart import Cart, CartItem
from app.models.catalog import Product, ProductVariant
from app.models.inventory import Inventory
from app.models.order import Order, OrderItem, OrderStatusHistory
from app.models.user import User
from app.schemas.orders import CheckoutRequest, OrderItemResponse, OrderResponse


def _order_response(order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        code=order.code,
        shop_id=order.shop_id,
        status=order.status,
        receiver_name=order.receiver_name,
        receiver_phone=order.receiver_phone,
        shipping_address=order.shipping_address,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        total_amount=int(order.total_amount),
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
    )


def checkout(db: Session, buyer: User, request: CheckoutRequest) -> OrderResponse:
    try:
        # Serialize every cart mutation for this buyer. Without these locks,
        # two requests can read the same cart before either one clears it and
        # create two orders when stock is sufficient for both.
        db.execute(select(User.id).where(User.id == buyer.id).with_for_update()).one()
        cart = db.scalar(
            select(Cart)
            .where(Cart.buyer_id == buyer.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if cart is None or cart.shop_id is None:
            raise HTTPException(status_code=400, detail="Giỏ hàng đang trống")
        cart_items = list(
            db.scalars(select(CartItem).where(CartItem.cart_id == cart.id).order_by(CartItem.id))
        )
        if not cart_items:
            raise HTTPException(status_code=400, detail="Giỏ hàng đang trống")

        # Unique placeholder so two concurrent checkouts never contend on the
        # same `code` value before each order gets its own id-based code below.
        order = Order(
            code=uuid4().hex[:20],
            buyer_id=buyer.id,
            shop_id=cart.shop_id,
            status="PENDING",
            shipping_address=request.shipping_address,
            receiver_name=request.receiver_name,
            receiver_phone=request.receiver_phone,
            payment_method=request.payment_method,
            payment_status="UNPAID",
            total_amount=0,
        )
        db.add(order)
        db.flush()
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        order.code = f"ORD-{today}-{order.id:04d}"

        total = Decimal(0)
        for cart_item in cart_items:
            # Giá + tên lấy HIỆN TẠI từ DB, không dùng dữ liệu cache trong giỏ.
            variant = db.scalar(
                select(ProductVariant)
                .join(Product)
                .where(ProductVariant.id == cart_item.variant_id)
                .execution_options(populate_existing=True)
            )
            if variant is None:
                raise HTTPException(status_code=409, detail="Sản phẩm không còn tồn tại")

            # Trừ kho bằng UPDATE có điều kiện — atomic, chống race condition.
            result = db.execute(
                update(Inventory)
                .where(
                    Inventory.variant_id == cart_item.variant_id,
                    Inventory.quantity >= cart_item.quantity,
                )
                .values(quantity=Inventory.quantity - cart_item.quantity)
            )
            if result.rowcount == 0:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Sản phẩm {variant.product.name} ({variant.size}/{variant.color}) "
                        "không đủ hàng"
                    ),
                )

            db.add(
                OrderItem(
                    order_id=order.id,
                    variant_id=variant.id,
                    product_name=variant.product.name,
                    size=variant.size,
                    color=variant.color,
                    unit_price=variant.price,
                    quantity=cart_item.quantity,
                )
            )
            total += variant.price * cart_item.quantity

        order.total_amount = total
        db.add(
            OrderStatusHistory(
                order_id=order.id,
                from_status=None,
                to_status="PENDING",
                changed_by=buyer.id,
            )
        )
        if request.payment_method == "MOCK_CARD":
            order.payment_status = "PAID"

        db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        cart.shop_id = None

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(order)
    return _order_response(order)
