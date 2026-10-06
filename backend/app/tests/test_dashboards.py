from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models import Inventory, Order, OrderItem, ProductVariant
from app.tests.test_catalog import user_with_token
from app.tests.test_shop_stats import client as client
from app.tests.test_shop_stats import make_order, seed_shop, utc

PARAMS = {"from": "2026-10-02", "to": "2026-10-03"}


def populated(db):
    ctx = seed_shop(db)
    second = ProductVariant(
        product_id=ctx["product"].id,
        size="L",
        color="Đỏ",
        price=900000,
        sku=f"dashboard-{uuid4().hex[:8]}",
    )
    db.add(second)
    db.flush()
    for status, created, delivered, amount, quantity, variant in [
        ("DELIVERED", utc(2026, 9, 28), utc(2026, 10, 1, 20), 100000, 1, ctx["variant"]),
        ("DELIVERED", utc(2026, 10, 2, 20), utc(2026, 10, 3, 12), 300000, 3, second),
        ("CANCELLED", utc(2026, 10, 2, 10), None, 900000, 1, second),
        ("PENDING", utc(2026, 10, 2, 10), None, 100000, 1, ctx["variant"]),
        ("PENDING", utc(2026, 9, 1), None, 100000, 1, ctx["variant"]),
        ("DELIVERED", utc(2026, 9, 30, 20), utc(2026, 9, 30, 20), 200000, 2, second),
    ]:
        make_order(
            db,
            ctx,
            status=status,
            created_at=created,
            delivered_at=delivered,
            total_amount=amount,
            quantity=quantity,
            variant=variant,
        )
    db.add_all(
        [
            Inventory(
                shop_id=ctx["shop"].id,
                variant_id=ctx["variant"].id,
                quantity=0,
                low_stock_threshold=5,
            ),
            Inventory(
                shop_id=ctx["shop"].id, variant_id=second.id, quantity=2, low_stock_threshold=5
            ),
        ]
    )
    db.commit()
    ctx["second"] = second
    return ctx


def test_shop_dashboard_periods_dates_snapshot_prices_and_actionable_current_queue(
    db_session, client
):
    ctx = populated(db_session)
    response = client.get("/shop/stats/dashboard", headers=ctx["headers"], params=PARAMS)
    assert response.status_code == 200
    data = response.json()
    assert (data["previous_from"], data["previous_to"]) == ("2026-09-30", "2026-10-01")
    assert data["overview"] == {
        "revenue": 400000,
        "order_count": 3,
        "cancelled_count": 1,
        "cancel_rate": 1 / 3,
        "aov": 200000,
    }
    assert data["previous"]["revenue"] == 200000 and data["previous"]["order_count"] == 1
    assert data["revenue_daily"] == [
        {"date": "2026-10-02", "revenue": 100000, "order_count": 1},
        {"date": "2026-10-03", "revenue": 300000, "order_count": 1},
    ]
    assert dict((row["status"], row["count"]) for row in data["order_statuses"]) == {
        "PENDING": 1,
        "CONFIRMED": 0,
        "PREPARING": 0,
        "SHIPPING": 0,
        "DELIVERED": 1,
        "CANCELLED": 1,
    }
    assert data["work_queue"][0] == {"status": "PENDING", "count": 2}
    assert data["top_products"][0]["total_quantity_sold"] == 4
    assert data["top_products"][0]["total_revenue"] == 400000
    assert data["stock"]["tracked_variants"] == 2
    assert (data["stock"]["out_of_stock"], data["stock"]["low_stock"]) == (1, 1)
    assert [(row["variant_id"], row["sold_quantity"]) for row in data["stock"]["priorities"]] == [
        (ctx["variant"].id, 1),
        (ctx["second"].id, 3),
    ]
    assert data["shops"] == []


def test_shop_cannot_select_another_shop_and_admin_sees_both_without_join_fanout(
    db_session, client
):
    ctx = populated(db_session)
    other = seed_shop(db_session, suffix="-dashboard")
    make_order(
        db_session,
        other,
        status="DELIVERED",
        created_at=utc(2026, 10, 2, 12),
        delivered_at=utc(2026, 10, 2, 12),
        total_amount=2000000,
    )
    db_session.add(
        Inventory(
            shop_id=other["shop"].id,
            variant_id=other["variant"].id,
            quantity=0,
            low_stock_threshold=0,
        )
    )
    db_session.commit()
    own = client.get(
        "/shop/stats/dashboard",
        headers=ctx["headers"],
        params={**PARAMS, "shop_id": other["shop"].id},
    ).json()
    assert own["overview"]["revenue"] == 400000
    assert own["stock"]["tracked_variants"] == 2
    assert {p["shop_name"] for p in own["top_products"]} == {ctx["shop"].name}
    _, admin = user_with_token(db_session, "dashboard-admin@example.com", "ADMIN")
    all_data = client.get("/admin/stats/dashboard", headers=admin, params=PARAMS).json()
    assert all_data["overview"]["revenue"] == 2400000
    assert all_data["overview"]["order_count"] == 4
    assert all_data["stock"]["out_of_stock"] == 2  # zero threshold still means no stock
    assert [(r["shop_id"], r["revenue"]) for r in all_data["shops"]] == [
        (other["shop"].id, 2000000),
        (ctx["shop"].id, 400000),
    ]
    assert sum(r["order_count"] for r in all_data["shops"]) == 4


@pytest.mark.parametrize("hidden", ["product", "variant", "shop"])
def test_hidden_catalog_is_not_restock_work_but_sales_history_is_preserved(
    db_session, client, hidden
):
    ctx = populated(db_session)
    target = ctx[hidden]
    target.is_active = False
    db_session.commit()
    data = client.get("/shop/stats/dashboard", headers=ctx["headers"], params=PARAMS).json()
    assert (
        data["overview"]["revenue"] == 400000 and data["top_products"][0]["total_revenue"] == 400000
    )
    assert data["stock"]["tracked_variants"] == (1 if hidden == "variant" else 0)


def test_empty_dashboard_null_ratios_and_read_only_reporting(db_session, client):
    ctx = seed_shop(db_session)
    before = db_session.scalar(select(func.count()).select_from(Order))
    data = client.get("/shop/stats/dashboard", headers=ctx["headers"], params=PARAMS).json()
    assert data["overview"]["revenue"] == 0 and data["overview"]["aov"] is None
    assert data["previous"]["cancel_rate"] is None
    assert data["revenue_daily"] == data["top_products"] == data["stock"]["priorities"] == []
    assert sum(r["count"] for r in data["order_statuses"] + data["work_queue"]) == 0
    assert db_session.scalar(select(func.count()).select_from(Order)) == before


def test_multiple_items_do_not_multiply_order_metrics_and_threshold_boundary_is_healthy(
    db_session, client
):
    ctx = seed_shop(db_session)
    second = ProductVariant(
        product_id=ctx["product"].id,
        size="L",
        color="Đỏ",
        price=999000,
        sku=f"dashboard-multi-{uuid4().hex[:8]}",
    )
    db_session.add(second)
    db_session.flush()
    order = make_order(
        db_session,
        ctx,
        status="DELIVERED",
        created_at=utc(2026, 10, 2),
        delivered_at=utc(2026, 10, 2),
        total_amount=100000,
    )
    order.total_amount = 400000
    db_session.add_all(
        [
            OrderItem(
                order_id=order.id,
                variant_id=second.id,
                product_name="Áo snapshot",
                size="L",
                color="Đỏ",
                unit_price=100000,
                quantity=3,
            ),
            Inventory(
                shop_id=ctx["shop"].id,
                variant_id=ctx["variant"].id,
                quantity=0,
                low_stock_threshold=0,
            ),
            Inventory(
                shop_id=ctx["shop"].id, variant_id=second.id, quantity=5, low_stock_threshold=5
            ),
        ]
    )
    db_session.commit()
    _, admin = user_with_token(db_session, "dashboard-multi@example.com", "ADMIN")
    data = client.get("/admin/stats/dashboard", headers=admin, params=PARAMS).json()
    assert data["overview"]["revenue"] == data["shops"][0]["revenue"] == 400000
    assert data["overview"]["order_count"] == data["shops"][0]["order_count"] == 1
    assert data["overview"]["aov"] == 400000
    assert data["top_products"][0]["total_quantity_sold"] == 4
    assert data["top_products"][0]["total_revenue"] == 400000
    assert (
        data["stock"]["tracked_variants"],
        data["stock"]["out_of_stock"],
        data["stock"]["low_stock"],
    ) == (2, 1, 0)
    assert [r["variant_id"] for r in data["stock"]["priorities"]] == [ctx["variant"].id]


@pytest.mark.parametrize("role", ["BUYER", "SHOP_OWNER", "ADMIN"])
def test_dashboard_endpoints_enforce_roles(db_session, client, role):
    _, headers = user_with_token(db_session, f"dashboard-{role}@example.com", role)
    for path in ("/shop/stats/dashboard", "/admin/stats/dashboard"):
        assert client.get(path, params=PARAMS).status_code == 401
        response = client.get(path, params=PARAMS, headers=headers)
        expected = 200 if role == "ADMIN" and path.startswith("/admin") else 403
        assert response.status_code == expected


@pytest.mark.parametrize(
    "params,code",
    [
        ({"from": "2026-10-03", "to": "2026-10-02"}, 400),
        ({"from": "0001-01-01", "to": "0001-01-02"}, 400),
        ({"from": "invalid", "to": "2026-10-02"}, 422),
        ({}, 422),
    ],
)
def test_dashboard_invalid_dates(db_session, client, params, code):
    ctx = seed_shop(db_session)
    assert (
        client.get("/shop/stats/dashboard", headers=ctx["headers"], params=params).status_code
        == code
    )
