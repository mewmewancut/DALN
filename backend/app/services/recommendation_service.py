from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.models.catalog import Product, ProductVariant
from app.models.inventory import Inventory
from app.models.review import Review
from app.models.shop import Shop
from app.schemas.catalog import ProductSummary
from app.services.preference_service import get_preferences


def list_recommendations(db: Session, buyer_id: int, *, limit: int) -> list[ProductSummary]:
    preferences = get_preferences(db, buyer_id)
    in_stock = Inventory.quantity > 0
    price_conditions = [in_stock]
    if preferences.min_price is not None:
        price_conditions.append(ProductVariant.price >= preferences.min_price)
    if preferences.max_price is not None:
        price_conditions.append(ProductVariant.price <= preferences.max_price)
    has_price_preference = preferences.min_price is not None or preferences.max_price is not None
    variants = (
        select(
            ProductVariant.product_id,
            func.min(ProductVariant.price).label("price_from"),
            func.max(case((in_stock, 1), else_=0)).label("has_stock"),
            func.max(
                case((and_(in_stock, ProductVariant.color.in_(preferences.colors)), 1), else_=0)
            ).label("color_score"),
            func.max(case((and_(has_price_preference, *price_conditions), 1), else_=0)).label(
                "price_score"
            ),
        )
        .outerjoin(Inventory, Inventory.variant_id == ProductVariant.id)
        .where(ProductVariant.is_active.is_(True))
        .group_by(ProductVariant.product_id)
        .subquery()
    )
    ratings = (
        select(Review.product_id, func.avg(Review.rating).label("rating_average"))
        .group_by(Review.product_id)
        .subquery()
    )
    score = (
        case((Product.category_id.in_(preferences.category_ids), 1), else_=0)
        + variants.c.color_score
        + variants.c.price_score
    )
    rows = db.execute(
        select(Product, Shop.name, variants.c.price_from, ratings.c.rating_average)
        .join(Shop, Product.shop_id == Shop.id)
        .join(variants, Product.id == variants.c.product_id)
        .outerjoin(ratings, Product.id == ratings.c.product_id)
        .where(
            Product.is_active.is_(True),
            Shop.is_active.is_(True),
            variants.c.has_stock == 1,
        )
        .order_by(score.desc(), Product.created_at.desc(), Product.id.desc())
        .limit(limit)
    ).all()
    return [
        ProductSummary(
            id=product.id,
            shop_id=product.shop_id,
            shop_name=shop_name,
            category_id=product.category_id,
            name=product.name,
            image_url=product.image_url,
            base_price=product.base_price,
            price_from=price_from,
            rating_average=float(rating) if rating is not None else None,
        )
        for product, shop_name, price_from, rating in rows
    ]
