import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cart import CartMerge
from app.models.catalog import Product, ProductVariant
from app.models.inventory import Inventory
from app.models.shop import Shop
from app.schemas.cart import CartItemResponse, CartMergeRequest, CartPreviewRequest, CartResponse
from app.services.cart_service import (
    add_to_cart,
    cart_response,
    cart_transaction,
    get_cart_response,
)


def preview_cart(db: Session, request: CartPreviewRequest) -> CartResponse:
    rows = {
        variant.id: (variant, product, shop, stock or 0)
        for variant, product, shop, stock in db.execute(
            select(ProductVariant, Product, Shop, Inventory.quantity)
            .select_from(ProductVariant)
            .join(Product, ProductVariant.product_id == Product.id)
            .join(Shop, Product.shop_id == Shop.id)
            .outerjoin(Inventory, Inventory.variant_id == ProductVariant.id)
            .where(ProductVariant.id.in_([item.variant_id for item in request.items]))
        )
    }
    items = []
    for item in request.items:
        row = rows.get(item.variant_id)
        available = bool(row and row[0].is_active and row[1].is_active and row[2].is_active)
        variant, product, shop, stock = row if row else (None, None, None, 0)
        items.append(
            CartItemResponse(
                id=item.variant_id,
                variant_id=item.variant_id,
                product_id=product.id if available else None,
                shop_id=shop.id if shop else None,
                shop_name=shop.name if shop and shop.is_active else "Shop không còn khả dụng",
                is_available=available,
                product_name=product.name if available else "Sản phẩm không còn khả dụng",
                image_url=product.image_url if available else None,
                size=variant.size if available else "",
                color=variant.color if available else "",
                quantity=item.quantity,
                unit_price=int(variant.price) if available else 0,
                stock_quantity=stock if available else 0,
            )
        )
    return cart_response(items)


def merge_cart(db: Session, buyer_id: int, request: CartMergeRequest) -> CartResponse:
    payload = sorted((item.variant_id, item.quantity) for item in request.items)
    payload_hash = hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()
    with cart_transaction(db, buyer_id, create=True) as cart:
        receipt = db.scalar(
            select(CartMerge).where(
                CartMerge.buyer_id == buyer_id,
                CartMerge.merge_id == str(request.merge_id),
            )
        )
        if receipt is not None:
            if receipt.payload_hash != payload_hash:
                raise HTTPException(
                    status_code=409, detail="Mã chuyển giỏ đã được dùng cho nội dung khác"
                )
        else:
            for item in request.items:
                try:
                    add_to_cart(db, cart, item.variant_id, item.quantity)
                except HTTPException as error:
                    raise HTTPException(
                        status_code=error.status_code,
                        detail=f"Chưa chuyển được giỏ tạm: {error.detail}. Giỏ tạm vẫn được giữ.",
                    ) from error
            db.add(
                CartMerge(
                    buyer_id=buyer_id, merge_id=str(request.merge_id), payload_hash=payload_hash
                )
            )
        result = get_cart_response(db, cart)
    return result
