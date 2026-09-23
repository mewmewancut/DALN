from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base
from app.deps import get_db
from app.main import app
from app.models import Category, Inventory, LowStockAlert, Product, ProductVariant, Shop
from app.models.cart import CartItem
from app.services import inventory_service
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


def test_check_low_stock_never_raises_when_commit_fails(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = seed_variant(db_session, quantity=1, threshold=5)

    def fail_commit():
        raise RuntimeError("simulated check_low_stock commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    inventory_service.check_low_stock(db_session, ctx["variant"].id)


def test_resolve_alerts_if_ok_never_raises_when_commit_fails(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = seed_variant(db_session, quantity=10, threshold=5)
    db_session.add(
        LowStockAlert(variant_id=ctx["variant"].id, shop_id=ctx["shop"].id, quantity_at_alert=2)
    )
    db_session.commit()

    def fail_commit():
        raise RuntimeError("simulated resolve_alerts_if_ok commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    inventory_service.resolve_alerts_if_ok(db_session, ctx["variant"].id)


def test_concurrent_check_low_stock_creates_only_one_open_alert() -> None:
    schema = f"low_stock_race_test_{uuid4().hex}"
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
            owner, _ = user_with_token(setup, "race-low-stock-owner@example.com", "SHOP_OWNER")
            shop = Shop(owner_id=owner.id, name="Race Low Stock Shop")
            category = Category(name="Race low stock category")
            setup.add_all([shop, category])
            setup.flush()
            product = Product(
                shop_id=shop.id,
                category_id=category.id,
                name="Áo race low stock",
                base_price=100000,
            )
            setup.add(product)
            setup.flush()
            variant = ProductVariant(
                product_id=product.id,
                size="M",
                color="Đen",
                price=100000,
                sku=f"race-low-stock-{uuid4().hex[:8]}",
            )
            setup.add(variant)
            setup.flush()
            setup.add(
                Inventory(variant_id=variant.id, shop_id=shop.id, quantity=2, low_stock_threshold=5)
            )
            setup.commit()
            variant_id = variant.id

        barrier = Barrier(2)

        def run_check_low_stock(_: int) -> None:
            with Session(engine) as db:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                barrier.wait(timeout=10)
                inventory_service.check_low_stock(db, variant_id)

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(run_check_low_stock, range(2)))

        with Session(engine) as db:
            open_alerts = db.scalar(
                select(func.count())
                .select_from(LowStockAlert)
                .where(
                    LowStockAlert.variant_id == variant_id,
                    LowStockAlert.is_resolved.is_(False),
                )
            )
            assert open_alerts == 1
    finally:
        if engine is not None:
            engine.dispose()
        with control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        control.dispose()


def test_alert_resolution_serializes_with_concurrent_stock_decrement() -> None:
    schema = f"alert_resolution_race_test_{uuid4().hex}"
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
            owner, _ = user_with_token(setup, "resolve-race-owner@example.com", "SHOP_OWNER")
            shop = Shop(owner_id=owner.id, name="Resolve Race Shop")
            category = Category(name="Resolve race category")
            setup.add_all([shop, category])
            setup.flush()
            product = Product(
                shop_id=shop.id,
                category_id=category.id,
                name="Áo resolve race",
                base_price=100000,
            )
            setup.add(product)
            setup.flush()
            variant = ProductVariant(
                product_id=product.id,
                size="M",
                color="Đen",
                price=100000,
                sku=f"resolve-race-{uuid4().hex[:8]}",
            )
            setup.add(variant)
            setup.flush()
            setup.add(
                Inventory(
                    variant_id=variant.id,
                    shop_id=shop.id,
                    quantity=5,
                    low_stock_threshold=5,
                )
            )
            setup.add(
                LowStockAlert(
                    variant_id=variant.id,
                    shop_id=shop.id,
                    quantity_at_alert=2,
                )
            )
            setup.commit()
            variant_id = variant.id

        inventory_locked = Event()
        release_resolver = Event()
        decrement_started = Event()
        decrement_finished = Event()

        class PausingSession:
            def __init__(self, session: Session):
                self.session = session

            def scalar(self, statement):
                value = self.session.scalar(statement)
                inventory_locked.set()
                if not release_resolver.wait(timeout=10):
                    raise TimeoutError("Không nhận được tín hiệu tiếp tục resolver")
                return value

            def __getattr__(self, name):
                return getattr(self.session, name)

        def resolve_open_alert() -> None:
            with Session(engine) as db:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                inventory_service.resolve_alerts_if_ok(PausingSession(db), variant_id)

        def decrement_and_check_low_stock() -> None:
            if not inventory_locked.wait(timeout=10):
                raise TimeoutError("Resolver chưa khóa inventory")
            with Session(engine) as db:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                decrement_started.set()
                db.execute(
                    update(Inventory).where(Inventory.variant_id == variant_id).values(quantity=2)
                )
                db.commit()
                decrement_finished.set()
                inventory_service.check_low_stock(db, variant_id)

        with ThreadPoolExecutor(max_workers=2) as pool:
            resolver = pool.submit(resolve_open_alert)
            assert inventory_locked.wait(timeout=10)
            decrement = pool.submit(decrement_and_check_low_stock)
            assert decrement_started.wait(timeout=10)
            assert not decrement_finished.wait(timeout=0.3)
            release_resolver.set()
            resolver.result(timeout=10)
            decrement.result(timeout=10)

        with Session(engine) as db:
            assert (
                db.scalar(select(Inventory.quantity).where(Inventory.variant_id == variant_id)) == 2
            )
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(LowStockAlert)
                    .where(
                        LowStockAlert.variant_id == variant_id,
                        LowStockAlert.is_resolved.is_(False),
                    )
                )
                == 1
            )
    finally:
        if engine is not None:
            engine.dispose()
        with control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        control.dispose()
