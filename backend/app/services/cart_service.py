from collections.abc import Generator
from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.cart import Cart, CartItem
from app.models.catalog import Product, ProductVariant
from app.models.inventory import Inventory
from app.models.shop import Shop
from app.models.user import User
from app.schemas.cart import CartItemResponse, CartResponse


@contextmanager
def cart_transaction(db: Session, buyer_id: int, *, create: bool = False) -> Generator:
    try:
        # Serialize creation, edits, imports and checkout for the same buyer.
        db.execute(select(User.id).where(User.id == buyer_id).with_for_update()).one()
        cart = db.scalar(
            select(Cart)
            .where(Cart.buyer_id == buyer_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if cart is None and create:
            cart = Cart(buyer_id=buyer_id)
            db.add(cart)
            db.flush()
        yield cart
        db.commit()
    except Exception:
        db.rollback()
        raise


def cart_response(items: list[CartItemResponse]) -> CartResponse:
    shops = {(item.shop_id, item.shop_name) for item in items}
    shop_id, shop_name = next(iter(shops)) if len(shops) == 1 else (None, None)
    return CartResponse(
        shop_id=shop_id,
        shop_name=shop_name,
        items=items,
        total_amount=sum(item.quantity * item.unit_price for item in items),
    )


def get_cart_response(db: Session, cart: Cart | None) -> CartResponse:
    if cart is None:
        return cart_response([])
    db.flush()
    rows = db.execute(
        select(CartItem, ProductVariant, Product, Shop, Inventory.quantity)
        .join(ProductVariant, CartItem.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .join(Shop, Product.shop_id == Shop.id)
        .outerjoin(Inventory, Inventory.variant_id == ProductVariant.id)
        .where(CartItem.cart_id == cart.id)
        .order_by(CartItem.id)
        .execution_options(populate_existing=True)
    )
    return cart_response(
        [
            CartItemResponse(
                id=item.id,
                variant_id=variant.id,
                product_id=product.id,
                shop_id=shop.id,
                shop_name=shop.name,
                is_available=variant.is_active and product.is_active and shop.is_active,
                product_name=product.name,
                image_url=product.image_url,
                size=variant.size,
                color=variant.color,
                quantity=item.quantity,
                unit_price=int(variant.price),
                stock_quantity=quantity or 0,
            )
            for item, variant, product, shop, quantity in rows
        ]
    )


def get_cart(db: Session, buyer_id: int) -> CartResponse:
    cart = db.scalar(select(Cart).where(Cart.buyer_id == buyer_id))
    return get_cart_response(db, cart)


def available_variant(db: Session, variant_id: int) -> ProductVariant:
    variant = db.scalar(
        select(ProductVariant)
        .join(Product)
        .join(Shop)
        .where(
            ProductVariant.id == variant_id,
            ProductVariant.is_active.is_(True),
            Product.is_active.is_(True),
            Shop.is_active.is_(True),
        )
        .execution_options(populate_existing=True)
    )
    if variant is None:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại hoặc đã ngừng bán")
    return variant


def check_stock(db: Session, variant_id: int, quantity: int) -> None:
    stock = db.scalar(select(Inventory.quantity).where(Inventory.variant_id == variant_id)) or 0
    if quantity > stock:
        raise HTTPException(status_code=409, detail="Không đủ hàng")


def _owned_item(db: Session, item_id: int, buyer_id: int) -> CartItem:
    item = db.get(CartItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Sản phẩm trong giỏ không tồn tại")
    if item.cart.buyer_id != buyer_id:
        raise HTTPException(status_code=403, detail="Không có quyền sửa giỏ hàng này")
    return item


def add_to_cart(db: Session, cart: Cart, variant_id: int, quantity: int) -> None:
    available_variant(db, variant_id)
    item = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.variant_id == variant_id,
        )
    )
    new_quantity = (item.quantity if item else 0) + quantity
    check_stock(db, variant_id, new_quantity)
    if item is None:
        db.add(CartItem(cart_id=cart.id, variant_id=variant_id, quantity=new_quantity))
    else:
        item.quantity = new_quantity


def add_item(db: Session, buyer_id: int, variant_id: int, quantity: int) -> CartResponse:
    with cart_transaction(db, buyer_id, create=True) as cart:
        add_to_cart(db, cart, variant_id, quantity)
        result = get_cart_response(db, cart)
    return result


def update_item(db: Session, buyer_id: int, item_id: int, quantity: int) -> CartResponse:
    with cart_transaction(db, buyer_id) as cart:
        item = _owned_item(db, item_id, buyer_id)
        available_variant(db, item.variant_id)
        check_stock(db, item.variant_id, quantity)
        item.quantity = quantity
        result = get_cart_response(db, cart)
    return result


def remove_item(db: Session, buyer_id: int, item_id: int) -> CartResponse:
    with cart_transaction(db, buyer_id) as cart:
        db.delete(_owned_item(db, item_id, buyer_id))
        result = get_cart_response(db, cart)
    return result


def clear_cart(db: Session, buyer_id: int) -> CartResponse:
    with cart_transaction(db, buyer_id) as cart:
        if cart is not None:
            db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        result = get_cart_response(db, cart)
    return result
