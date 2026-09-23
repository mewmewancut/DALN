from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.main import app
from app.models import Category, Inventory, LowStockAlert, Product, ProductVariant, Shop, Supplier
from app.tests.test_catalog import user_with_token


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def seed_shop(
    db_session: Session, *, quantity: int = 10, threshold: int = 5, email_suffix: str = ""
) -> dict:
    owner, headers = user_with_token(
        db_session, f"po-owner{email_suffix}-{uuid4().hex[:8]}@example.com", "SHOP_OWNER"
    )
    shop = Shop(owner_id=owner.id, name="PO Shop")
    category = Category(name=f"PO category {uuid4().hex[:8]}")
    db_session.add_all([shop, category])
    db_session.flush()
    product = Product(
        shop_id=shop.id,
        category_id=category.id,
        name="Áo nhập hàng",
        base_price=100000,
    )
    db_session.add(product)
    db_session.flush()
    variant = ProductVariant(
        product_id=product.id,
        size="M",
        color="Đen",
        price=150000,
        sku=f"po-{uuid4().hex[:8]}",
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
    supplier = Supplier(shop_id=shop.id, name="NCC mặc định")
    db_session.add(supplier)
    db_session.commit()
    return {
        "headers": headers,
        "shop": shop,
        "variant": variant,
        "supplier": supplier,
    }


def po_body(
    supplier_id: int, variant_id: int, *, quantity: int = 10, unit_cost: int = 80000
) -> dict:
    return {
        "supplier_id": supplier_id,
        "items": [{"variant_id": variant_id, "quantity": quantity, "unit_cost": unit_cost}],
    }


def test_create_purchase_order_rejects_other_shop_variant_and_supplier(
    db_session: Session, client: TestClient
) -> None:
    ctx = seed_shop(db_session)
    other = seed_shop(db_session, email_suffix="-other")

    created = client.post(
        "/shop/purchase-orders",
        json=po_body(ctx["supplier"].id, ctx["variant"].id),
        headers=ctx["headers"],
    )
    assert created.status_code == 201
    assert created.json()["status"] == "DRAFT"
    assert created.json()["items"][0]["quantity"] == 10

    assert (
        client.post(
            "/shop/purchase-orders",
            json=po_body(ctx["supplier"].id, other["variant"].id),
            headers=ctx["headers"],
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/shop/purchase-orders",
            json=po_body(other["supplier"].id, ctx["variant"].id),
            headers=ctx["headers"],
        ).status_code
        == 403
    )

    duplicate_variant = client.post(
        "/shop/purchase-orders",
        json={
            "supplier_id": ctx["supplier"].id,
            "items": [
                {"variant_id": ctx["variant"].id, "quantity": 1, "unit_cost": 1000},
                {"variant_id": ctx["variant"].id, "quantity": 2, "unit_cost": 2000},
            ],
        },
        headers=ctx["headers"],
    )
    assert duplicate_variant.status_code == 422


def test_create_purchase_order_rejects_nonexistent_supplier_and_variant_with_404(
    db_session: Session, client: TestClient
) -> None:
    ctx = seed_shop(db_session)

    assert (
        client.post(
            "/shop/purchase-orders",
            json=po_body(999999999, ctx["variant"].id),
            headers=ctx["headers"],
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/shop/purchase-orders",
            json=po_body(ctx["supplier"].id, 999999999),
            headers=ctx["headers"],
        ).status_code
        == 404
    )

    assert (
        client.post(
            "/shop/purchase-orders", json=po_body(ctx["supplier"].id, ctx["variant"].id)
        ).status_code
        == 401
    )


def test_ordered_to_received_adds_stock_once_and_resolves_alert(
    db_session: Session, client: TestClient
) -> None:
    ctx = seed_shop(db_session, quantity=2, threshold=5)
    variant_id = ctx["variant"].id
    # Cảnh báo chỉ được tạo bởi check_low_stock (C6) sau một lần trừ kho;
    # ở đây seed thẳng một cảnh báo đang mở để kiểm tra bước resolve khi nhận hàng.
    db_session.add(
        LowStockAlert(variant_id=variant_id, shop_id=ctx["shop"].id, quantity_at_alert=2)
    )
    db_session.commit()
    alert_before = client.get("/shop/alerts", headers=ctx["headers"]).json()
    assert len(alert_before) == 1
    assert alert_before[0]["is_resolved"] is False

    po = client.post(
        "/shop/purchase-orders",
        json=po_body(ctx["supplier"].id, variant_id, quantity=10),
        headers=ctx["headers"],
    ).json()

    assert (
        client.patch(
            f"/shop/purchase-orders/{po['id']}/status",
            json={"status": "ORDERED"},
            headers=ctx["headers"],
        ).status_code
        == 200
    )
    received = client.patch(
        f"/shop/purchase-orders/{po['id']}/status",
        json={"status": "RECEIVED"},
        headers=ctx["headers"],
    )
    assert received.status_code == 200
    assert received.json()["status"] == "RECEIVED"
    assert received.json()["received_at"] is not None
    assert (
        db_session.scalar(select(Inventory.quantity).where(Inventory.variant_id == variant_id))
        == 12
    )
    assert client.get("/shop/alerts", headers=ctx["headers"]).json() == []
    assert (
        db_session.scalar(
            select(LowStockAlert.is_resolved).where(LowStockAlert.variant_id == variant_id)
        )
        is True
    )

    repeated = client.patch(
        f"/shop/purchase-orders/{po['id']}/status",
        json={"status": "RECEIVED"},
        headers=ctx["headers"],
    )
    assert repeated.status_code == 400
    assert (
        db_session.scalar(select(Inventory.quantity).where(Inventory.variant_id == variant_id))
        == 12
    )


def test_purchase_order_transitions_and_ownership(db_session: Session, client: TestClient) -> None:
    ctx = seed_shop(db_session)
    other = seed_shop(db_session, email_suffix="-viewer")
    po = client.post(
        "/shop/purchase-orders",
        json=po_body(ctx["supplier"].id, ctx["variant"].id),
        headers=ctx["headers"],
    ).json()

    assert (
        client.patch(
            f"/shop/purchase-orders/{po['id']}/status",
            json={"status": "RECEIVED"},
            headers=ctx["headers"],
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/shop/purchase-orders/{po['id']}/status",
            json={"status": "ORDERED"},
            headers=other["headers"],
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/shop/purchase-orders/999999999/status",
            json={"status": "ORDERED"},
            headers=ctx["headers"],
        ).status_code
        == 404
    )

    cancelled = client.patch(
        f"/shop/purchase-orders/{po['id']}/status",
        json={"status": "CANCELLED"},
        headers=ctx["headers"],
    )
    assert cancelled.status_code == 200
    assert (
        client.patch(
            f"/shop/purchase-orders/{po['id']}/status",
            json={"status": "ORDERED"},
            headers=ctx["headers"],
        ).status_code
        == 400
    )


def test_list_purchase_orders_filters_by_status_and_scope(
    db_session: Session, client: TestClient
) -> None:
    ctx = seed_shop(db_session)
    other = seed_shop(db_session, email_suffix="-list")
    client.post(
        "/shop/purchase-orders",
        json=po_body(ctx["supplier"].id, ctx["variant"].id),
        headers=ctx["headers"],
    )
    second = client.post(
        "/shop/purchase-orders",
        json=po_body(ctx["supplier"].id, ctx["variant"].id),
        headers=ctx["headers"],
    ).json()
    client.patch(
        f"/shop/purchase-orders/{second['id']}/status",
        json={"status": "ORDERED"},
        headers=ctx["headers"],
    )
    client.post(
        "/shop/purchase-orders",
        json=po_body(other["supplier"].id, other["variant"].id),
        headers=other["headers"],
    )

    all_pos = client.get("/shop/purchase-orders", headers=ctx["headers"])
    assert all_pos.status_code == 200
    assert all_pos.json()["total"] == 2

    ordered_only = client.get(
        "/shop/purchase-orders", params={"status": "ORDERED"}, headers=ctx["headers"]
    )
    assert ordered_only.json()["total"] == 1
    assert ordered_only.json()["items"][0]["id"] == second["id"]

    assert client.get("/shop/purchase-orders", headers=other["headers"]).json()["total"] == 1
