from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base
from app.models import Cart, CartItem, CartMerge, Inventory, Order
from app.schemas.cart import CartMergeRequest
from app.services.guest_cart_service import merge_cart
from app.tests.test_cart import add, create_catalog
from app.tests.test_cart import catalog as catalog
from app.tests.test_cart import client as client
from app.tests.test_checkout import CHECKOUT_BODY


def payload(variants, *quantities):
    return {
        "merge_id": str(uuid4()),
        "items": [
            {"variant_id": variant.id, "quantity": quantity}
            for variant, quantity in zip(variants, quantities, strict=True)
        ],
    }


def test_cart_keeps_multiple_shops_and_checkout_only_removes_selected_shop(
    client, db_session, catalog
):
    _, headers, _, _, shop, variants = catalog
    add(client, headers, variants[0], 2)
    before = add(client, headers, variants[2], 3).json()
    assert before["shop_id"] is None
    assert {item["shop_id"] for item in before["items"]} == {shop.id, variants[2].product.shop_id}
    assert before["total_amount"] == 2 * 120000 + 3 * 140000
    response = client.post(
        "/orders/checkout", headers=headers, json={**CHECKOUT_BODY, "shop_id": shop.id}
    )
    assert response.status_code == 200
    order = response.json()
    assert order["shop_id"] == shop.id
    assert order["total_amount"] == 240000
    assert [item["variant_id"] for item in order["items"]] == [variants[0].id]
    remaining = client.get("/cart", headers=headers).json()
    assert remaining["items"] == [before["items"][1]]
    assert (
        db_session.scalar(select(Inventory.quantity).where(Inventory.variant_id == variants[0].id))
        == 3
    )
    assert (
        db_session.scalar(select(Inventory.quantity).where(Inventory.variant_id == variants[2].id))
        == 5
    )


def test_multishop_checkout_requires_selection_and_rejects_unowned_shop(
    client, db_session, catalog
):
    _, headers, other_headers, _, shop, variants = catalog
    add(client, headers, variants[0])
    before = add(client, headers, variants[2]).json()
    for actor, body in [
        (headers, CHECKOUT_BODY),
        (headers, {**CHECKOUT_BODY, "shop_id": 999999999}),
        (other_headers, {**CHECKOUT_BODY, "shop_id": shop.id}),
    ]:
        assert client.post("/orders/checkout", headers=actor, json=body).status_code == 400
    assert client.get("/cart", headers=headers).json() == before
    assert db_session.scalar(select(func.count()).select_from(Order)) == 0
    assert list(db_session.scalars(select(Inventory.quantity))) == [5, 5, 5]


def test_checkout_rolls_back_selected_shop_and_preserves_other_shops(client, db_session, catalog):
    _, headers, _, _, shop, variants = catalog
    for variant in variants:
        add(client, headers, variant, 2)
    variants[1].inventory.quantity = 1
    db_session.commit()
    before = client.get("/cart", headers=headers).json()
    response = client.post(
        "/orders/checkout", headers=headers, json={**CHECKOUT_BODY, "shop_id": shop.id}
    )
    assert response.status_code == 409
    assert client.get("/cart", headers=headers).json() == before
    assert list(db_session.scalars(select(Inventory.quantity).order_by(Inventory.id))) == [5, 1, 5]
    assert db_session.scalar(select(func.count()).select_from(Order)) == 0


def test_unavailable_other_shop_does_not_block_selected_shop(client, db_session, catalog):
    _, headers, _, _, shop, variants = catalog
    add(client, headers, variants[0])
    add(client, headers, variants[2])
    variants[2].product.is_active = False
    db_session.commit()
    response = client.post(
        "/orders/checkout", headers=headers, json={**CHECKOUT_BODY, "shop_id": shop.id}
    )
    assert response.status_code == 200
    remaining = client.get("/cart", headers=headers).json()["items"]
    assert len(remaining) == 1
    assert remaining[0]["variant_id"] == variants[2].id
    assert remaining[0]["is_available"] is False


def test_guest_merge_adds_existing_variants_once_and_survives_replay_after_checkout(
    client, db_session, catalog
):
    _, headers, _, _, shop, variants = catalog
    add(client, headers, variants[0])
    request = payload([variants[0], variants[2]], 1, 2)
    merged = client.post("/cart/merge", headers=headers, json=request)
    assert merged.status_code == 200
    assert {item["variant_id"]: item["quantity"] for item in merged.json()["items"]} == {
        variants[0].id: 2,
        variants[2].id: 2,
    }
    replay = client.post(
        "/cart/merge", headers=headers, json={**request, "items": list(reversed(request["items"]))}
    )
    assert replay.json() == merged.json()
    assert db_session.scalar(select(func.count()).select_from(CartMerge)) == 1
    assert list(db_session.scalars(select(Inventory.quantity))) == [5, 5, 5]
    assert (
        client.post(
            "/orders/checkout", headers=headers, json={**CHECKOUT_BODY, "shop_id": shop.id}
        ).status_code
        == 200
    )
    replay_after_purchase = client.post("/cart/merge", headers=headers, json=request)
    assert [item["variant_id"] for item in replay_after_purchase.json()["items"]] == [
        variants[2].id
    ]


def test_merge_key_cannot_be_reused_with_different_payload(client, catalog):
    _, headers, _, _, _, variants = catalog
    request = payload([variants[0]], 1)
    before = client.post("/cart/merge", headers=headers, json=request).json()
    request["items"][0]["quantity"] = 2
    assert client.post("/cart/merge", headers=headers, json=request).status_code == 409
    assert client.get("/cart", headers=headers).json() == before


@pytest.mark.parametrize("failure", ["missing", "hidden", "stock"])
def test_guest_merge_is_atomic_and_failed_key_can_retry(client, db_session, catalog, failure):
    _, headers, _, _, _, variants = catalog
    add(client, headers, variants[0], 1)
    request = payload([variants[1], variants[2]], 1, 1)
    if failure == "missing":
        request["items"][1]["variant_id"] = 999999999
    elif failure == "hidden":
        variants[2].is_active = False
    else:
        request["items"][1]["quantity"] = 6
    db_session.commit()
    before = client.get("/cart", headers=headers).json()
    response = client.post("/cart/merge", headers=headers, json=request)
    assert response.status_code == (409 if failure == "stock" else 404)
    assert client.get("/cart", headers=headers).json() == before
    assert db_session.scalar(select(func.count()).select_from(CartMerge)) == 0
    assert db_session.scalar(select(func.count()).select_from(CartItem)) == 1
    request["items"][1] = {"variant_id": variants[2].id, "quantity": 1}
    variants[2].is_active = True
    db_session.commit()
    assert client.post("/cart/merge", headers=headers, json=request).status_code == 200


def test_guest_merge_checks_combined_quantity_without_capping(client, catalog):
    _, headers, _, _, _, variants = catalog
    before = add(client, headers, variants[0], 4).json()
    response = client.post("/cart/merge", headers=headers, json=payload([variants[0]], 2))
    assert response.status_code == 409
    assert client.get("/cart", headers=headers).json() == before


def test_guest_preview_is_public_current_and_does_not_write_cart_or_inventory(
    client, db_session, catalog
):
    _, _, _, _, _, variants = catalog
    variants[0].price = 333000
    variants[0].inventory.quantity = 2
    variants[1].is_active = False
    db_session.commit()
    response = client.post(
        "/cart/preview",
        json={
            "items": [
                {"variant_id": variants[0].id, "quantity": 3},
                {"variant_id": variants[1].id, "quantity": 1},
                {"variant_id": 999999999, "quantity": 1},
            ]
        },
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["unit_price"] == 333000
    assert items[0]["stock_quantity"] == 2
    assert items[0]["quantity"] == 3
    for item in items[1:]:
        assert item["is_available"] is False
        assert item["product_id"] is None
        assert item["unit_price"] == 0
        assert item["product_name"] == "Sản phẩm không còn khả dụng"
    assert db_session.scalar(select(func.count()).select_from(Cart)) == 0
    assert db_session.scalar(select(func.count()).select_from(CartMerge)) == 0
    assert variants[0].inventory.quantity == 2


def test_guest_merge_permissions_and_body_validation(client, catalog):
    _, headers, _, owner_headers, _, variants = catalog
    request = payload([variants[0]], 1)
    assert client.post("/cart/merge", json=request).status_code == 401
    assert client.post("/cart/merge", headers=owner_headers, json=request).status_code == 403
    for extra in [{"buyer_id": 1}, {"shop_id": 1}, {"total_amount": 1}]:
        assert (
            client.post("/cart/merge", headers=headers, json={**request, **extra}).status_code
            == 422
        )
    for item in [
        {"variant_id": True, "quantity": 1},
        {"variant_id": variants[0].id, "quantity": True},
        {"variant_id": variants[0].id, "quantity": 0},
        {"variant_id": variants[0].id, "quantity": 1, "unit_price": 1},
    ]:
        assert client.post("/cart/preview", json={"items": [item]}).status_code == 422
    assert client.post("/cart/preview", json={"items": request["items"] * 2}).status_code == 422


def test_guest_merge_rolls_back_on_commit_failure(client, db_session, catalog, monkeypatch):
    _, headers, _, _, _, variants = catalog
    before = add(client, headers, variants[0]).json()

    def fail_commit():
        raise RuntimeError("simulated merge commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="simulated merge commit failure"):
        client.post("/cart/merge", headers=headers, json=payload([variants[1]], 1))
    assert client.get("/cart", headers=headers).json() == before
    assert db_session.scalar(select(func.count()).select_from(CartMerge)) == 0


def test_concurrent_guest_imports_apply_only_once():
    schema = f"guest_cart_test_{uuid4().hex}"
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
            request = CartMergeRequest(**payload([variants[0], variants[2]], 1, 1))
        barrier = Barrier(2)

        def import_concurrently(_):
            with Session(engine) as db:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                barrier.wait(timeout=10)
                return merge_cart(db, buyer_id, request)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(import_concurrently, range(2)))
        assert all(len(result.items) == 2 for result in results)
        with Session(engine) as db:
            assert list(db.scalars(select(CartItem.quantity))) == [1, 1]
            assert db.scalar(select(func.count()).select_from(CartMerge)) == 1
    finally:
        if engine is not None:
            engine.dispose()
        with control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        control.dispose()


def test_guest_preview_item_limit_and_empty_cart(client):
    assert client.post("/cart/preview", json={"items": []}).json()["items"] == []
    items = [{"variant_id": 900000 + number, "quantity": 1} for number in range(200)]
    assert len(client.post("/cart/preview", json={"items": items}).json()["items"]) == 200
    items.append({"variant_id": 900200, "quantity": 1})
    assert client.post("/cart/preview", json={"items": items}).status_code == 422


@pytest.mark.parametrize("shop_id", [0, -1, True, "1", 1.5, []])
def test_checkout_rejects_invalid_shop_selection(client, catalog, shop_id):
    _, headers, _, _, _, variants = catalog
    before = add(client, headers, variants[0]).json()
    assert (
        client.post(
            "/orders/checkout", headers=headers, json={**CHECKOUT_BODY, "shop_id": shop_id}
        ).status_code
        == 422
    )
    assert client.get("/cart", headers=headers).json() == before
