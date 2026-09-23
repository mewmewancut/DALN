from collections.abc import Generator
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.deps import get_db
from app.main import app
from app.models import Category, Order, OrderItem, Product, ProductVariant, Shop
from app.tests.test_catalog import user_with_token


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def seed_shop(db_session: Session, *, suffix: str = "") -> dict:
    owner, headers = user_with_token(
        db_session, f"stats-owner{suffix}-{uuid4().hex[:8]}@example.com", "SHOP_OWNER"
    )
    shop = Shop(owner_id=owner.id, name="Stats Shop")
    category = Category(name=f"Stats category {uuid4().hex[:8]}")
    db_session.add_all([shop, category])
    db_session.flush()
    product = Product(shop_id=shop.id, category_id=category.id, name="Áo stats", base_price=100000)
    db_session.add(product)
    db_session.flush()
    variant = ProductVariant(
        product_id=product.id, size="M", color="Đen", price=100000, sku=f"stats-{uuid4().hex[:8]}"
    )
    db_session.add(variant)
    db_session.flush()
    db_session.commit()
    return {"headers": headers, "shop": shop, "product": product, "variant": variant}


def make_order(
    db_session: Session,
    ctx: dict,
    *,
    status: str,
    created_at: datetime,
    delivered_at: datetime | None,
    total_amount: int,
    quantity: int = 1,
    variant: ProductVariant | None = None,
) -> Order:
    buyer, _ = user_with_token(db_session, f"stats-buyer-{uuid4().hex[:8]}@example.com", "BUYER")
    variant = variant or ctx["variant"]
    order = Order(
        code=f"ORD-STATS-{uuid4().hex[:10]}",
        buyer_id=buyer.id,
        shop_id=ctx["shop"].id,
        status=status,
        shipping_address="Địa chỉ",
        receiver_name="Người nhận",
        receiver_phone="0900000000",
        payment_method="COD",
        total_amount=total_amount,
        created_at=created_at,
        delivered_at=delivered_at,
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            variant_id=variant.id,
            product_name=ctx["product"].name,
            size=variant.size,
            color=variant.color,
            unit_price=total_amount // quantity,
            quantity=quantity,
        )
    )
    db_session.commit()
    return order


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_overview_uses_vn_date_for_revenue_and_created_date_for_order_count(
    db_session: Session, client: TestClient
) -> None:
    ctx = seed_shop(db_session)
    other = seed_shop(db_session, suffix="-other")

    # 20:00 UTC 01/01 = 03:00 giờ VN 02/01 -> tính doanh thu vào ngày 02/01 VN.
    make_order(
        db_session,
        ctx,
        status="DELIVERED",
        created_at=utc(2026, 1, 1, 20, 0),
        delivered_at=utc(2026, 1, 1, 20, 0),
        total_amount=100000,
    )
    # 10:00 UTC 01/01 = 17:00 giờ VN 01/01 -> vẫn thuộc ngày 01/01 VN, ngoài kỳ lọc.
    make_order(
        db_session,
        ctx,
        status="DELIVERED",
        created_at=utc(2026, 1, 1, 10, 0),
        delivered_at=utc(2026, 1, 1, 10, 0),
        total_amount=500000,
    )
    make_order(
        db_session,
        ctx,
        status="CANCELLED",
        created_at=utc(2026, 1, 1, 20, 30),
        delivered_at=None,
        total_amount=200000,
    )
    make_order(
        db_session,
        other,
        status="DELIVERED",
        created_at=utc(2026, 1, 1, 20, 0),
        delivered_at=utc(2026, 1, 1, 20, 0),
        total_amount=999999,
    )

    response = client.get(
        "/shop/stats/overview",
        params={"from": "2026-01-02", "to": "2026-01-02"},
        headers=ctx["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["revenue"] == 100000
    assert body["order_count"] == 2
    assert body["cancelled_count"] == 1
    assert body["cancel_rate"] == pytest.approx(0.5)
    assert body["aov"] == pytest.approx(100000.0)

    empty = client.get(
        "/shop/stats/overview",
        params={"from": "2026-02-01", "to": "2026-02-01"},
        headers=ctx["headers"],
    )
    assert empty.json() == {
        "revenue": 0,
        "order_count": 0,
        "cancelled_count": 0,
        "cancel_rate": None,
        "aov": None,
    }

    assert (
        client.get(
            "/shop/stats/overview", params={"from": "2026-01-02", "to": "2026-01-01"}
        ).status_code
        == 401
    )
    _, buyer_headers = user_with_token(db_session, "stats-buyer-role@example.com", "BUYER")
    db_session.commit()
    assert (
        client.get(
            "/shop/stats/overview",
            params={"from": "2026-01-02", "to": "2026-01-01"},
            headers=buyer_headers,
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/shop/stats/overview",
            params={"from": "2026-01-02", "to": "2026-01-01"},
            headers=ctx["headers"],
        ).status_code
        == 400
    )


def test_revenue_by_day_groups_by_vn_delivered_date_and_scopes_to_shop(
    db_session: Session, client: TestClient
) -> None:
    ctx = seed_shop(db_session)
    make_order(
        db_session,
        ctx,
        status="DELIVERED",
        created_at=utc(2026, 1, 1, 20, 0),
        delivered_at=utc(2026, 1, 1, 20, 0),
        total_amount=100000,
    )
    make_order(
        db_session,
        ctx,
        status="DELIVERED",
        created_at=utc(2026, 1, 2, 1, 0),
        delivered_at=utc(2026, 1, 2, 1, 0),
        total_amount=50000,
    )
    make_order(
        db_session,
        ctx,
        status="PENDING",
        created_at=utc(2026, 1, 2, 1, 0),
        delivered_at=None,
        total_amount=999999,
    )

    response = client.get(
        "/shop/stats/revenue-by-day",
        params={"from": "2026-01-01", "to": "2026-01-03"},
        headers=ctx["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body == [
        {"date": "2026-01-02", "revenue": 150000, "order_count": 2},
    ]


def test_top_products_aggregates_across_variants_and_orders_desc(
    db_session: Session, client: TestClient
) -> None:
    ctx = seed_shop(db_session)
    second_variant = ProductVariant(
        product_id=ctx["product"].id,
        size="L",
        color="Đen",
        price=100000,
        sku=f"stats-2-{uuid4().hex[:8]}",
    )
    db_session.add(second_variant)
    db_session.flush()
    db_session.commit()

    other_product = Product(
        shop_id=ctx["shop"].id,
        category_id=ctx["product"].category_id,
        name="Quần stats",
        base_price=50000,
    )
    db_session.add(other_product)
    db_session.flush()
    other_variant = ProductVariant(
        product_id=other_product.id,
        size="M",
        color="Xanh",
        price=50000,
        sku=f"stats-3-{uuid4().hex[:8]}",
    )
    db_session.add(other_variant)
    db_session.flush()
    db_session.commit()

    make_order(
        db_session,
        ctx,
        status="DELIVERED",
        created_at=utc(2026, 1, 1, 0, 0),
        delivered_at=utc(2026, 1, 1, 0, 0),
        total_amount=100000,
        quantity=3,
        variant=ctx["variant"],
    )
    make_order(
        db_session,
        ctx,
        status="DELIVERED",
        created_at=utc(2026, 1, 1, 0, 0),
        delivered_at=utc(2026, 1, 1, 0, 0),
        total_amount=100000,
        quantity=4,
        variant=second_variant,
    )
    make_order(
        db_session,
        ctx,
        status="DELIVERED",
        created_at=utc(2026, 1, 1, 0, 0),
        delivered_at=utc(2026, 1, 1, 0, 0),
        total_amount=50000,
        quantity=2,
        variant=other_variant,
    )
    make_order(
        db_session,
        ctx,
        status="PENDING",
        created_at=utc(2026, 1, 1, 0, 0),
        delivered_at=None,
        total_amount=100000,
        quantity=100,
        variant=ctx["variant"],
    )

    response = client.get("/shop/stats/top-products", params={"limit": 1}, headers=ctx["headers"])
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["product_id"] == ctx["product"].id
    assert body[0]["total_quantity_sold"] == 7

    full = client.get("/shop/stats/top-products", headers=ctx["headers"]).json()
    assert [item["product_id"] for item in full] == [ctx["product"].id, other_product.id]
