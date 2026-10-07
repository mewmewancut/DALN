import runpy
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Cart, CartItem
from app.tests.test_cart import create_catalog

VERSIONS = Path(__file__).resolve().parents[2] / "alembic" / "versions"


@pytest.fixture
def previous_schema():
    schema = f"cart_migration_{uuid4().hex}"
    engine = create_engine(get_settings().test_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            with Operations.context(MigrationContext.configure(connection)):
                for path in sorted(VERSIONS.glob("*.py")):
                    migration = runpy.run_path(str(path))
                    if migration["revision"] == "20261007_0010":
                        break
                    migration["upgrade"]()
            yield connection
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()


def migration(connection, direction):
    with Operations.context(MigrationContext.configure(connection)):
        runpy.run_path(str(VERSIONS / "20261007_0010_multi_shop_carts.py"))[direction]()


def seed_previous_cart(connection):
    with Session(connection, join_transaction_mode="create_savepoint") as db:
        buyer, _, _, _, shop, variants = create_catalog(db)
        cart = Cart(buyer_id=buyer.id)
        db.add(cart)
        db.flush()
        db.add(CartItem(cart_id=cart.id, variant_id=variants[0].id, quantity=2))
        db.execute(
            text("UPDATE carts SET shop_id=:shop WHERE id=:cart"),
            {"shop": shop.id, "cart": cart.id},
        )
        db.commit()
        return cart.id, shop.id, variants[0].id, variants[2].id


def test_cart_migration_preserves_items_and_rebuilds_single_shop_on_downgrade(previous_schema):
    cart_id, shop_id, variant_id, _ = seed_previous_cart(previous_schema)
    before = previous_schema.execute(
        text("SELECT id, cart_id, variant_id, quantity FROM cart_items")
    ).all()
    migration(previous_schema, "upgrade")
    assert "shop_id" not in {
        column["name"] for column in inspect(previous_schema).get_columns("carts")
    }
    assert inspect(previous_schema).has_table("cart_merges")
    assert (
        previous_schema.execute(
            text("SELECT id, cart_id, variant_id, quantity FROM cart_items")
        ).all()
        == before
    )
    with Session(previous_schema, join_transaction_mode="create_savepoint") as db:
        assert db.scalar(select(CartItem.quantity).where(CartItem.variant_id == variant_id)) == 2
    migration(previous_schema, "downgrade")
    assert (
        previous_schema.scalar(text("SELECT shop_id FROM carts WHERE id=:id"), {"id": cart_id})
        == shop_id
    )
    assert not inspect(previous_schema).has_table("cart_merges")


def test_cart_downgrade_rejects_mixed_shops_without_losing_items(previous_schema):
    cart_id, _, _, other_variant = seed_previous_cart(previous_schema)
    migration(previous_schema, "upgrade")
    previous_schema.execute(
        text("INSERT INTO cart_items (cart_id, variant_id, quantity) VALUES (:cart, :variant, 1)"),
        {"cart": cart_id, "variant": other_variant},
    )
    before = previous_schema.execute(
        text("SELECT id, variant_id, quantity FROM cart_items ORDER BY id")
    ).all()
    with pytest.raises(RuntimeError, match="Không thể downgrade"):
        migration(previous_schema, "downgrade")
    assert (
        previous_schema.execute(
            text("SELECT id, variant_id, quantity FROM cart_items ORDER BY id")
        ).all()
        == before
    )
    assert "shop_id" not in {
        column["name"] for column in inspect(previous_schema).get_columns("carts")
    }
    assert inspect(previous_schema).has_table("cart_merges")
