from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.main import app
from app.models import (
    Category,
    Inventory,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    Review,
    Shop,
    UserPreference,
)
from app.tests.test_catalog import user_with_token


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def catalog(db_session: Session):
    _, headers = user_with_token(db_session, "recommend-buyer@example.com", "BUYER")
    _, other_headers = user_with_token(db_session, "recommend-other@example.com", "BUYER")
    owner, _ = user_with_token(db_session, "recommend-owner@example.com", "SHOP_OWNER")
    shop = Shop(owner_id=owner.id, name="Shop gợi ý")
    shirts = Category(name="Áo gợi ý")
    shoes = Category(name="Giày gợi ý")
    db_session.add_all([shop, shirts, shoes])
    db_session.flush()
    return shop, shirts, shoes, headers, other_headers


def add_product(db, shop, category, name, variants, *, day=0, active=True):
    product = Product(
        shop_id=shop.id,
        category_id=category.id,
        name=name,
        base_price=999999,
        is_active=active,
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc) + timedelta(days=day),
    )
    db.add(product)
    db.flush()
    for index, (color, price, quantity, variant_active) in enumerate(variants):
        variant = ProductVariant(
            product_id=product.id,
            size=f"M{index}",
            color=color,
            price=price,
            sku=f"recommend-{product.id}-{index}",
            is_active=variant_active,
        )
        db.add(variant)
        db.flush()
        if quantity is not None:
            db.add(Inventory(variant_id=variant.id, shop_id=shop.id, quantity=quantity))
    db.flush()
    return product


def ids(client, headers, **params):
    response = client.get("/users/me/recommendations", headers=headers, params=params)
    assert response.status_code == 200
    return [item["id"] for item in response.json()]


def test_scores_each_criterion_once_and_orders_ties_before_limiting(client, db_session, catalog):
    shop, shirts, shoes, headers, _ = catalog
    full = add_product(
        db_session,
        shop,
        shirts,
        "Khớp ba tiêu chí",
        [("Đen", 100000, 2, True), ("Đen", 200000, 3, True)],
    )
    full_new = add_product(
        db_session, shop, shirts, "Ba tiêu chí mới hơn", [("Đen", 150000, 1, True)], day=1
    )
    two = add_product(db_session, shop, shirts, "Khớp hai", [("Đen", 400000, 1, True)], day=1)
    one_new = add_product(db_session, shop, shoes, "Khớp giá mới", [("Đỏ", 150000, 1, True)], day=3)
    one_old = add_product(db_session, shop, shoes, "Khớp màu cũ", [("Đen", 400000, 1, True)], day=2)
    neutral = add_product(db_session, shop, shoes, "Không khớp", [("Đỏ", 400000, 1, True)], day=4)
    db_session.commit()
    saved = client.put(
        "/users/me/preferences",
        headers=headers,
        json={
            "category_ids": [shirts.id],
            "colors": ["Đen"],
            "min_price": 100000,
            "max_price": 200000,
        },
    )
    assert saved.status_code == 200
    expected = [full_new.id, full.id, two.id, one_new.id, one_old.id, neutral.id]
    assert ids(client, headers) == expected
    assert ids(client, headers, limit=3) == expected[:3]
    assert ids(client, headers) == expected


@pytest.mark.parametrize("save_empty", [False, True])
def test_empty_preferences_fall_back_to_newest_without_creating_preferences(
    client, db_session, catalog, save_empty
):
    shop, shirts, _, headers, _ = catalog
    products = [
        add_product(db_session, shop, shirts, str(index), [("Đen", 100000, 1, True)])
        for index in range(10)
    ]
    newest = add_product(db_session, shop, shirts, "Mới nhất", [("Đỏ", 100000, 1, True)], day=1)
    db_session.commit()
    if save_empty:
        assert client.put("/users/me/preferences", headers=headers, json={}).status_code == 200
    assert ids(client, headers) == [newest.id] + [item.id for item in reversed(products[-7:])]
    assert ids(client, headers, limit=20) == [newest.id] + [item.id for item in reversed(products)]
    assert db_session.scalar(select(func.count()).select_from(UserPreference)) == int(save_empty)


@pytest.mark.parametrize(
    "bounds, matching_price",
    [
        ({"min_price": 100000}, 100000),
        ({"max_price": 100000}, 100000),
        ({"min_price": 100000, "max_price": 200000}, 100000),
        ({"min_price": 100000, "max_price": 200000}, 200000),
        ({"min_price": 0, "max_price": 0}, 0),
    ],
)
def test_price_boundaries_are_inclusive_and_use_any_in_stock_variant(
    client, db_session, catalog, bounds, matching_price
):
    shop, shirts, _, headers, _ = catalog
    match = add_product(
        db_session,
        shop,
        shirts,
        "Có variant đúng giá",
        [("Đen", matching_price, 1, True), ("Đỏ", 1, 0, True)],
    )
    outside_price = 99999 if "min_price" in bounds and bounds["min_price"] else 300000
    outside = add_product(
        db_session, shop, shirts, "Ngoài khoảng", [("Đen", outside_price, 1, True)], day=1
    )
    db_session.commit()
    assert client.put("/users/me/preferences", headers=headers, json=bounds).status_code == 200
    assert ids(client, headers) == [match.id, outside.id]
    result = client.get("/users/me/recommendations", headers=headers).json()[0]
    assert result["price_from"] == min(matching_price, 1)
    assert result["base_price"] == 999999


def test_hidden_sold_out_and_missing_inventory_are_not_recommended(client, db_session, catalog):
    shop, shirts, _, headers, _ = catalog
    eligible = add_product(db_session, shop, shirts, "Đang bán", [("Đen", 100000, 1, True)])
    add_product(db_session, shop, shirts, "Ẩn sản phẩm", [("Đen", 100000, 1, True)], active=False)
    add_product(db_session, shop, shirts, "Ẩn variant", [("Đen", 100000, 1, False)])
    add_product(db_session, shop, shirts, "Hết hàng", [("Đen", 100000, 0, True)])
    add_product(db_session, shop, shirts, "Không có kho", [("Đen", 100000, None, True)])
    add_product(db_session, shop, shirts, "Không có variant", [])
    owner, _ = user_with_token(db_session, "recommend-hidden-owner@example.com", "SHOP_OWNER")
    hidden_shop = Shop(owner_id=owner.id, name="Shop bị khóa", is_active=False)
    db_session.add(hidden_shop)
    db_session.flush()
    add_product(db_session, hidden_shop, shirts, "Ẩn shop", [("Đen", 100000, 1, True)])
    db_session.commit()
    assert ids(client, headers) == [eligible.id]
    shop.is_active = False
    db_session.commit()
    assert ids(client, headers) == []


def test_color_and_price_matches_ignore_unavailable_variants(client, db_session, catalog):
    shop, shirts, _, headers, _ = catalog
    match = add_product(db_session, shop, shirts, "Khớp còn hàng", [("Đen", 100000, 1, True)])
    unavailable = add_product(
        db_session,
        shop,
        shirts,
        "Khớp nhưng không bán được",
        [("Đen", 100000, 0, True), ("Đen", 100000, 2, False), ("Đỏ", 300000, 2, True)],
        day=1,
    )
    db_session.commit()
    assert (
        client.put(
            "/users/me/preferences",
            headers=headers,
            json={"colors": ["Đen"], "max_price": 150000},
        ).status_code
        == 200
    )
    assert ids(client, headers) == [match.id, unavailable.id]
    matching_variant = db_session.scalar(
        select(ProductVariant).where(ProductVariant.product_id == match.id)
    )
    matching_variant.inventory.quantity = 0
    db_session.commit()
    assert ids(client, headers) == [unavailable.id]
    assert ids(client, headers) == [unavailable.id]


def test_each_buyer_uses_own_current_preferences(client, db_session, catalog):
    shop, shirts, shoes, headers, other_headers = catalog
    shirt = add_product(db_session, shop, shirts, "Áo", [("Đen", 100000, 1, True)])
    shoe = add_product(db_session, shop, shoes, "Giày", [("Đỏ", 100000, 1, True)], day=1)
    db_session.commit()
    assert (
        client.put(
            "/users/me/preferences", headers=headers, json={"category_ids": [shirts.id]}
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/users/me/preferences", headers=other_headers, json={"category_ids": [shoes.id]}
        ).status_code
        == 200
    )
    assert ids(client, headers) == [shirt.id, shoe.id]
    assert ids(client, other_headers) == [shoe.id, shirt.id]
    assert client.put("/users/me/preferences", headers=headers, json={}).status_code == 200
    assert ids(client, headers) == [shoe.id, shirt.id]


def test_color_and_price_are_independent_criteria(client, db_session, catalog):
    shop, shirts, _, headers, _ = catalog
    split = add_product(
        db_session,
        shop,
        shirts,
        "Khớp trên hai variant",
        [("Đen", 300000, 2, True), ("Đỏ", 100000, 1, True)],
    )
    single = add_product(
        db_session, shop, shirts, "Chỉ khớp màu", [("Đen", 300000, 1, True)], day=1
    )
    db_session.commit()
    assert (
        client.put(
            "/users/me/preferences", headers=headers, json={"colors": ["Đen"], "max_price": 100000}
        ).status_code
        == 200
    )
    assert ids(client, headers) == [split.id, single.id]


def test_preferences_with_no_matches_fall_back_to_newest(client, db_session, catalog):
    shop, shirts, shoes, headers, _ = catalog
    newer = add_product(db_session, shop, shirts, "Mới hơn", [("Đỏ", 100000, 1, True)], day=1)
    older = add_product(db_session, shop, shirts, "Cũ hơn", [("Đỏ", 100000, 1, True)])
    db_session.commit()
    assert (
        client.put(
            "/users/me/preferences", headers=headers, json={"category_ids": [shoes.id]}
        ).status_code
        == 200
    )
    assert ids(client, headers) == [newer.id, older.id]


def test_current_price_and_ratings_are_read_from_catalog(client, db_session, catalog):
    shop, shirts, _, headers, _ = catalog
    affordable = add_product(
        db_session, shop, shirts, "Trong ngân sách", [("Đen", 100000, 1, True)]
    )
    expensive = add_product(
        db_session, shop, shirts, "Ngoài ngân sách", [("Đỏ", 300000, 1, True)], day=1
    )
    buyer, _ = user_with_token(db_session, "recommend-review@example.com", "BUYER")
    variant = db_session.scalar(
        select(ProductVariant).where(ProductVariant.product_id == affordable.id)
    )
    order = Order(
        code="REC-REVIEW",
        buyer_id=buyer.id,
        shop_id=shop.id,
        payment_method="COD",
        shipping_address="Địa chỉ test",
        receiver_name="Buyer test",
        receiver_phone="0900000000",
        total_amount=200000,
    )
    db_session.add(order)
    db_session.flush()
    for rating in [4, 5]:
        item = OrderItem(
            order_id=order.id,
            variant_id=variant.id,
            product_name=affordable.name,
            size=variant.size,
            color=variant.color,
            unit_price=100000,
            quantity=1,
        )
        db_session.add(item)
        db_session.flush()
        db_session.add(
            Review(
                order_item_id=item.id, product_id=affordable.id, buyer_id=buyer.id, rating=rating
            )
        )
    db_session.commit()
    assert (
        client.put("/users/me/preferences", headers=headers, json={"max_price": 100000}).status_code
        == 200
    )
    result = client.get("/users/me/recommendations", headers=headers).json()
    assert [item["id"] for item in result] == [affordable.id, expensive.id]
    assert result[0] == {
        "id": affordable.id,
        "shop_id": shop.id,
        "shop_name": shop.name,
        "category_id": shirts.id,
        "name": affordable.name,
        "image_url": None,
        "base_price": 999999,
        "price_from": 100000,
        "rating_average": 4.5,
    }
    assert result[1]["rating_average"] is None
    variant.price = 400000
    db_session.commit()
    updated = client.get("/users/me/recommendations", headers=headers).json()
    assert [item["id"] for item in updated] == [expensive.id, affordable.id]
    assert updated[1]["price_from"] == 400000


@pytest.mark.parametrize("role", ["SHOP_OWNER", "ADMIN"])
def test_endpoint_requires_authenticated_active_buyer(client, db_session, role):
    user, headers = user_with_token(db_session, f"recommend-{role}@example.com", role)
    buyer, buyer_headers = user_with_token(
        db_session, f"recommend-locked-{role}@example.com", "BUYER"
    )
    buyer.is_active = False
    db_session.commit()
    assert client.get("/users/me/recommendations").status_code == 401
    assert client.get("/users/me/recommendations", headers=headers).status_code == 403
    assert client.get("/users/me/recommendations", headers=buyer_headers).status_code == 403
    user.role = "BUYER"
    db_session.commit()
    assert client.get("/users/me/recommendations", headers=headers).status_code == 200


@pytest.mark.parametrize("limit", [0, -1, 21, "bad"])
def test_invalid_limits_are_rejected(client, db_session, catalog, limit):
    _, _, _, headers, _ = catalog
    db_session.commit()
    assert (
        client.get(
            "/users/me/recommendations", headers=headers, params={"limit": limit}
        ).status_code
        == 422
    )
