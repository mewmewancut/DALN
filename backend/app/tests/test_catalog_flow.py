from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.deps import get_db
from app.main import app
from app.models import Category, ProductVariant


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_owner_can_publish_product_for_public_catalog(
    db_session: Session, client: TestClient
) -> None:
    category = Category(name="Áo")
    db_session.add(category)
    db_session.flush()

    owner_credentials = {"email": "flow-owner@example.com", "password": "Secret@123"}
    registered = client.post(
        "/auth/register",
        json={
            **owner_credentials,
            "full_name": "Chủ shop",
            "role": "SHOP_OWNER",
        },
    )
    assert registered.status_code == 201
    first_login = client.post("/auth/login", json=owner_credentials)
    assert first_login.status_code == 200
    assert first_login.json()["shop_id"] is None
    owner_headers = {
        "Authorization": f"Bearer {first_login.json()['access_token']}"
    }

    created_shop = client.post(
        "/shops", json={"name": "Shop luồng mua"}, headers=owner_headers
    )
    assert created_shop.status_code == 201
    shop_id = created_shop.json()["id"]
    second_login = client.post("/auth/login", json=owner_credentials)
    assert second_login.json()["shop_id"] == shop_id

    created_product = client.post(
        "/products",
        headers=owner_headers,
        json={
            "category_id": category.id,
            "name": "Áo sơ mi xanh",
            "base_price": 210000,
            "variants": [
                {"size": "M", "color": "Xanh", "price": 215000, "initial_quantity": 4},
                {"size": "L", "color": "Xanh", "price": 225000, "initial_quantity": 2},
            ],
        },
    )
    assert created_product.status_code == 201
    product_id = created_product.json()["id"]
    variant_id = created_product.json()["variants"][0]["id"]
    inventory = db_session.get(ProductVariant, variant_id).inventory
    assert inventory.shop_id == shop_id
    assert inventory.quantity == 4

    listing = client.get("/products", params={"keyword": "sơ mi", "shop_id": shop_id})
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["price_from"] == 215000
    detail = client.get(f"/products/{product_id}")
    assert detail.status_code == 200
    assert detail.json()["shop_name"] == "Shop luồng mua"
    assert [variant["quantity"] for variant in detail.json()["variants"]] == [4, 2]

    buyer = client.post(
        "/auth/register",
        json={
            "email": "flow-buyer@example.com",
            "password": "Secret@123",
            "full_name": "Người mua",
            "role": "BUYER",
        },
    )
    assert buyer.status_code == 201
    buyer_login = client.post(
        "/auth/login",
        json={"email": "flow-buyer@example.com", "password": "Secret@123"},
    )
    buyer_headers = {
        "Authorization": f"Bearer {buyer_login.json()['access_token']}"
    }
    assert client.put(
        f"/products/{product_id}", json={"name": "Sai quyền"}, headers=buyer_headers
    ).status_code == 403

    assert client.delete(f"/products/{product_id}", headers=owner_headers).status_code == 204
    assert client.get(f"/products/{product_id}").status_code == 404
    assert client.get("/products").json()["total"] == 0
