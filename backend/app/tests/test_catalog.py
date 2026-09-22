from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
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
    User,
)


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def user_with_token(db: Session, email: str, role: str) -> tuple[User, dict[str, str]]:
    user = User(
        email=email,
        password_hash="unused",
        full_name="Test User",
        role=role,
    )
    db.add(user)
    db.flush()
    token = jwt.encode(
        {
            "sub": str(user.id),
            "role": role,
            "shop_id": 999999,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    return user, {"Authorization": f"Bearer {token}"}


def product_payload(category_id: int, name: str = "Áo thun") -> dict:
    return {
        "category_id": category_id,
        "name": name,
        "description": "Mô tả",
        "image_url": "https://example.com/shirt.jpg",
        "base_price": 200000,
        "variants": [
            {"size": "M", "color": "Đen", "price": 220000, "initial_quantity": 7},
            {"size": "L", "color": "Đen", "price": 240000, "initial_quantity": 3},
        ],
    }


def test_shop_creation_and_update_use_authenticated_owner(
    db_session: Session, client: TestClient
) -> None:
    owner, owner_headers = user_with_token(db_session, "owner-c2@example.com", "SHOP_OWNER")
    _, buyer_headers = user_with_token(db_session, "buyer-c2@example.com", "BUYER")
    assert (
        client.post("/shops", json={"name": "Sai quyền"}, headers=buyer_headers).status_code == 403
    )
    assert client.post("/shops", json={"name": "Thiếu token"}).status_code == 401
    assert (
        client.post(
            "/shops", json={"name": "Sai owner", "owner_id": 123}, headers=owner_headers
        ).status_code
        == 422
    )

    created = client.post(
        "/shops", json={"name": "Shop A", "description": "Mô tả"}, headers=owner_headers
    )
    assert created.status_code == 201
    assert created.json()["owner_id"] == owner.id
    assert (
        client.post("/shops", json={"name": "Shop thứ hai"}, headers=owner_headers).status_code
        == 400
    )
    updated = client.put(
        "/shops/me", json={"name": "Shop mới", "description": None}, headers=owner_headers
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Shop mới"
    assert db_session.get(Shop, created.json()["id"]).description is None


def test_product_creation_writes_variants_and_inventory_together(
    db_session: Session, client: TestClient
) -> None:
    _, owner_headers = user_with_token(db_session, "owner-create@example.com", "SHOP_OWNER")
    shop_id = client.post("/shops", json={"name": "Shop A"}, headers=owner_headers).json()["id"]
    category = Category(name="Áo")
    db_session.add(category)
    db_session.flush()

    assert (
        client.post(
            "/products",
            json={**product_payload(category.id), "shop_id": 999},
            headers=owner_headers,
        ).status_code
        == 422
    )
    response = client.post("/products", json=product_payload(category.id), headers=owner_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["shop_id"] == shop_id
    assert body["price_from"] == 220000
    assert [(v["size"], v["quantity"]) for v in body["variants"]] == [("M", 7), ("L", 3)]
    assert body["variants"][0]["sku"] == f"P{body['id']}-M-Đen"
    assert (
        db_session.scalar(
            select(func.count()).select_from(Inventory).where(Inventory.shop_id == shop_id)
        )
        == 2
    )
    assert client.get(f"/products/{body['id']}").status_code == 200


def test_variant_sku_is_collision_safe_when_size_or_color_contains_hyphen(
    db_session: Session, client: TestClient
) -> None:
    _, headers = user_with_token(db_session, "owner-sku@example.com", "SHOP_OWNER")
    client.post("/shops", json={"name": "Shop SKU"}, headers=headers)
    category = Category(name="Phụ kiện")
    db_session.add(category)
    db_session.flush()
    payload = product_payload(category.id, "Sản phẩm SKU")
    payload["variants"] = [
        {"size": "S-M", "color": "Red", "price": 100000, "initial_quantity": 1},
        {"size": "S", "color": "M-Red", "price": 100000, "initial_quantity": 1},
    ]
    response = client.post("/products", json=payload, headers=headers)
    assert response.status_code == 201
    skus = [variant["sku"] for variant in response.json()["variants"]]
    assert len(skus) == len(set(skus))


def test_duplicate_variant_rolls_back_the_whole_product(
    db_session: Session, client: TestClient
) -> None:
    _, headers = user_with_token(db_session, "owner-rollback@example.com", "SHOP_OWNER")
    client.post("/shops", json={"name": "Shop A"}, headers=headers)
    category = Category(name="Quần")
    db_session.add(category)
    db_session.flush()
    payload = product_payload(category.id)
    payload["variants"][1]["size"] = "M"
    response = client.post("/products", json=payload, headers=headers)
    assert response.status_code == 409
    assert db_session.scalar(select(func.count()).select_from(Product)) == 0
    assert db_session.scalar(select(func.count()).select_from(ProductVariant)) == 0
    assert db_session.scalar(select(func.count()).select_from(Inventory)) == 0


def test_owner_isolation_variant_updates_and_soft_delete(
    db_session: Session, client: TestClient
) -> None:
    _, owner_a = user_with_token(db_session, "owner-a@example.com", "SHOP_OWNER")
    _, owner_b = user_with_token(db_session, "owner-b@example.com", "SHOP_OWNER")
    client.post("/shops", json={"name": "Shop A"}, headers=owner_a)
    client.post("/shops", json={"name": "Shop B"}, headers=owner_b)
    category = Category(name="Váy")
    db_session.add(category)
    db_session.flush()
    product = client.post("/products", json=product_payload(category.id), headers=owner_b).json()
    product_id = product["id"]
    variant_id = product["variants"][0]["id"]
    assert (
        client.put(f"/products/{product_id}", json={"name": "Chiếm"}, headers=owner_a).status_code
        == 403
    )
    assert client.delete(f"/products/{product_id}", headers=owner_a).status_code == 403
    assert (
        client.post(
            f"/products/{product_id}/variants",
            json={"size": "S", "color": "Đỏ", "price": 100000, "initial_quantity": 1},
            headers=owner_a,
        ).status_code
        == 403
    )
    assert (
        client.put(f"/variants/{variant_id}", json={"price": 1}, headers=owner_a).status_code == 403
    )
    assert (
        client.put(f"/products/{product_id}", json={"name": "Váy mới"}, headers=owner_b).json()[
            "name"
        ]
        == "Váy mới"
    )

    duplicate = client.post(
        f"/products/{product_id}/variants",
        json={"size": "M", "color": "Đen", "price": 100000, "initial_quantity": 1},
        headers=owner_b,
    )
    assert duplicate.status_code == 409
    new_variant = client.post(
        f"/products/{product_id}/variants",
        json={"size": "S", "color": "Đỏ", "price": 180000, "initial_quantity": 2},
        headers=owner_b,
    )
    assert new_variant.status_code == 201
    changed = client.put(
        f"/variants/{new_variant.json()['id']}",
        json={"price": 190000, "is_active": False},
        headers=owner_b,
    )
    assert changed.status_code == 200
    assert changed.json()["quantity"] == 2
    assert changed.json()["is_active"] is False
    assert len(client.get(f"/products/{product_id}").json()["variants"]) == 2

    assert client.delete(f"/products/{product_id}", headers=owner_b).status_code == 204
    assert db_session.get(Product, product_id).is_active is False
    assert client.get(f"/products/{product_id}").status_code == 404
    assert client.get("/products").json()["total"] == 0
    assert (
        client.put(f"/products/{product_id}", json={"is_active": True}, headers=owner_b).status_code
        == 200
    )
    assert client.get(f"/products/{product_id}").status_code == 200


def test_public_search_filters_sort_pagination_and_rating(
    db_session: Session, client: TestClient
) -> None:
    buyer, _ = user_with_token(db_session, "reviewer@example.com", "BUYER")
    _, owner_a = user_with_token(db_session, "owner-search-a@example.com", "SHOP_OWNER")
    _, owner_b = user_with_token(db_session, "owner-search-b@example.com", "SHOP_OWNER")
    shop_a = client.post("/shops", json={"name": "Shop A"}, headers=owner_a).json()["id"]
    shop_b = client.post("/shops", json={"name": "Shop B"}, headers=owner_b).json()["id"]
    shirt = Category(name="Áo")
    pants = Category(name="Quần")
    db_session.add_all([shirt, pants])
    db_session.flush()
    cheap = product_payload(shirt.id, "Áo giá tốt")
    cheap["variants"][0]["price"] = 100000
    cheap["variants"][1]["price"] = 300000
    expensive = product_payload(pants.id, "Quần cao cấp")
    expensive["variants"][0]["price"] = 400000
    expensive["variants"][1]["price"] = 500000
    cheap_product = client.post("/products", json=cheap, headers=owner_a).json()
    expensive_product = client.post("/products", json=expensive, headers=owner_b).json()

    order = Order(
        code="CATALOG-REVIEW-1",
        buyer_id=buyer.id,
        shop_id=shop_a,
        shipping_address="Địa chỉ",
        receiver_name="Người mua",
        receiver_phone="0900000000",
        payment_method="COD",
        total_amount=100000,
    )
    db_session.add(order)
    db_session.flush()
    item = OrderItem(
        order_id=order.id,
        variant_id=cheap_product["variants"][0]["id"],
        product_name=cheap_product["name"],
        size="M",
        color="Đen",
        unit_price=100000,
        quantity=1,
    )
    db_session.add(item)
    db_session.flush()
    db_session.add(
        Review(order_item_id=item.id, product_id=cheap_product["id"], buyer_id=buyer.id, rating=4)
    )
    db_session.flush()

    assert [row["name"] for row in client.get("/categories").json()] == ["Áo", "Quần"]
    assert client.get("/products", params={"keyword": "ÁO"}).json()["total"] == 1
    assert (
        client.get("/products", params={"category_id": pants.id}).json()["items"][0]["id"]
        == expensive_product["id"]
    )
    assert client.get("/products", params={"shop_id": shop_a}).json()["total"] == 1
    assert client.get("/products", params={"min_price": 200000}).json()["total"] == 1
    assert client.get("/products", params={"max_price": 200000}).json()["total"] == 1
    assert [
        row["id"] for row in client.get("/products", params={"sort": "price_asc"}).json()["items"]
    ] == [cheap_product["id"], expensive_product["id"]]
    paged = client.get("/products", params={"sort": "price_desc", "page_size": 1, "page": 2}).json()
    assert paged["total"] == 2
    assert paged["items"][0]["id"] == cheap_product["id"]
    assert client.get(f"/products/{cheap_product['id']}").json()["rating_average"] == 4.0
    assert client.get("/products", params={"sort": "bad"}).status_code == 422

    hidden = client.put(
        f"/variants/{cheap_product['variants'][0]['id']}",
        json={"is_active": False},
        headers=owner_a,
    )
    assert hidden.status_code == 200
    assert client.get(f"/products/{cheap_product['id']}").json()["price_from"] == 300000
    assert client.get("/products", params={"max_price": 200000}).json()["total"] == 0

    db_session.get(Shop, shop_b).is_active = False
    db_session.flush()
    assert client.get("/products").json()["total"] == 1
    assert client.get(f"/products/{expensive_product['id']}").status_code == 404
