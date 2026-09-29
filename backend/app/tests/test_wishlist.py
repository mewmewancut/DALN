from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.main import app
from app.models import Category, Inventory, Product, ProductVariant, Shop, WishlistItem
from app.tests.test_catalog import user_with_token


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def create_catalog(db_session: Session):
    buyer, buyer_headers = user_with_token(db_session, "wishlist-buyer@example.com", "BUYER")
    _, other_headers = user_with_token(db_session, "wishlist-other@example.com", "BUYER")
    owner, owner_headers = user_with_token(db_session, "wishlist-owner@example.com", "SHOP_OWNER")
    shop = Shop(owner_id=owner.id, name="Shop yêu thích")
    category = Category(name="Wishlist category")
    db_session.add_all([shop, category])
    db_session.flush()
    product = Product(
        shop_id=shop.id,
        category_id=category.id,
        name="Áo được yêu thích",
        image_url="https://example.com/wishlist.jpg",
        base_price=100000,
    )
    db_session.add(product)
    db_session.flush()
    variant = ProductVariant(
        product_id=product.id,
        size="M",
        color="Đen",
        price=120000,
        sku="wishlist-test-1",
    )
    db_session.add(variant)
    db_session.flush()
    db_session.add(Inventory(variant_id=variant.id, shop_id=shop.id, quantity=3))
    db_session.commit()
    return buyer, buyer_headers, other_headers, owner_headers, shop, product, variant


def test_buyer_adds_lists_and_removes_wishlist_idempotently(
    client: TestClient, db_session: Session
) -> None:
    buyer, headers, other_headers, _, _, product, _ = create_catalog(db_session)

    first = client.put(f"/wishlist/items/{product.id}", headers=headers)
    second = client.put(f"/wishlist/items/{product.id}", headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json() == {
        **first.json(),
        "product_id": product.id,
        "name": "Áo được yêu thích",
        "shop_name": "Shop yêu thích",
        "price_from": 120000,
        "rating_average": None,
        "is_available": True,
        "has_stock": True,
    }
    assert (
        db_session.scalar(
            select(func.count()).select_from(WishlistItem).where(WishlistItem.buyer_id == buyer.id)
        )
        == 1
    )
    assert client.get("/wishlist", headers=other_headers).json() == []

    assert client.delete(f"/wishlist/items/{product.id}", headers=headers).status_code == 204
    assert client.delete(f"/wishlist/items/{product.id}", headers=headers).status_code == 204
    assert client.get("/wishlist", headers=headers).json() == []


def test_hidden_product_stays_in_wishlist_but_cannot_be_added_again(
    client: TestClient, db_session: Session
) -> None:
    _, headers, _, _, shop, product, variant = create_catalog(db_session)
    assert client.put(f"/wishlist/items/{product.id}", headers=headers).status_code == 200

    product.is_active = False
    variant.inventory.quantity = 0
    db_session.commit()
    saved = client.get("/wishlist", headers=headers).json()
    assert len(saved) == 1
    assert saved[0]["is_available"] is False
    assert saved[0]["has_stock"] is False
    repeated = client.put(f"/wishlist/items/{product.id}", headers=headers)
    assert repeated.status_code == 200
    assert repeated.json()["is_available"] is False

    product.is_active = True
    shop.is_active = False
    db_session.commit()
    assert client.get("/wishlist", headers=headers).json()[0]["is_available"] is False


def test_wishlist_requires_buyer_and_rejects_missing_product(
    client: TestClient, db_session: Session
) -> None:
    _, headers, _, owner_headers, _, product, _ = create_catalog(db_session)
    assert client.get("/wishlist").status_code == 401
    assert client.get("/wishlist", headers=owner_headers).status_code == 403
    assert client.put(f"/wishlist/items/{product.id}", headers=owner_headers).status_code == 403
    assert client.delete(f"/wishlist/items/{product.id}", headers=owner_headers).status_code == 403
    assert client.put("/wishlist/items/999999999", headers=headers).status_code == 404
