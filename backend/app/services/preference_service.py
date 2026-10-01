from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import Category, Product, ProductVariant
from app.models.preference import UserPreference, UserPreferredCategory, UserPreferredColor
from app.models.shop import Shop
from app.models.user import User
from app.schemas.preference import (
    PreferenceCategoryOption,
    PreferenceOptionsResponse,
    PreferenceResponse,
    PreferenceUpdate,
)


def _preference_query(buyer_id: int):
    return (
        select(UserPreference)
        .options(
            selectinload(UserPreference.categories),
            selectinload(UserPreference.colors),
        )
        .where(UserPreference.buyer_id == buyer_id)
    )


def _response(preference: UserPreference | None) -> PreferenceResponse:
    if preference is None:
        return PreferenceResponse(category_ids=[], colors=[], min_price=None, max_price=None)
    return PreferenceResponse(
        category_ids=sorted(item.category_id for item in preference.categories),
        colors=sorted((item.color for item in preference.colors), key=str.casefold),
        min_price=int(preference.min_price) if preference.min_price is not None else None,
        max_price=int(preference.max_price) if preference.max_price is not None else None,
    )


def get_preferences(db: Session, buyer_id: int) -> PreferenceResponse:
    return _response(db.scalar(_preference_query(buyer_id)))


def _active_colors(db: Session) -> set[str]:
    return set(
        db.scalars(
            select(ProductVariant.color)
            .join(Product, ProductVariant.product_id == Product.id)
            .join(Shop, Product.shop_id == Shop.id)
            .where(
                ProductVariant.is_active.is_(True),
                Product.is_active.is_(True),
                Shop.is_active.is_(True),
            )
            .distinct()
        )
    )


def list_options(db: Session, buyer_id: int) -> PreferenceOptionsResponse:
    categories = list(db.scalars(select(Category).order_by(Category.id)))
    preference = db.scalar(_preference_query(buyer_id))
    saved_colors = {item.color for item in preference.colors} if preference is not None else set()
    return PreferenceOptionsResponse(
        categories=[PreferenceCategoryOption(id=item.id, name=item.name) for item in categories],
        colors=sorted(_active_colors(db) | saved_colors, key=str.casefold),
    )


def update_preferences(
    db: Session,
    buyer_id: int,
    request: PreferenceUpdate,
) -> PreferenceResponse:
    db.execute(select(User.id).where(User.id == buyer_id).with_for_update()).scalar_one()

    known_category_ids = set(
        db.scalars(select(Category.id).where(Category.id.in_(request.category_ids)))
    )
    if known_category_ids != set(request.category_ids):
        raise HTTPException(status_code=400, detail="Danh mục không tồn tại")

    existing = db.scalar(_preference_query(buyer_id))
    saved_colors = {item.color for item in existing.colors} if existing is not None else set()
    if not set(request.colors).issubset(_active_colors(db) | saved_colors):
        raise HTTPException(status_code=400, detail="Màu sắc không tồn tại")

    try:
        preference = existing
        if preference is None:
            preference = UserPreference(buyer_id=buyer_id)
            db.add(preference)
            db.flush()
        preference.min_price = request.min_price
        preference.max_price = request.max_price
        db.execute(
            delete(UserPreferredCategory).where(
                UserPreferredCategory.preference_id == preference.id
            )
        )
        db.execute(
            delete(UserPreferredColor).where(UserPreferredColor.preference_id == preference.id)
        )
        db.add_all(
            UserPreferredCategory(preference_id=preference.id, category_id=category_id)
            for category_id in request.category_ids
        )
        db.add_all(
            UserPreferredColor(preference_id=preference.id, color=color) for color in request.colors
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_preferences(db, buyer_id)
