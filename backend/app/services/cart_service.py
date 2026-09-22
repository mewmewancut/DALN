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


class DifferentShopError(HTTPException):
    def __init__(self, shop: Shop):
        super().__init__(status_code=409, detail="CART_DIFFERENT_SHOP")
        self.current_shop = {"id": shop.id, "name": shop.name}


@contextmanager
def _cart_transaction(db: Session, buyer_id: int, *, create: bool = False) -> Generator:
    try:
        # The buyer exists even before their first cart: serialize first creation
        # and all writes for this buyer so concurrent adds cannot mix shops.
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


def _response(db: Session, cart: Cart | None) -> CartResponse:
    if cart is None:
        return CartResponse(shop_id=None, shop_name=None, items=[], total_amount=0)
    db.flush()
    rows = db.execute(
        select(CartItem, ProductVariant, Product, Inventory.quantity)
        .join(ProductVariant, CartItem.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .outerjoin(Inventory, Inventory.variant_id == ProductVariant.id)
        .where(CartItem.cart_id == cart.id)
        .order_by(CartItem.id)
        .execution_options(populate_existing=True)
    )
    items = [
        CartItemResponse(
            id=item.id,
            variant_id=variant.id,
            product_id=product.id,
            product_name=product.name,
            image_url=product.image_url,
            size=variant.size,
            color=variant.color,
            quantity=item.quantity,
            unit_price=int(variant.price),
            stock_quantity=quantity or 0,
        )
        for item, variant, product, quantity in rows
    ]
    shop_name = (
        db.scalar(select(Shop.name).where(Shop.id == cart.shop_id)) if cart.shop_id else None
    )
    return CartResponse(
        shop_id=cart.shop_id,
        shop_name=shop_name,
        items=items,
        total_amount=sum(item.quantity * item.unit_price for item in items),
    )


def get_cart(db: Session, buyer_id: int) -> CartResponse:
    cart = db.scalar(select(Cart).where(Cart.buyer_id == buyer_id))
    return _response(db, cart)


def _available_variant(db: Session, variant_id: int) -> ProductVariant:
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


def _check_stock(db: Session, variant_id: int, quantity: int) -> None:
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


def add_item(db: Session, buyer_id: int, variant_id: int, quantity: int) -> CartResponse:
    with _cart_transaction(db, buyer_id, create=True) as cart:
        variant = _available_variant(db, variant_id)
        shop_id = variant.product.shop_id
        if cart.shop_id is not None and cart.shop_id != shop_id:
            raise DifferentShopError(db.get(Shop, cart.shop_id))
        item = db.scalar(
            select(CartItem).where(CartItem.cart_id == cart.id, CartItem.variant_id == variant_id)
        )
        new_quantity = (item.quantity if item else 0) + quantity
        _check_stock(db, variant_id, new_quantity)
        cart.shop_id = shop_id
        if item is None:
            db.add(CartItem(cart_id=cart.id, variant_id=variant_id, quantity=new_quantity))
        else:
            item.quantity = new_quantity
        result = _response(db, cart)
    return result


def update_item(db: Session, buyer_id: int, item_id: int, quantity: int) -> CartResponse:
    with _cart_transaction(db, buyer_id) as cart:
        item = _owned_item(db, item_id, buyer_id)
        _available_variant(db, item.variant_id)
        _check_stock(db, item.variant_id, quantity)
        item.quantity = quantity
        result = _response(db, cart)
    return result


def remove_item(db: Session, buyer_id: int, item_id: int) -> CartResponse:
    with _cart_transaction(db, buyer_id) as cart:
        item = _owned_item(db, item_id, buyer_id)
        db.delete(item)
        db.flush()
        if db.scalar(select(CartItem.id).where(CartItem.cart_id == cart.id).limit(1)) is None:
            cart.shop_id = None
        result = _response(db, cart)
    return result


def clear_cart(db: Session, buyer_id: int) -> CartResponse:
    with _cart_transaction(db, buyer_id) as cart:
        if cart is not None:
            db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
            cart.shop_id = None
        result = _response(db, cart)
    return result
