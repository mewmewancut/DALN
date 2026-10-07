from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import (
    Category,
    Inventory,
    LowStockAlert,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductVariant,
    Shop,
    Supplier,
    User,
)
from app.seed import seed_database

TEST_REFERENCE_TIME = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)


def count_rows(db_session: Session, model: type) -> int:
    return db_session.scalar(select(func.count()).select_from(model)) or 0


def test_seed_creates_complete_demo_data_and_is_idempotent(
    db_session: Session,
) -> None:
    first_run = seed_database(db_session, reference_time=TEST_REFERENCE_TIME)
    counts_after_first_run = {
        "users": count_rows(db_session, User),
        "shops": count_rows(db_session, Shop),
        "categories": count_rows(db_session, Category),
        "products": count_rows(db_session, Product),
        "variants": count_rows(db_session, ProductVariant),
        "inventory": count_rows(db_session, Inventory),
        "low_stock_alerts": count_rows(db_session, LowStockAlert),
        "suppliers": count_rows(db_session, Supplier),
        "orders": count_rows(db_session, Order),
        "order_items": count_rows(db_session, OrderItem),
        "order_history": count_rows(db_session, OrderStatusHistory),
    }

    second_run = seed_database(
        db_session,
        reference_time=TEST_REFERENCE_TIME + timedelta(days=7),
    )
    counts_after_second_run = {
        "users": count_rows(db_session, User),
        "shops": count_rows(db_session, Shop),
        "categories": count_rows(db_session, Category),
        "products": count_rows(db_session, Product),
        "variants": count_rows(db_session, ProductVariant),
        "inventory": count_rows(db_session, Inventory),
        "low_stock_alerts": count_rows(db_session, LowStockAlert),
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
        "low_stock_alerts": 19,
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

    low_inventory = db_session.scalars(
        select(Inventory).where(Inventory.quantity < Inventory.low_stock_threshold)
    ).all()
    alerts = db_session.scalars(select(LowStockAlert)).all()
    assert {(alert.variant_id, alert.shop_id, alert.quantity_at_alert) for alert in alerts} == {
        (item.variant_id, item.shop_id, item.quantity) for item in low_inventory
    }
    assert all(not alert.is_resolved for alert in alerts)

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
    variants = db_session.scalars(select(ProductVariant)).all()
    assert all(
        variant.sku == f"P{variant.product_id}-{variant.size}-{variant.color}"
        for variant in variants
    )
    suppliers_per_shop = db_session.execute(
        select(Supplier.shop_id, func.count(Supplier.id)).group_by(Supplier.shop_id)
    ).all()
    assert {count for _, count in suppliers_per_shop} == {2}

    assert db_session.scalar(
        select(func.count()).select_from(Inventory).where(Inventory.quantity == 0)
    )
    assert db_session.scalar(
        select(func.count()).select_from(Inventory).where(Inventory.quantity.between(1, 4))
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
    assert newest_order <= TEST_REFERENCE_TIME
    assert oldest_order >= TEST_REFERENCE_TIME - timedelta(days=30)


def test_seed_repairs_missing_alerts_without_resetting_stock_or_existing_alerts(
    db_session: Session,
) -> None:
    seed_database(db_session, reference_time=TEST_REFERENCE_TIME)
    db_session.execute(delete(LowStockAlert))
    items = db_session.scalars(select(Inventory).order_by(Inventory.id)).all()
    # Simulate a previously seeded database, including user edits and alert history.
    for item in items:
        item.quantity = 5
        item.low_stock_threshold = 5
    items[0].quantity = 0
    items[1].quantity = 2
    items[2].quantity = 0
    items[2].low_stock_threshold = 0
    history = LowStockAlert(
        variant_id=items[0].variant_id,
        shop_id=items[0].shop_id,
        quantity_at_alert=3,
        is_resolved=True,
    )
    existing = LowStockAlert(
        variant_id=items[1].variant_id,
        shop_id=items[1].shop_id,
        quantity_at_alert=4,
    )
    db_session.add_all([history, existing])
    db_session.flush()
    stock_before = [(item.id, item.quantity, item.low_stock_threshold) for item in items]

    repaired = seed_database(db_session, reference_time=TEST_REFERENCE_TIME)
    assert repaired["low_stock_alerts"] == 1
    assert sum(repaired.values()) == 1
    open_alerts = db_session.scalars(
        select(LowStockAlert).where(LowStockAlert.is_resolved.is_(False))
    ).all()
    assert {(alert.variant_id, alert.quantity_at_alert) for alert in open_alerts} == {
        (items[0].variant_id, 0),
        (items[1].variant_id, 4),
    }
    assert history.is_resolved is True
    assert existing in open_alerts
    assert count_rows(db_session, LowStockAlert) == 3
    db_session.expire_all()
    assert [(item.id, item.quantity, item.low_stock_threshold) for item in items] == stock_before
    assert not any(seed_database(db_session, reference_time=TEST_REFERENCE_TIME).values())
