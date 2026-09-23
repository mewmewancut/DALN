from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base
from app.deps import get_db
from app.main import app
from app.models import (
    Cart,
    CartItem,
    Category,
    Inventory,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductVariant,
    Shop,
    User,
)
from app.schemas.orders import CheckoutRequest
from app.services.checkout_service import checkout
from app.tests.test_catalog import user_with_token

CHECKOUT_BODY = {
    "receiver_name": "Người nhận",
    "receiver_phone": "0900000000",
    "shipping_address": "123 Đường ABC",
    "payment_method": "COD",
}


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def seed_cart(db_session: Session, *, stock: int = 5) -> dict:
    buyer, headers = user_with_token(db_session, "checkout-buyer@example.com", "BUYER")
    owner, owner_headers = user_with_token(db_session, "checkout-owner@example.com", "SHOP_OWNER")
    shop = Shop(owner_id=owner.id, name="Shop Checkout")
    category = Category(name="Checkout category")
    db_session.add_all([shop, category])
    db_session.flush()
    product = Product(
        shop_id=shop.id,
        category_id=category.id,
        name="Áo checkout",
        image_url="https://example.com/shirt.jpg",
        base_price=100000,
    )
    db_session.add(product)
    db_session.flush()
    variant = ProductVariant(
        product_id=product.id,
        size="M",
        color="Đen",
        price=150000,
        sku=f"checkout-{uuid4().hex[:8]}",
    )
    db_session.add(variant)
    db_session.flush()
    db_session.add(Inventory(variant_id=variant.id, shop_id=shop.id, quantity=stock))
    cart = Cart(buyer_id=buyer.id, shop_id=shop.id)
    db_session.add(cart)
    db_session.flush()
    db_session.add(CartItem(cart_id=cart.id, variant_id=variant.id, quantity=2))
    db_session.commit()
    return {
        "buyer": buyer,
        "headers": headers,
        "owner_headers": owner_headers,
        "shop": shop,
        "product": product,
        "variant": variant,
        "cart": cart,
    }


def test_checkout_empty_cart_returns_400(db_session: Session, client: TestClient) -> None:
    _, headers = user_with_token(db_session, "empty-cart@example.com", "BUYER")
    db_session.commit()
    response = client.post("/orders/checkout", json=CHECKOUT_BODY, headers=headers)
    assert response.status_code == 400


def test_checkout_success_deducts_stock_clears_cart_and_records_history(
    db_session: Session, client: TestClient
) -> None:
    ctx = seed_cart(db_session, stock=5)
    response = client.post("/orders/checkout", json=CHECKOUT_BODY, headers=ctx["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["payment_status"] == "UNPAID"
    assert body["total_amount"] == 150000 * 2
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 2
    assert body["items"][0]["review_id"] is None

    assert (
        db_session.scalar(
            select(Inventory.quantity).where(Inventory.variant_id == ctx["variant"].id)
        )
        == 3
    )
    remaining_items = db_session.scalar(
        select(func.count()).select_from(CartItem).where(CartItem.cart_id == ctx["cart"].id)
    )
    assert remaining_items == 0
    assert db_session.scalar(select(Cart.shop_id).where(Cart.id == ctx["cart"].id)) is None
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == body["id"])
        )
        == 1
    )


def test_checkout_insufficient_stock_rolls_back_everything(
    db_session: Session, client: TestClient
) -> None:
    ctx = seed_cart(db_session, stock=1)
    response = client.post("/orders/checkout", json=CHECKOUT_BODY, headers=ctx["headers"])
    assert response.status_code == 409
    assert "không đủ hàng" in response.json()["detail"]

    assert (
        db_session.scalar(
            select(Inventory.quantity).where(Inventory.variant_id == ctx["variant"].id)
        )
        == 1
    )
    assert db_session.scalar(select(func.count()).select_from(Order)) == 0
    assert db_session.scalar(select(func.count()).select_from(OrderItem)) == 0
    assert (
        db_session.scalar(select(CartItem.quantity).where(CartItem.cart_id == ctx["cart"].id)) == 2
    )


def test_checkout_keeps_price_snapshot_after_shop_changes_price(
    db_session: Session, client: TestClient
) -> None:
    ctx = seed_cart(db_session, stock=5)
    response = client.post("/orders/checkout", json=CHECKOUT_BODY, headers=ctx["headers"])
    assert response.status_code == 200
    original_unit_price = response.json()["items"][0]["unit_price"]

    ctx["variant"].price = 999999
    db_session.commit()

    order_item_price = db_session.scalar(
        select(OrderItem.unit_price).where(OrderItem.order_id == response.json()["id"])
    )
    assert int(order_item_price) == original_unit_price != 999999


def test_checkout_ignores_client_supplied_total_amount(
    db_session: Session, client: TestClient
) -> None:
    ctx = seed_cart(db_session, stock=5)
    assert (
        client.post(
            "/orders/checkout",
            json={**CHECKOUT_BODY, "shop_id": ctx["shop"].id},
            headers=ctx["headers"],
        ).status_code
        == 422
    )
    tampered = {**CHECKOUT_BODY, "total_amount": 1}
    response = client.post("/orders/checkout", json=tampered, headers=ctx["headers"])
    assert response.status_code == 200
    assert response.json()["total_amount"] == int(ctx["variant"].price) * 2


def test_checkout_mock_card_is_paid_and_requires_buyer_role(
    db_session: Session, client: TestClient
) -> None:
    ctx = seed_cart(db_session, stock=5)
    assert client.post("/orders/checkout", json=CHECKOUT_BODY).status_code == 401
    assert (
        client.post(
            "/orders/checkout", json=CHECKOUT_BODY, headers=ctx["owner_headers"]
        ).status_code
        == 403
    )
    response = client.post(
        "/orders/checkout",
        json={**CHECKOUT_BODY, "payment_method": "MOCK_CARD"},
        headers=ctx["headers"],
    )
    assert response.status_code == 200
    assert response.json()["payment_status"] == "PAID"
    assert db_session.get(Order, response.json()["id"]).payment_status == "PAID"


def test_checkout_computes_total_from_database_prices(
    db_session: Session, client: TestClient
) -> None:
    ctx = seed_cart(db_session, stock=5)
    response = client.post("/orders/checkout", json=CHECKOUT_BODY, headers=ctx["headers"])
    assert response.status_code == 200
    assert response.json()["total_amount"] == int(ctx["variant"].price) * 2


@pytest.mark.parametrize("target", ["variant", "product", "shop"])
def test_checkout_rejects_catalog_item_hidden_after_it_was_added(
    target: str, db_session: Session, client: TestClient
) -> None:
    ctx = seed_cart(db_session, stock=5)
    entity = {
        "variant": ctx["variant"],
        "product": ctx["product"],
        "shop": ctx["shop"],
    }[target]
    entity.is_active = False
    db_session.commit()

    response = client.post("/orders/checkout", json=CHECKOUT_BODY, headers=ctx["headers"])

    assert response.status_code == 409
    assert "không còn bán" in response.json()["detail"]
    assert db_session.scalar(select(func.count()).select_from(Order)) == 0
    assert (
        db_session.scalar(
            select(Inventory.quantity).where(Inventory.variant_id == ctx["variant"].id)
        )
        == 5
    )
    assert (
        db_session.scalar(select(CartItem.quantity).where(CartItem.cart_id == ctx["cart"].id)) == 2
    )


def test_concurrent_checkout_on_shared_stock_allows_only_one_winner() -> None:
    # Separate schema so both threads can commit real, independent transactions
    # against the same rows without leaking state into other tests.
    schema = f"checkout_test_{uuid4().hex}"
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
            owner, _ = user_with_token(setup, "concurrent-owner@example.com", "SHOP_OWNER")
            buyer_a, _ = user_with_token(setup, "concurrent-buyer-a@example.com", "BUYER")
            buyer_b, _ = user_with_token(setup, "concurrent-buyer-b@example.com", "BUYER")
            shop = Shop(owner_id=owner.id, name="Concurrent Shop")
            category = Category(name="Concurrent category")
            setup.add_all([shop, category])
            setup.flush()
            product = Product(
                shop_id=shop.id,
                category_id=category.id,
                name="Áo concurrent",
                base_price=100000,
            )
            setup.add(product)
            setup.flush()
            variant = ProductVariant(
                product_id=product.id,
                size="M",
                color="Đen",
                price=150000,
                sku=f"concurrent-{uuid4().hex[:8]}",
            )
            setup.add(variant)
            setup.flush()
            setup.add(Inventory(variant_id=variant.id, shop_id=shop.id, quantity=1))
            cart_a = Cart(buyer_id=buyer_a.id, shop_id=shop.id)
            cart_b = Cart(buyer_id=buyer_b.id, shop_id=shop.id)
            setup.add_all([cart_a, cart_b])
            setup.flush()
            setup.add(CartItem(cart_id=cart_a.id, variant_id=variant.id, quantity=1))
            setup.add(CartItem(cart_id=cart_b.id, variant_id=variant.id, quantity=1))
            setup.commit()
            buyer_ids = [buyer_a.id, buyer_b.id]
            variant_id = variant.id

        barrier = Barrier(2)
        request = CheckoutRequest(**CHECKOUT_BODY)

        def checkout_concurrently(buyer_id: int):
            with Session(engine) as db:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                buyer = db.get(User, buyer_id)
                barrier.wait(timeout=10)
                try:
                    checkout(db, buyer, request)
                    return 200
                except HTTPException as error:
                    return error.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(checkout_concurrently, buyer_ids))

        assert sorted(results) == [200, 409]
        with Session(engine) as db:
            assert (
                db.scalar(select(Inventory.quantity).where(Inventory.variant_id == variant_id)) == 0
            )
            assert db.scalar(select(func.count()).select_from(Order)) == 1
    finally:
        if engine is not None:
            engine.dispose()
        with control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        control.dispose()


def test_concurrent_checkout_on_same_cart_creates_only_one_order() -> None:
    schema = f"same_cart_checkout_test_{uuid4().hex}"
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
            owner, _ = user_with_token(setup, "same-cart-owner@example.com", "SHOP_OWNER")
            buyer, _ = user_with_token(setup, "same-cart-buyer@example.com", "BUYER")
            shop = Shop(owner_id=owner.id, name="Same Cart Shop")
            category = Category(name="Same cart category")
            setup.add_all([shop, category])
            setup.flush()
            product = Product(
                shop_id=shop.id,
                category_id=category.id,
                name="Áo same cart",
                base_price=100000,
            )
            setup.add(product)
            setup.flush()
            variant = ProductVariant(
                product_id=product.id,
                size="M",
                color="Đen",
                price=150000,
                sku=f"same-cart-{uuid4().hex[:8]}",
            )
            setup.add(variant)
            setup.flush()
            setup.add(Inventory(variant_id=variant.id, shop_id=shop.id, quantity=2))
            cart = Cart(buyer_id=buyer.id, shop_id=shop.id)
            setup.add(cart)
            setup.flush()
            setup.add(CartItem(cart_id=cart.id, variant_id=variant.id, quantity=1))
            setup.commit()
            buyer_id = buyer.id
            variant_id = variant.id

        barrier = Barrier(2)
        request = CheckoutRequest(**CHECKOUT_BODY)

        def checkout_same_cart():
            with Session(engine) as db:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                buyer = db.get(User, buyer_id)
                barrier.wait(timeout=10)
                try:
                    checkout(db, buyer, request)
                    return 200
                except HTTPException as error:
                    return error.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: checkout_same_cart(), range(2)))

        assert sorted(results) == [200, 400]
        with Session(engine) as db:
            assert (
                db.scalar(select(Inventory.quantity).where(Inventory.variant_id == variant_id)) == 1
            )
            assert db.scalar(select(func.count()).select_from(Order)) == 1
            assert db.scalar(select(func.count()).select_from(CartItem)) == 0
    finally:
        if engine is not None:
            engine.dispose()
        with control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        control.dispose()
