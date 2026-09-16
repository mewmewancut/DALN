from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Category, Inventory, Product, ProductVariant, Shop, User


def make_user(email: str = "owner@example.com", role: str = "SHOP_OWNER") -> User:
    return User(
        email=email,
        password_hash="hashed-password",
        full_name="Test User",
        role=role,
    )


def create_catalog(db_session: Session) -> tuple[Shop, Product, ProductVariant]:
    owner = make_user()
    category = Category(name="Áo")
    shop = Shop(owner=owner, name="Test Shop")
    product = Product(
        shop=shop,
        category=category,
        name="Áo thun",
        base_price=Decimal("150000"),
    )
    variant = ProductVariant(
        product=product,
        size="M",
        color="Đen",
        price=Decimal("150000"),
        sku="P1-M-DEN",
    )
    db_session.add_all([owner, category, shop, product, variant])
    db_session.flush()
    return shop, product, variant


def test_user_role_constraint(db_session: Session) -> None:
    db_session.add(make_user(role="INVALID"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_user_email_is_unique(db_session: Session) -> None:
    db_session.add_all([make_user(), make_user()])

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_one_user_can_own_only_one_shop(db_session: Session) -> None:
    owner = make_user()
    db_session.add_all(
        [
            Shop(owner=owner, name="Shop One"),
            Shop(owner=owner, name="Shop Two"),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_category_name_is_unique(db_session: Session) -> None:
    db_session.add_all([Category(name="Giày"), Category(name="Giày")])

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_product_base_price_cannot_be_negative(db_session: Session) -> None:
    owner = make_user()
    category = Category(name="Quần")
    shop = Shop(owner=owner, name="Test Shop")
    db_session.add(
        Product(
            shop=shop,
            category=category,
            name="Quần jean",
            base_price=Decimal("-1"),
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_product_variant_combination_is_unique(db_session: Session) -> None:
    _, product, variant = create_catalog(db_session)
    db_session.add(
        ProductVariant(
            product=product,
            size=variant.size,
            color=variant.color,
            price=Decimal("160000"),
            sku="P1-M-DEN-SECOND",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_product_variant_sku_is_unique(db_session: Session) -> None:
    _, product, variant = create_catalog(db_session)
    db_session.add(
        ProductVariant(
            product=product,
            size="L",
            color="Trắng",
            price=Decimal("170000"),
            sku=variant.sku,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_inventory_quantity_cannot_be_negative(db_session: Session) -> None:
    shop, _, variant = create_catalog(db_session)
    db_session.add(Inventory(variant=variant, shop=shop, quantity=-1))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_database_defaults_are_applied(db_session: Session) -> None:
    shop, product, variant = create_catalog(db_session)
    inventory = Inventory(variant=variant, shop=shop)
    db_session.add(inventory)
    db_session.flush()

    assert shop.owner.is_active is True
    assert shop.is_active is True
    assert product.is_active is True
    assert variant.is_active is True
    assert inventory.quantity == 0
    assert inventory.low_stock_threshold == 5
    assert inventory.created_at.tzinfo is not None
    assert inventory.updated_at.tzinfo is not None


def test_variant_has_only_one_inventory_row(db_session: Session) -> None:
    shop, _, variant = create_catalog(db_session)
    db_session.add_all(
        [
            Inventory(variant=variant, shop=shop, quantity=5),
            Inventory(variant=variant, shop=shop, quantity=10),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()
