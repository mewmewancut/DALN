from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.deps import get_db
from app.main import app
from app.tests.test_catalog import user_with_token
from app.tests.test_shop_stats import make_order, seed_shop, utc


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def admin_headers(db_session: Session) -> tuple:
    admin, headers = user_with_token(db_session, f"admin-{uuid4().hex[:8]}@example.com", "ADMIN")
    db_session.commit()
    return admin, headers


def test_list_and_lock_users_requires_admin_and_blocks_self_lock(
    db_session: Session, client: TestClient
) -> None:
    admin, headers = admin_headers(db_session)
    buyer, buyer_headers = user_with_token(
        db_session, f"admin-target-{uuid4().hex[:8]}@example.com", "BUYER"
    )
    db_session.commit()

    listed = client.get("/admin/users", params={"role": "BUYER"}, headers=headers)
    assert listed.status_code == 200
    assert buyer.id in [item["id"] for item in listed.json()["items"]]

    assert client.get("/admin/users").status_code == 401
    assert client.get("/admin/users", headers=buyer_headers).status_code == 403

    locked = client.patch(f"/admin/users/{buyer.id}", json={"is_active": False}, headers=headers)
    assert locked.status_code == 200
    assert locked.json()["is_active"] is False

    assert (
        client.patch(
            f"/admin/users/{admin.id}", json={"is_active": False}, headers=headers
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/admin/users/{admin.id}", json={"is_active": True}, headers=headers
        ).status_code
        == 200
    )
    assert (
        client.patch(
            "/admin/users/999999999", json={"is_active": False}, headers=headers
        ).status_code
        == 404
    )


def test_lock_shop_hides_its_products_from_public_catalog(
    db_session: Session, client: TestClient
) -> None:
    _, headers = admin_headers(db_session)
    ctx = seed_shop(db_session)

    shops_listed = client.get(
        "/admin/shops",
        params={"keyword": ctx["shop"].name, "is_active": True},
        headers=headers,
    )
    assert shops_listed.status_code == 200
    assert ctx["shop"].id in [item["id"] for item in shops_listed.json()["items"]]

    before = client.get("/products", params={"shop_id": ctx["shop"].id})
    assert before.json()["total"] == 1

    locked = client.patch(
        f"/admin/shops/{ctx['shop'].id}", json={"is_active": False}, headers=headers
    )
    assert locked.status_code == 200
    assert locked.json()["is_active"] is False

    locked_filter = client.get(
        "/admin/shops",
        params={"keyword": ctx["shop"].name, "is_active": False},
        headers=headers,
    )
    assert locked_filter.status_code == 200
    assert [item["id"] for item in locked_filter.json()["items"]] == [ctx["shop"].id]

    after = client.get("/products", params={"shop_id": ctx["shop"].id})
    assert after.json()["total"] == 0

    assert (
        client.patch(
            "/admin/shops/999999999", json={"is_active": False}, headers=headers
        ).status_code
        == 404
    )


def test_admin_orders_lists_across_shops_with_filters(
    db_session: Session, client: TestClient
) -> None:
    _, headers = admin_headers(db_session)
    ctx = seed_shop(db_session)
    other = seed_shop(db_session, suffix="-admin-orders")

    make_order(
        db_session,
        ctx,
        status="DELIVERED",
        created_at=utc(2026, 1, 1, 0, 0),
        delivered_at=utc(2026, 1, 1, 0, 0),
        total_amount=100000,
    )
    make_order(
        db_session,
        other,
        status="PENDING",
        created_at=utc(2026, 1, 1, 0, 0),
        delivered_at=None,
        total_amount=200000,
    )

    all_orders = client.get("/admin/orders", headers=headers)
    assert all_orders.status_code == 200
    assert all_orders.json()["total"] == 2

    scoped = client.get("/admin/orders", params={"shop_id": ctx["shop"].id}, headers=headers)
    assert scoped.json()["total"] == 1
    assert scoped.json()["items"][0]["shop_id"] == ctx["shop"].id

    filtered_status = client.get("/admin/orders", params={"status": "PENDING"}, headers=headers)
    assert filtered_status.json()["total"] == 1
    assert filtered_status.json()["items"][0]["status"] == "PENDING"

    assert client.get("/admin/orders").status_code == 401


def test_admin_stats_overview_aggregates_across_shops(
    db_session: Session, client: TestClient
) -> None:
    _, headers = admin_headers(db_session)
    ctx = seed_shop(db_session)
    other = seed_shop(db_session, suffix="-admin-stats")

    make_order(
        db_session,
        ctx,
        status="DELIVERED",
        created_at=utc(2026, 1, 1, 0, 0),
        delivered_at=utc(2026, 1, 1, 0, 0),
        total_amount=100000,
    )
    make_order(
        db_session,
        other,
        status="DELIVERED",
        created_at=utc(2026, 1, 1, 0, 0),
        delivered_at=utc(2026, 1, 1, 0, 0),
        total_amount=50000,
    )

    response = client.get(
        "/admin/stats/overview",
        params={"from": "2026-01-01", "to": "2026-01-01"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["revenue"] == 150000
    assert body["order_count"] == 2

    assert (
        client.get(
            "/admin/stats/overview", params={"from": "2026-01-02", "to": "2026-01-01"}
        ).status_code
        == 401
    )
