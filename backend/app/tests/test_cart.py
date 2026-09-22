from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base
from app.deps import get_db
from app.main import app
from app.models import Cart, CartItem, Category, Inventory, Product, ProductVariant, Shop
from app.services.cart_service import DifferentShopError, add_item, get_cart
from app.tests.test_catalog import user_with_token


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def create_catalog(db_session):
    buyer, headers = user_with_token(db_session, "cart-buyer@example.com", "BUYER")
    _, other_headers = user_with_token(db_session, "cart-other@example.com", "BUYER")
    owner, owner_headers = user_with_token(db_session, "cart-owner@example.com", "SHOP_OWNER")
    owner_b, _ = user_with_token(db_session, "cart-owner-b@example.com", "SHOP_OWNER")
    shop = Shop(owner_id=owner.id, name="Shop A")
    shop_b = Shop(owner_id=owner_b.id, name="Shop B")
    category = Category(name="Cart category")
    db_session.add_all([shop, shop_b, category])
    db_session.flush()
    variants = []
    for index, current_shop in enumerate([shop, shop, shop_b]):
        product = Product(
            shop_id=current_shop.id,
            category_id=category.id,
            name=f"Áo {index}",
            image_url="https://example.com/shirt.jpg",
            base_price=100000,
        )
        db_session.add(product)
        db_session.flush()
        variant = ProductVariant(
            product_id=product.id,
            size="M",
            color="Đen",
            price=120000 + index * 10000,
            sku=f"cart-test-{index}",
        )
        db_session.add(variant)
        db_session.flush()
        db_session.add(Inventory(variant_id=variant.id, shop_id=current_shop.id, quantity=5))
        variants.append(variant)
    # Release the fixture savepoint so a failed request only rolls back its own
    # changes; the outer test transaction still isolates all fixture data.
    db_session.commit()
    return buyer, headers, other_headers, owner_headers, shop, variants


@pytest.fixture
def catalog(db_session):
    return create_catalog(db_session)


def add(client, headers, variant, quantity=1):
    return client.post(
        "/cart/items", headers=headers, json={"variant_id": variant.id, "quantity": quantity}
    )


def test_cart_empty_add_merge_and_current_prices(client, db_session, catalog):
    buyer, headers, _, _, shop, variants = catalog
    empty = client.get("/cart", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == {"shop_id": None, "shop_name": None, "items": [], "total_amount": 0}
    assert add(client, headers, variants[0], 2).status_code == 200
    merged = add(client, headers, variants[0], 1)
    assert merged.status_code == 200
    body = merged.json()
    assert body["shop_id"] == shop.id
    assert body["shop_name"] == shop.name
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["quantity"] == 3
    assert item["stock_quantity"] == 5
    assert item["unit_price"] == 120000
    assert item["product_name"] == "Áo 0"
    assert item["size"] == "M" and item["color"] == "Đen"
    assert item["image_url"] == "https://example.com/shirt.jpg"
    assert body["total_amount"] == 360000
    variants[0].price = 150000
    variants[0].inventory.quantity = 2
    db_session.flush()
    current = client.get("/cart", headers=headers).json()
    assert current["items"][0]["unit_price"] == 150000
    assert current["items"][0]["stock_quantity"] == 2
    assert current["items"][0]["quantity"] == 3  # Cart does not reserve stock.
    assert current["total_amount"] == 450000
    assert (
        db_session.scalar(select(func.count()).select_from(Cart).where(Cart.buyer_id == buyer.id))
        == 1
    )


def test_cart_different_shop_conflict_preserves_cart(client, catalog):
    _, headers, _, _, shop, variants = catalog
    before = add(client, headers, variants[0]).json()
    response = add(client, headers, variants[2])
    assert response.status_code == 409
    assert response.json() == {
        "detail": "CART_DIFFERENT_SHOP",
        "current_shop": {"id": shop.id, "name": shop.name},
    }
    assert client.get("/cart", headers=headers).json() == before


def test_cart_stock_checks_rollback_and_update(client, db_session, catalog):
    buyer, headers, _, _, _, variants = catalog
    assert add(client, headers, variants[0], 6).status_code == 409
    assert db_session.scalar(select(Cart).where(Cart.buyer_id == buyer.id)) is None
    before = add(client, headers, variants[0], 4).json()
    item_id = before["items"][0]["id"]
    assert add(client, headers, variants[0], 2).status_code == 409
    assert (
        client.put(f"/cart/items/{item_id}", headers=headers, json={"quantity": 6}).status_code
        == 409
    )
    assert client.get("/cart", headers=headers).json() == before
    updated = client.put(f"/cart/items/{item_id}", headers=headers, json={"quantity": 2})
    assert updated.status_code == 200
    assert updated.json()["items"][0]["quantity"] == 2
    assert updated.json()["total_amount"] == 240000
    assert db_session.get(Inventory, variants[0].inventory.id).quantity == 5


def test_cart_delete_last_item_and_clear_allow_other_shop(client, catalog):
    _, headers, _, _, shop, variants = catalog
    add(client, headers, variants[0])
    body = add(client, headers, variants[1]).json()
    response = client.delete(f"/cart/items/{body['items'][0]['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["shop_id"] == shop.id
    remaining = response.json()["items"][0]["id"]
    empty = client.delete(f"/cart/items/{remaining}", headers=headers)
    assert empty.json()["shop_id"] is None
    assert empty.json()["items"] == []
    assert add(client, headers, variants[2]).status_code == 200
    assert client.delete("/cart", headers=headers).json()["shop_id"] is None
    assert client.delete("/cart", headers=headers).json()["items"] == []
    assert add(client, headers, variants[0]).status_code == 200


@pytest.mark.parametrize("target", ["variant", "product", "shop"])
def test_cart_rejects_hidden_catalog_but_allows_removal(client, db_session, catalog, target):
    _, headers, _, _, shop, variants = catalog
    variant = variants[0]
    body = add(client, headers, variant).json()
    item_id = body["items"][0]["id"]
    entity = {"variant": variant, "product": variant.product, "shop": shop}[target]
    entity.is_active = False
    db_session.commit()
    assert add(client, headers, variant).status_code == 404
    assert (
        client.put(f"/cart/items/{item_id}", headers=headers, json={"quantity": 2}).status_code
        == 404
    )
    assert client.delete(f"/cart/items/{item_id}", headers=headers).status_code == 200


def test_cart_ownership_and_roles(client, catalog):
    _, headers, other_headers, owner_headers, _, variants = catalog
    item_id = add(client, headers, variants[0]).json()["items"][0]["id"]
    for method, url, body in [
        ("get", "/cart", None),
        ("post", "/cart/items", {"variant_id": variants[0].id, "quantity": 1}),
        ("put", f"/cart/items/{item_id}", {"quantity": 1}),
        ("delete", f"/cart/items/{item_id}", None),
        ("delete", "/cart", None),
    ]:
        assert client.request(method, url, json=body).status_code == 401
        assert client.request(method, url, headers=owner_headers, json=body).status_code == 403
    assert client.get("/cart", headers=other_headers).json()["items"] == []
    assert (
        client.put(
            f"/cart/items/{item_id}", headers=other_headers, json={"quantity": 1}
        ).status_code
        == 403
    )
    assert client.delete(f"/cart/items/{item_id}", headers=other_headers).status_code == 403
    assert client.delete("/cart", headers=other_headers).status_code == 200
    assert len(client.get("/cart", headers=headers).json()["items"]) == 1


@pytest.mark.parametrize("quantity", [0, -1, 1.5, 2147483648, True])
def test_cart_rejects_invalid_quantities(client, catalog, quantity):
    _, headers, _, _, _, variants = catalog
    assert add(client, headers, variants[0], quantity).status_code == 422
    item_id = add(client, headers, variants[0]).json()["items"][0]["id"]
    assert (
        client.put(
            f"/cart/items/{item_id}", headers=headers, json={"quantity": quantity}
        ).status_code
        == 422
    )


def test_cart_missing_resources_and_client_trusted_fields(client, catalog):
    _, headers, _, _, _, variants = catalog
    assert (
        client.post(
            "/cart/items", headers=headers, json={"variant_id": 999999999, "quantity": 1}
        ).status_code
        == 404
    )
    assert (
        client.put("/cart/items/999999999", headers=headers, json={"quantity": 1}).status_code
        == 404
    )
    assert client.delete("/cart/items/999999999", headers=headers).status_code == 404
    for extra in [{"shop_id": 1}, {"buyer_id": 1}, {"unit_price": 1}]:
        assert (
            client.post(
                "/cart/items",
                headers=headers,
                json={"variant_id": variants[0].id, "quantity": 1, **extra},
            ).status_code
            == 422
        )


def test_cart_rolls_back_on_database_failure(client, db_session, catalog, monkeypatch):
    _, headers, _, _, _, variants = catalog
    before = add(client, headers, variants[0]).json()

    def fail_commit():
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="simulated commit failure"):
        add(client, headers, variants[1])
    assert client.get("/cart", headers=headers).json() == before
    assert db_session.scalar(select(func.count()).select_from(CartItem)) == 1


@pytest.mark.parametrize("different_shop", [False, True])
def test_concurrent_first_add_preserves_cart_invariants(different_shop):
    # Separate schema in the test database permits real commits and two
    # independent connections without exposing data to other tests.
    schema = f"cart_test_{uuid4().hex}"
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
            buyer, _, _, _, _, variants = create_catalog(setup)
            buyer_id = buyer.id
            variant_ids = [variants[0].id, variants[2 if different_shop else 0].id]
        barrier = Barrier(2)

        def add_concurrently(variant_id):
            with Session(engine) as db:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                barrier.wait(timeout=10)
                try:
                    add_item(db, buyer_id, variant_id, 1)
                    return 200
                except DifferentShopError:
                    return 409

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(add_concurrently, variant_ids))
        assert sorted(results) == ([200, 409] if different_shop else [200, 200])
        with Session(engine) as db:
            cart = get_cart(db, buyer_id)
            assert len(cart.items) == 1
            assert cart.items[0].quantity == (1 if different_shop else 2)
            assert db.scalar(select(func.count()).select_from(Cart)) == 1
            assert db.scalar(select(func.count()).select_from(CartItem)) == 1
            assert all(quantity == 5 for quantity in db.scalars(select(Inventory.quantity)))
    finally:
        if engine is not None:
            engine.dispose()
        with control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        control.dispose()
