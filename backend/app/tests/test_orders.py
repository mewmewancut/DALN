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
from app.services.order_service import transition_order
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


def create_order(client: TestClient, db_session: Session, *, payment_method: str = "COD") -> dict:
    context = seed_cart(db_session, stock=5)
    response = client.post(
        "/orders/checkout",
        json={**CHECKOUT_BODY, "payment_method": payment_method},
        headers=context["headers"],
    )
    assert response.status_code == 200
    context["order"] = response.json()
    return context


def change_status(client: TestClient, context: dict, status: str, note: str | None = None):
    body = {"status": status}
    if note is not None:
        body["note"] = note
    return client.patch(
        f"/orders/{context['order']['id']}/status",
        json=body,
        headers=context["owner_headers"],
    )


def test_order_happy_path_lists_details_history_and_delivery(
    db_session: Session, client: TestClient
) -> None:
    context = create_order(client, db_session)
    order_id = context["order"]["id"]

    buyer_list = client.get("/orders/my", headers=context["headers"])
    assert buyer_list.status_code == 200
    assert buyer_list.json()["total"] == 1
    assert buyer_list.json()["items"][0]["id"] == order_id
    assert (
        client.get(
            "/orders/my",
            params={"status": "DELIVERED"},
            headers=context["headers"],
        ).json()["total"]
        == 0
    )

    shop_list = client.get("/shop/orders", headers=context["owner_headers"])
    assert shop_list.status_code == 200
    assert shop_list.json()["items"][0]["buyer_id"] == context["buyer"].id
    shop_detail = client.get(f"/orders/{order_id}", headers=context["owner_headers"])
    assert shop_detail.status_code == 200
    assert shop_detail.json()["id"] == order_id

    for status in ("CONFIRMED", "PREPARING", "SHIPPING"):
        response = change_status(client, context, status)
        assert response.status_code == 200
        assert response.json()["status"] == status
    delivered = change_status(client, context, "DELIVERED", "Đã giao cho người nhận")
    assert delivered.status_code == 200
    body = delivered.json()
    assert body["delivered_at"] is not None
    assert body["payment_status"] == "PAID"
    assert [entry["to_status"] for entry in body["status_history"]] == [
        "PENDING",
        "CONFIRMED",
        "PREPARING",
        "SHIPPING",
        "DELIVERED",
    ]
    assert body["status_history"][-1]["note"] == "Đã giao cho người nhận"
    delivered_shop_list = client.get(
        "/shop/orders",
        params={"status": "DELIVERED"},
        headers=context["owner_headers"],
    )
    assert delivered_shop_list.status_code == 200
    assert delivered_shop_list.json()["total"] == 1
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order_id)
        )
        == 5
    )

    detail = client.get(f"/orders/{order_id}", headers=context["headers"])
    assert detail.status_code == 200
    assert detail.json()["items"] == context["order"]["items"]


def test_order_rejects_skipped_and_forbidden_transitions(
    db_session: Session, client: TestClient
) -> None:
    context = create_order(client, db_session)
    order_id = context["order"]["id"]
    assert change_status(client, context, "SHIPPING").status_code == 400
    assert db_session.get(Order, order_id).status == "PENDING"

    assert change_status(client, context, "CONFIRMED").status_code == 200
    buyer_cancel = client.post(
        f"/orders/{order_id}/cancel",
        json={"reason": "Không muốn mua nữa"},
        headers=context["headers"],
    )
    assert buyer_cancel.status_code == 400
    assert change_status(client, context, "PREPARING").status_code == 200
    assert change_status(client, context, "CANCELLED").status_code == 400
    assert change_status(client, context, "SHIPPING").status_code == 200
    assert change_status(client, context, "DELIVERED").status_code == 200
    assert change_status(client, context, "CANCELLED").status_code == 400
    assert db_session.get(Order, order_id).status == "DELIVERED"


def test_buyer_cancellation_restocks_exactly_once(db_session: Session, client: TestClient) -> None:
    context = create_order(client, db_session)
    order_id = context["order"]["id"]
    variant_id = context["variant"].id
    assert (
        db_session.scalar(select(Inventory.quantity).where(Inventory.variant_id == variant_id)) == 3
    )

    cancelled = client.post(
        f"/orders/{order_id}/cancel",
        json={"reason": "Đổi ý"},
        headers=context["headers"],
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["cancel_reason"] == "Đổi ý"
    assert cancelled.json()["cancelled_at"] is not None
    assert (
        db_session.scalar(select(Inventory.quantity).where(Inventory.variant_id == variant_id)) == 5
    )

    repeated = client.post(
        f"/orders/{order_id}/cancel",
        json={"reason": "Hủy lần nữa"},
        headers=context["headers"],
    )
    assert repeated.status_code == 400
    assert (
        db_session.scalar(select(Inventory.quantity).where(Inventory.variant_id == variant_id)) == 5
    )


def test_cancellation_rolls_back_status_history_and_stock_on_commit_failure(
    db_session: Session, client: TestClient, monkeypatch
) -> None:
    context = create_order(client, db_session)
    order_id = context["order"]["id"]
    variant_id = context["variant"].id

    def fail_commit():
        raise RuntimeError("simulated transition commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="simulated transition commit failure"):
        client.post(
            f"/orders/{order_id}/cancel",
            json={"reason": "Đổi ý"},
            headers=context["headers"],
        )

    assert db_session.get(Order, order_id).status == "PENDING"
    assert (
        db_session.scalar(select(Inventory.quantity).where(Inventory.variant_id == variant_id)) == 3
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order_id)
        )
        == 1
    )


def test_shop_can_cancel_confirmed_order_once(db_session: Session, client: TestClient) -> None:
    context = create_order(client, db_session)
    variant_id = context["variant"].id
    assert change_status(client, context, "CONFIRMED").status_code == 200

    cancelled = change_status(client, context, "CANCELLED", "Shop hết khả năng xử lý")
    assert cancelled.status_code == 200
    assert cancelled.json()["cancel_reason"] == "Shop hết khả năng xử lý"
    assert (
        db_session.scalar(select(Inventory.quantity).where(Inventory.variant_id == variant_id)) == 5
    )
    assert change_status(client, context, "CANCELLED").status_code == 400
    assert (
        db_session.scalar(select(Inventory.quantity).where(Inventory.variant_id == variant_id)) == 5
    )


def test_order_access_is_scoped_to_buyer_and_database_shop(
    db_session: Session, client: TestClient
) -> None:
    context = create_order(client, db_session)
    order_id = context["order"]["id"]
    _, other_buyer = user_with_token(db_session, "other-order-buyer@example.com", "BUYER")
    other_owner, other_owner_headers = user_with_token(
        db_session, "other-order-owner@example.com", "SHOP_OWNER"
    )
    db_session.add(Shop(owner_id=other_owner.id, name="Other Order Shop"))
    admin, admin_headers = user_with_token(db_session, "order-admin@example.com", "ADMIN")
    db_session.commit()

    assert client.get(f"/orders/{order_id}", headers=other_buyer).status_code == 403
    assert (
        client.post(
            f"/orders/{order_id}/cancel",
            json={"reason": "Chiếm đơn"},
            headers=other_buyer,
        ).status_code
        == 403
    )
    assert client.get(f"/orders/{order_id}", headers=other_owner_headers).status_code == 403
    assert (
        client.patch(
            f"/orders/{order_id}/status",
            json={"status": "CONFIRMED"},
            headers=other_owner_headers,
        ).status_code
        == 403
    )
    assert client.get("/shop/orders", headers=other_owner_headers).json()["total"] == 0
    assert (
        client.patch(
            f"/orders/{order_id}/status",
            json={"status": "CONFIRMED"},
            headers=other_buyer,
        ).status_code
        == 403
    )
    admin_detail = client.get(f"/orders/{order_id}", headers=admin_headers)
    assert admin_detail.status_code == 200
    assert admin_detail.json()["buyer_id"] == context["buyer"].id
    assert admin_detail.json()["id"] == order_id
    assert admin.id != context["buyer"].id
    assert (
        client.patch(
            f"/orders/{order_id}/status",
            json={"status": "CONFIRMED"},
            headers=admin_headers,
        ).status_code
        == 403
    )

    assert client.get("/orders/my", headers=other_buyer).json()["total"] == 0
    assert (
        client.get("/orders/my", params={"status": "INVALID"}, headers=other_buyer).status_code
        == 422
    )
    assert client.get("/orders/my", params={"page_size": 0}, headers=other_buyer).status_code == 422
    assert client.get(f"/orders/{order_id}").status_code == 401
    assert client.get("/shop/orders", headers=other_buyer).status_code == 403
    assert client.get("/orders/999999999", headers=admin_headers).status_code == 404


def test_concurrent_buyer_cancel_and_shop_confirm_apply_one_transition() -> None:
    schema = f"order_transition_test_{uuid4().hex}"
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
            owner, _ = user_with_token(setup, "race-order-owner@example.com", "SHOP_OWNER")
            buyer, _ = user_with_token(setup, "race-order-buyer@example.com", "BUYER")
            shop = Shop(owner_id=owner.id, name="Race Order Shop")
            category = Category(name="Race Order Category")
            setup.add_all([shop, category])
            setup.flush()
            product = Product(
                shop_id=shop.id,
                category_id=category.id,
                name="Áo race order",
                base_price=100000,
            )
            setup.add(product)
            setup.flush()
            variant = ProductVariant(
                product_id=product.id,
                size="M",
                color="Đen",
                price=150000,
                sku=f"race-order-{uuid4().hex[:8]}",
            )
            setup.add(variant)
            setup.flush()
            setup.add(Inventory(variant_id=variant.id, shop_id=shop.id, quantity=3))
            order = Order(
                code="RACE-ORDER-1",
                buyer_id=buyer.id,
                shop_id=shop.id,
                shipping_address="Địa chỉ race",
                receiver_name="Người nhận",
                receiver_phone="0900000000",
                payment_method="COD",
                total_amount=300000,
            )
            setup.add(order)
            setup.flush()
            setup.add_all(
                [
                    OrderItem(
                        order_id=order.id,
                        variant_id=variant.id,
                        product_name=product.name,
                        size=variant.size,
                        color=variant.color,
                        unit_price=variant.price,
                        quantity=2,
                    ),
                    OrderStatusHistory(
                        order_id=order.id,
                        from_status=None,
                        to_status="PENDING",
                        changed_by=buyer.id,
                    ),
                ]
            )
            setup.commit()
            owner_id = owner.id
            buyer_id = buyer.id
            shop_id = shop.id
            order_id = order.id
            variant_id = variant.id

        barrier = Barrier(2)

        def run_transition(actor_id: int, status: str):
            with Session(engine) as db:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                actor = db.get(User, actor_id)
                barrier.wait(timeout=10)
                try:
                    transition_order(
                        db,
                        order_id,
                        status,
                        actor,
                        shop_id=shop_id if status == "CONFIRMED" else None,
                        note="race",
                    )
                    return 200
                except HTTPException as error:
                    return error.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda args: run_transition(*args),
                    [(buyer_id, "CANCELLED"), (owner_id, "CONFIRMED")],
                )
            )

        assert sorted(results) == [200, 400]
        with Session(engine) as db:
            final_order = db.get(Order, order_id)
            quantity = db.scalar(
                select(Inventory.quantity).where(Inventory.variant_id == variant_id)
            )
            assert (final_order.status, quantity) in {("CANCELLED", 5), ("CONFIRMED", 3)}
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(OrderStatusHistory)
                    .where(OrderStatusHistory.order_id == order_id)
                )
                == 2
            )
    finally:
        if engine is not None:
            engine.dispose()
        with control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        control.dispose()
