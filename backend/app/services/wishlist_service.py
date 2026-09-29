from fastapi import HTTPException
from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.catalog import Product, ProductVariant
from app.models.inventory import Inventory
from app.models.review import Review
from app.models.shop import Shop
from app.models.wishlist import WishlistItem
from app.schemas.wishlist import WishlistItemResponse


def _catalog_summaries():
    return (
        select(
            ProductVariant.product_id,
            func.min(ProductVariant.price)
            .filter(ProductVariant.is_active.is_(True))
            .label("price_from"),
            (
                func.sum(
                    case(
                        (
                            ProductVariant.is_active.is_(True) & (Inventory.quantity > 0),
                            1,
                        ),
                        else_=0,
                    )
                )
                > 0
            ).label("has_stock"),
        )
        .outerjoin(Inventory, Inventory.variant_id == ProductVariant.id)
        .group_by(ProductVariant.product_id)
        .subquery()
    )


def _ratings():
    return (
        select(Review.product_id, func.avg(Review.rating).label("rating_average"))
        .group_by(Review.product_id)
        .subquery()
    )


def _wishlist_query(buyer_id: int, product_id: int | None = None):
    catalog = _catalog_summaries()
    ratings = _ratings()
    query = (
        select(
            WishlistItem,
            Product,
            Shop,
            catalog.c.price_from,
            catalog.c.has_stock,
            ratings.c.rating_average,
        )
        .join(Product, WishlistItem.product_id == Product.id)
        .join(Shop, Product.shop_id == Shop.id)
        .outerjoin(catalog, Product.id == catalog.c.product_id)
        .outerjoin(ratings, Product.id == ratings.c.product_id)
        .where(WishlistItem.buyer_id == buyer_id)
    )
    if product_id is not None:
        query = query.where(WishlistItem.product_id == product_id)
    return query


def _response(row) -> WishlistItemResponse:
    item, product, shop, price_from, has_stock, rating_average = row
    return WishlistItemResponse(
        id=item.id,
        product_id=product.id,
        name=product.name,
        image_url=product.image_url,
        shop_name=shop.name,
        price_from=price_from,
        rating_average=float(rating_average) if rating_average is not None else None,
        is_available=product.is_active and shop.is_active,
        has_stock=bool(has_stock),
        created_at=item.created_at,
    )


def list_items(db: Session, buyer_id: int) -> list[WishlistItemResponse]:
    rows = db.execute(
        _wishlist_query(buyer_id).order_by(
            WishlistItem.created_at.desc(),
            WishlistItem.id.desc(),
        )
    ).all()
    return [_response(row) for row in rows]


def add_item(db: Session, buyer_id: int, product_id: int) -> WishlistItemResponse:
    existing = db.execute(_wishlist_query(buyer_id, product_id)).first()
    if existing is not None:
        return _response(existing)

    product_exists = db.scalar(
        select(Product.id)
        .join(Shop, Product.shop_id == Shop.id)
        .where(
            Product.id == product_id,
            Product.is_active.is_(True),
            Shop.is_active.is_(True),
        )
    )
    if product_exists is None:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")

    try:
        db.add(WishlistItem(buyer_id=buyer_id, product_id=product_id))
        db.commit()
    except IntegrityError:
        db.rollback()

    row = db.execute(_wishlist_query(buyer_id, product_id)).first()
    if row is None:
        raise RuntimeError("Không thể lưu sản phẩm yêu thích")
    return _response(row)


def remove_item(db: Session, buyer_id: int, product_id: int) -> None:
    db.execute(
        delete(WishlistItem).where(
            WishlistItem.buyer_id == buyer_id,
            WishlistItem.product_id == product_id,
        )
    )
    db.commit()
