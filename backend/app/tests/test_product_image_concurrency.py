from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base
from app.models import Category, Product, Shop, User
from app.schemas.catalog import ProductUpdate
from app.services.catalog_service import update_product


def test_concurrent_gallery_replacement_keeps_a_complete_set():
    schema = f"image_concurrency_{uuid4().hex}"
    control = create_engine(get_settings().test_database_url)
    engine = None
    try:
        with control.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(
            get_settings().test_database_url,
            connect_args={"options": f"-csearch_path={schema}", "connect_timeout": 10},
        )
        Base.metadata.create_all(engine)
        with Session(engine) as setup:
            owner = User(
                email="concurrent-images@example.com",
                password_hash="unused-test",
                full_name="Test",
                role="SHOP_OWNER",
            )
            shop = Shop(owner=owner, name="Test")
            product = Product(
                shop=shop,
                category=Category(name="Test"),
                name="Test",
                image_url="https://example.com/main.jpg",
                base_price=100,
            )
            setup.add(product)
            setup.commit()
            product_id, shop_id = product.id, shop.id
        barrier = Barrier(2)

        def replace(label):
            with Session(engine) as db:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                shop = db.get(Shop, shop_id)
                barrier.wait(timeout=10)
                update_product(
                    db,
                    shop,
                    product_id,
                    ProductUpdate(
                        image_url=f"https://example.com/{label}.jpg",
                        detail_image_urls=[
                            f"https://example.com/{label}-{i}.jpg" for i in range(10)
                        ],
                    ),
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(replace, ["a", "b"]))
        with Session(engine) as db:
            product = db.get(Product, product_id)
            label = "a" if product.image_url.endswith("/a.jpg") else "b"
            assert product.detail_image_urls == [
                f"https://example.com/{label}-{i}.jpg" for i in range(10)
            ]
        # Another request can already have cached the product before taking the lock.
        with Session(engine) as stale:
            cached_product = stale.get(Product, product_id)
            original_main = cached_product.image_url
            with Session(engine) as fresh:
                update_product(
                    fresh,
                    fresh.get(Shop, shop_id),
                    product_id,
                    ProductUpdate(
                        image_url="https://example.com/intermediate.jpg", detail_image_urls=[]
                    ),
                )
            update_product(
                stale,
                stale.get(Shop, shop_id),
                product_id,
                ProductUpdate(
                    image_url=original_main, detail_image_urls=["https://example.com/restored.jpg"]
                ),
            )
        with Session(engine) as db:
            product = db.get(Product, product_id)
            assert product.image_url == original_main
            assert product.detail_image_urls == ["https://example.com/restored.jpg"]
    finally:
        if engine is not None:
            engine.dispose()
        with control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        control.dispose()
