from datetime import timedelta

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Category,
    Inventory,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductVariant,
    Shop,
    Supplier,
    User,
)
from app.seed import SEED_REFERENCE_TIME, seed_database


def count_rows(db_session: Session, model: type) -> int:
    return db_session.scalar(select(func.count()).select_from(model)) or 0


def test_seed_creates_complete_demo_data_and_is_idempotent(
    db_session: Session,
) -> None:
    first_run = seed_database(db_session)
    counts_after_first_run = {
        "users": count_rows(db_session, User),
        "shops": count_rows(db_session, Shop),
        "categories": count_rows(db_session, Category),
        "products": count_rows(db_session, Product),
        "variants": count_rows(db_session, ProductVariant),
        "inventory": count_rows(db_session, Inventory),
        "suppliers": count_rows(db_session, Supplier),
        "orders": count_rows(db_session, Order),
        "order_items": count_rows(db_session, OrderItem),
        "order_history": count_rows(db_session, OrderStatusHistory),
    }

    second_run = seed_database(db_session)
    counts_after_second_run = {
        "users": count_rows(db_session, User),
        "shops": count_rows(db_session, Shop),
        "categories": count_rows(db_session, Category),
        "products": count_rows(db_session, Product),
        "variants": count_rows(db_session, ProductVariant),
        "inventory": count_rows(db_session, Inventory),
        "suppliers": count_rows(db_session, Supplier),
        "orders": count_rows(db_session, Order),
        "order_items": count_rows(db_session, OrderItem),
        "order_history": count_rows(db_session, OrderStatusHistory),
    }

    assert first_run == {
        "users": 9,
        "shops": 3,
        "categories": 6,
        "products": 45,
        "variants": 135,
        "inventory": 135,
        "suppliers": 6,
        "orders": 36,
    }
    assert counts_after_first_run == {
        **first_run,
        "order_items": 72,
        "order_history": 124,
    }
    assert second_run == {name: 0 for name in first_run}
    assert counts_after_second_run == counts_after_first_run

    admin = db_session.scalar(select(User).where(User.email == "admin@shop.vn"))
    owner = db_session.scalar(select(User).where(User.email == "shop1@shop.vn"))
    buyer = db_session.scalar(select(User).where(User.email == "buyer1@shop.vn"))
    assert admin is not None
    assert owner is not None
    assert buyer is not None
    assert bcrypt.checkpw(b"Admin@123", admin.password_hash.encode())
    assert bcrypt.checkpw(b"Shop@123", owner.password_hash.encode())
    assert bcrypt.checkpw(b"Buyer@123", buyer.password_hash.encode())

    products_per_shop = db_session.execute(
        select(Product.shop_id, func.count(Product.id)).group_by(Product.shop_id)
    ).all()
    assert {count for _, count in products_per_shop} == {15}
    variants_per_product = db_session.execute(
        select(ProductVariant.product_id, func.count(ProductVariant.id)).group_by(
            ProductVariant.product_id
        )
    ).all()
    assert {count for _, count in variants_per_product} == {3}
    suppliers_per_shop = db_session.execute(
        select(Supplier.shop_id, func.count(Supplier.id)).group_by(Supplier.shop_id)
    ).all()
    assert {count for _, count in suppliers_per_shop} == {2}

    assert db_session.scalar(
        select(func.count()).select_from(Inventory).where(Inventory.quantity == 0)
    )
    assert db_session.scalar(
        select(func.count())
        .select_from(Inventory)
        .where(Inventory.quantity.between(1, 4))
    )
    assert db_session.scalar(select(func.max(Inventory.quantity))) <= 50
    assert (
        db_session.scalar(
            select(func.count()).select_from(Order).where(Order.status == "CANCELLED")
        )
        == 4
    )
    oldest_order = db_session.scalar(select(func.min(Order.created_at)))
    newest_order = db_session.scalar(select(func.max(Order.created_at)))
    assert oldest_order is not None
    assert newest_order is not None
    assert newest_order <= SEED_REFERENCE_TIME
    assert oldest_order >= SEED_REFERENCE_TIME - timedelta(days=30)
