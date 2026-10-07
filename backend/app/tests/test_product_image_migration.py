import runpy
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from app.config import get_settings

VERSIONS = Path(__file__).resolve().parents[2] / "alembic" / "versions"


def product_columns(connection):
    return [
        {**column, "type": str(column["type"])}
        for column in inspect(connection).get_columns("products")
    ]


def test_image_migration_preserves_legacy_images_and_defaults():
    schema = f"image_migration_{uuid4().hex}"
    engine = create_engine(get_settings().test_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            with Operations.context(MigrationContext.configure(connection)):
                for path in sorted(VERSIONS.glob("*.py")):
                    migration = runpy.run_path(str(path))
                    if migration["revision"] == "20261007_0011":
                        break
                    migration["upgrade"]()
                owner = connection.scalar(
                    text(
                        "INSERT INTO users (email, password_hash, full_name, role) VALUES ('migration@example.com', 'unused-test', 'Test', 'SHOP_OWNER') RETURNING id"
                    )
                )
                shop = connection.scalar(
                    text("INSERT INTO shops (owner_id, name) VALUES (:owner, 'Test') RETURNING id"),
                    {"owner": owner},
                )
                category = connection.scalar(
                    text("INSERT INTO categories (name) VALUES ('Test') RETURNING id")
                )
                for url in (None, "https://example.com/legacy.jpg"):
                    connection.execute(
                        text(
                            "INSERT INTO products (shop_id, category_id, name, base_price, image_url) VALUES (:shop, :category, 'Test', 100, :url)"
                        ),
                        {"shop": shop, "category": category, "url": url},
                    )
                before = connection.execute(
                    text("SELECT id, image_url FROM products ORDER BY id")
                ).all()
                migration = runpy.run_path(str(VERSIONS / "20261007_0011_product_images.py"))
                columns_before = product_columns(connection)
                migration["upgrade"]()
                assert (
                    connection.execute(text("SELECT id, image_url FROM products ORDER BY id")).all()
                    == before
                )
                assert product_columns(connection) == columns_before
                assert connection.scalar(text("SELECT count(*) FROM product_detail_images")) == 0
                connection.execute(
                    text(
                        "INSERT INTO product_detail_images (product_id, position, image_url) VALUES (:id, 1, '/media/product-images/test.webp')"
                    ),
                    {"id": before[0].id},
                )
                assert connection.scalar(text("SELECT count(*) FROM product_detail_images")) == 1
                migration["downgrade"]()
                assert not inspect(connection).has_table("product_detail_images")
                assert (
                    connection.execute(text("SELECT id, image_url FROM products ORDER BY id")).all()
                    == before
                )
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()
