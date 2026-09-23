from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.catalog import Category, Product, ProductVariant
from app.models.inventory import Inventory
from app.models.review import Review
from app.models.shop import Shop
from app.schemas.catalog import (
    ProductCreate,
    ProductDetail,
    ProductPage,
    ProductSummary,
    ProductUpdate,
    VariantCreate,
    VariantResponse,
    VariantUpdate,
)


def list_categories(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.id)))


def get_owned_product_or_403(db: Session, product_id: int, shop_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    if product.shop_id != shop_id:
        raise HTTPException(status_code=403, detail="Sản phẩm không thuộc shop của bạn")
    return product


def _require_category(db: Session, category_id: int) -> None:
    if db.get(Category, category_id) is None:
        raise HTTPException(status_code=404, detail="Danh mục không tồn tại")


def _sku_component(value: str) -> str:
    return value.replace("%", "%25").replace("-", "%2D")


def _sku(product_id: int, size: str, color: str) -> str:
    safe_size = _sku_component(size)
    safe_color = _sku_component(color)
    sku = f"P{product_id}-{safe_size}-{safe_color}"
    if len(sku) > 50:
        raise HTTPException(status_code=400, detail="SKU vượt quá 50 ký tự")
    return sku


def _add_variant(
    db: Session, product: Product, shop_id: int, request: VariantCreate
) -> ProductVariant:
    variant = ProductVariant(
        product_id=product.id,
        size=request.size,
        color=request.color,
        price=request.price,
        sku=_sku(product.id, request.size, request.color),
    )
    db.add(variant)
    db.flush()
    db.add(
        Inventory(
            variant_id=variant.id,
            shop_id=shop_id,
            quantity=request.initial_quantity,
        )
    )
    return variant


def create_product(db: Session, shop: Shop, request: ProductCreate) -> ProductDetail:
    _require_category(db, request.category_id)
    product = Product(
        shop_id=shop.id,
        **request.model_dump(exclude={"variants"}),
    )
    try:
        db.add(product)
        db.flush()
        for variant_request in request.variants:
            _add_variant(db, product, shop.id, variant_request)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Biến thể bị trùng") from None
    except Exception:
        db.rollback()
        raise
    return get_product_detail(db, product.id, public=False)


def update_product(
    db: Session, shop: Shop, product_id: int, request: ProductUpdate
) -> ProductDetail:
    product = get_owned_product_or_403(db, product_id, shop.id)
    changes = request.model_dump(exclude_unset=True)
    for required in ("category_id", "name", "base_price", "is_active"):
        if required in changes and changes[required] is None:
            raise HTTPException(status_code=400, detail=f"{required} không được để trống")
    if "category_id" in changes:
        _require_category(db, changes["category_id"])
    for field, value in changes.items():
        setattr(product, field, value)
    db.commit()
    return get_product_detail(db, product.id, public=False)


def remove_product(db: Session, shop: Shop, product_id: int) -> None:
    product = get_owned_product_or_403(db, product_id, shop.id)
    product.is_active = False
    db.commit()


def add_variant(
    db: Session, shop: Shop, product_id: int, request: VariantCreate
) -> VariantResponse:
    product = get_owned_product_or_403(db, product_id, shop.id)
    duplicate = db.scalar(
        select(ProductVariant.id).where(
            ProductVariant.product_id == product.id,
            ProductVariant.size == request.size,
            ProductVariant.color == request.color,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Biến thể bị trùng")
    try:
        variant = _add_variant(db, product, shop.id, request)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Biến thể bị trùng") from None
    except Exception:
        db.rollback()
        raise
    db.refresh(variant)
    return _variant_response(variant)


def update_variant(
    db: Session, shop: Shop, variant_id: int, request: VariantUpdate
) -> VariantResponse:
    variant = db.get(ProductVariant, variant_id)
    if variant is None:
        raise HTTPException(status_code=404, detail="Biến thể không tồn tại")
    get_owned_product_or_403(db, variant.product_id, shop.id)
    changes = request.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=400, detail="Giá và trạng thái không được để trống")
    for field, value in changes.items():
        setattr(variant, field, value)
    db.commit()
    db.refresh(variant)
    return _variant_response(variant)


def _variant_response(variant: ProductVariant) -> VariantResponse:
    return VariantResponse(
        id=variant.id,
        size=variant.size,
        color=variant.color,
        price=variant.price,
        sku=variant.sku,
        is_active=variant.is_active,
        quantity=variant.inventory.quantity,
    )


def _rating_average(db: Session, product_id: int) -> float | None:
    rating = db.scalar(select(func.avg(Review.rating)).where(Review.product_id == product_id))
    return float(rating) if rating is not None else None


def get_product_detail(db: Session, product_id: int, *, public: bool = True) -> ProductDetail:
    product = db.get(Product, product_id)
    if product is None or (public and (not product.is_active or not product.shop.is_active)):
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    variants = list(
        db.scalars(
            select(ProductVariant)
            .where(ProductVariant.product_id == product.id)
            .order_by(ProductVariant.id)
        )
    )
    visible_variants = [v for v in variants if not public or v.is_active]
    prices = [int(v.price) for v in variants if v.is_active]
    return ProductDetail(
        id=product.id,
        shop_id=product.shop_id,
        shop_name=product.shop.name,
        category_id=product.category_id,
        name=product.name,
        description=product.description,
        image_url=product.image_url,
        base_price=product.base_price,
        price_from=min(prices) if prices else None,
        rating_average=_rating_average(db, product.id),
        is_active=product.is_active,
        variants=[_variant_response(v) for v in visible_variants],
    )


def list_products(
    db: Session,
    *,
    keyword: str | None,
    category_id: int | None,
    shop_id: int | None,
    min_price: int | None,
    max_price: int | None,
    sort: str,
    page: int,
    page_size: int,
) -> ProductPage:
    prices = (
        select(
            ProductVariant.product_id,
            func.min(ProductVariant.price).label("price_from"),
        )
        .where(ProductVariant.is_active.is_(True))
        .group_by(ProductVariant.product_id)
        .subquery()
    )
    ratings = (
        select(Review.product_id, func.avg(Review.rating).label("rating_average"))
        .group_by(Review.product_id)
        .subquery()
    )
    filters = [Product.is_active.is_(True), Shop.is_active.is_(True)]
    if keyword:
        filters.append(Product.name.ilike(f"%{keyword}%"))
    if category_id is not None:
        filters.append(Product.category_id == category_id)
    if shop_id is not None:
        filters.append(Product.shop_id == shop_id)
    if min_price is not None:
        filters.append(prices.c.price_from >= min_price)
    if max_price is not None:
        filters.append(prices.c.price_from <= max_price)

    total = db.scalar(
        select(func.count())
        .select_from(Product)
        .join(Shop, Product.shop_id == Shop.id)
        .outerjoin(prices, Product.id == prices.c.product_id)
        .where(*filters)
    )
    query = (
        select(Product, Shop.name, prices.c.price_from, ratings.c.rating_average)
        .join(Shop, Product.shop_id == Shop.id)
        .outerjoin(prices, Product.id == prices.c.product_id)
        .outerjoin(ratings, Product.id == ratings.c.product_id)
        .where(*filters)
    )
    if sort == "price_asc":
        query = query.order_by(prices.c.price_from.asc().nulls_last(), Product.id.desc())
    elif sort == "price_desc":
        query = query.order_by(prices.c.price_from.desc().nulls_last(), Product.id.desc())
    else:
        query = query.order_by(Product.created_at.desc(), Product.id.desc())
    rows = db.execute(query.offset((page - 1) * page_size).limit(page_size)).all()
    return ProductPage(
        items=[
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
        ],
        total=total or 0,
        page=page,
        page_size=page_size,
    )
