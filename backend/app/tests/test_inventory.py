from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.main import app
from app.models import Category, Inventory, LowStockAlert, Product, ProductVariant, Shop
from app.models.cart import CartItem
from app.tests.test_catalog import user_with_token
from app.tests.test_checkout import CHECKOUT_BODY, seed_cart


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def seed_variant(
    db_session: Session, *, quantity: int, threshold: int = 5, owner_email: str | None = None
) -> dict:
    owner_email = owner_email or f"inventory-owner-{uuid4().hex[:8]}@example.com"
    owner, owner_headers = user_with_token(db_session, owner_email, "SHOP_OWNER")
    shop = Shop(owner_id=owner.id, name="Inventory Shop")
    category = Category(name=f"Inventory category {uuid4().hex[:8]}")
    db_session.add_all([shop, category])
    db_session.flush()
    product = Product(
        shop_id=shop.id,
        category_id=category.id,
        name="Áo tồn kho",
        base_price=100000,
    )
    db_session.add(product)
    db_session.flush()
    variant = ProductVariant(
        product_id=product.id,
        size="M",
        color="Đen",
        price=150000,
        sku=f"inventory-{uuid4().hex[:8]}",
    )
    db_session.add(variant)
    db_session.flush()
    db_session.add(
        Inventory(
            variant_id=variant.id,
            shop_id=shop.id,
            quantity=quantity,
            low_stock_threshold=threshold,
        )
    )
    db_session.commit()
    return {
        "owner_headers": owner_headers,
        "shop": shop,
        "product": product,
        "variant": variant,
    }


def test_shop_inventory_lists_own_variants_with_is_low_flag(
    db_session: Session, client: TestClient
) -> None:
    low = seed_variant(db_session, quantity=2, threshold=5)
    other = seed_variant(db_session, quantity=20, threshold=5)

    response = client.get("/shop/inventory", headers=low["owner_headers"])
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["variant_id"] == low["variant"].id
    assert items[0]["quantity"] == 2
    assert items[0]["is_low"] is True
    assert other["variant"].id not in [item["variant_id"] for item in items]

    assert client.get("/shop/inventory").status_code == 401
    _, buyer_headers = user_with_token(db_session, "inventory-buyer@example.com", "BUYER")
    db_session.commit()
    assert client.get("/shop/inventory", headers=buyer_headers).status_code == 403


def test_update_threshold_recomputes_is_low_and_checks_ownership(
    db_session: Session, client: TestClient
) -> None:
    ctx = seed_variant(db_session, quantity=10, threshold=5)
    other_owner, other_headers = user_with_token(
        db_session, "other-inventory-owner@example.com", "SHOP_OWNER"
    )
    db_session.add(Shop(owner_id=other_owner.id, name="Other Inventory Shop"))
    db_session.commit()

    response = client.put(
        f"/shop/inventory/{ctx['variant'].id}/threshold",
        json={"low_stock_threshold": 15},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["low_stock_threshold"] == 15
    assert body["is_low"] is True
    assert (
        db_session.scalar(
            select(Inventory.low_stock_threshold).where(Inventory.variant_id == ctx["variant"].id)
        )
        == 15
    )

    assert (
        client.put(
            f"/shop/inventory/{ctx['variant'].id}/threshold",
            json={"low_stock_threshold": 1},
            headers=other_headers,
        ).status_code
        == 403
    )
    assert (
        client.put(
            "/shop/inventory/999999999/threshold",
            json={"low_stock_threshold": 1},
            headers=ctx["owner_headers"],
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/shop/inventory/{ctx['variant'].id}/threshold",
            json={"low_stock_threshold": -1},
            headers=ctx["owner_headers"],
        ).status_code
        == 422
    )


def test_checkout_below_threshold_creates_single_alert_until_resolved(
    db_session: Session, client: TestClient
) -> None:
    context = seed_cart(db_session, stock=5)
    variant_id = context["variant"].id
    db_session.execute(
        Inventory.__table__.update()
        .where(Inventory.__table__.c.variant_id == variant_id)
        .values(low_stock_threshold=4)
    )
    db_session.commit()

    # Mỗi lần checkout trừ 2 -> còn 3, dưới ngưỡng 4 -> sinh đúng 1 alert.
    first = client.post("/orders/checkout", json=CHECKOUT_BODY, headers=context["headers"])
    assert first.status_code == 200
    alerts_after_first = client.get("/shop/alerts", headers=context["owner_headers"])
    assert alerts_after_first.status_code == 200
    assert len(alerts_after_first.json()) == 1
    assert alerts_after_first.json()[0]["variant_id"] == variant_id
    assert alerts_after_first.json()[0]["is_resolved"] is False

    # Thêm hàng vào giỏ và checkout tiếp, vẫn dưới ngưỡng -> KHÔNG sinh alert thứ 2.
    db_session.add(CartItem(cart_id=context["cart"].id, variant_id=variant_id, quantity=1))
    context["cart"].shop_id = context["shop"].id
    db_session.commit()
    second = client.post("/orders/checkout", json=CHECKOUT_BODY, headers=context["headers"])
    assert second.status_code == 200
    alerts_after_second = client.get("/shop/alerts", headers=context["owner_headers"])
    assert len(alerts_after_second.json()) == 1

    assert (
        db_session.scalar(select(Inventory.quantity).where(Inventory.variant_id == variant_id)) == 2
    )
    assert (
        db_session.scalar(select(LowStockAlert.id).where(LowStockAlert.variant_id == variant_id))
        is not None
    )


def test_cancel_order_restock_resolves_alert_when_above_threshold(
    db_session: Session, client: TestClient
) -> None:
    context = seed_cart(db_session, stock=5)
    variant_id = context["variant"].id
    db_session.execute(
        Inventory.__table__.update()
        .where(Inventory.__table__.c.variant_id == variant_id)
        .values(low_stock_threshold=4)
    )
    db_session.commit()

    order = client.post("/orders/checkout", json=CHECKOUT_BODY, headers=context["headers"]).json()
    assert (
        client.get("/shop/alerts", headers=context["owner_headers"]).json()[0]["is_resolved"]
        is False
    )

    cancelled = client.post(
        f"/orders/{order['id']}/cancel",
        json={"reason": "Đổi ý"},
        headers=context["headers"],
    )
    assert cancelled.status_code == 200
    assert (
        db_session.scalar(select(Inventory.quantity).where(Inventory.variant_id == variant_id)) == 5
    )
    assert client.get("/shop/alerts", headers=context["owner_headers"]).json() == []
    assert (
        db_session.scalar(
            select(LowStockAlert.is_resolved).where(LowStockAlert.variant_id == variant_id)
        )
        is True
    )
