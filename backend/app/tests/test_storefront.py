import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Inventory, Product, ProductVariant, Shop
from app.tests.test_catalog import client as client
from app.tests.test_catalog import user_with_token
from app.tests.test_orders import create_order


def seed_shop(db: Session, suffix: str, *, description: str | None = None) -> Shop:
    owner, _ = user_with_token(db, f"storefront-{suffix}@example.com", "SHOP_OWNER")
    shop = Shop(owner_id=owner.id, name=f"Shop {suffix}", description=description)
    db.add(shop)
    db.commit()
    return shop


@pytest.mark.parametrize("role", [None, "BUYER", "SHOP_OWNER", "ADMIN"])
def test_public_shop_exposes_only_public_fields_without_writes(
    db_session: Session, client: TestClient, role: str | None
) -> None:
    shop = seed_shop(db_session, "public", description="Thời trang Việt\nDòng giới thiệu thứ hai")
    headers = {}
    if role:
        _, headers = user_with_token(db_session, f"visitor-{role}@example.com", role)
        db_session.commit()
    before = db_session.scalar(select(func.count()).select_from(Shop))
    response = client.get(f"/shops/{shop.id}", headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "id": shop.id,
        "name": shop.name,
        "description": shop.description,
        "created_at": shop.created_at.isoformat().replace("+00:00", "Z"),
    }
    assert db_session.scalar(select(func.count()).select_from(Shop)) == before
    assert not db_session.new and not db_session.dirty


def test_empty_shop_null_description_and_latest_profile(db_session: Session, client: TestClient):
    shop = seed_shop(db_session, "empty")
    assert client.get(f"/shops/{shop.id}").json()["description"] is None
    shop.name = "Tên shop mới"
    shop.description = "Giới thiệu mới"
    db_session.commit()
    body = client.get(f"/shops/{shop.id}").json()
    assert body["name"] == "Tên shop mới"
    assert body["description"] == "Giới thiệu mới"
    assert client.get("/products", params={"shop_id": shop.id}).json()["total"] == 0


def test_inactive_and_missing_shop_return_same_404(db_session: Session, client: TestClient):
    shop = seed_shop(db_session, "hidden")
    shop.is_active = False
    db_session.commit()
    hidden = client.get(f"/shops/{shop.id}")
    missing = client.get("/shops/999999999")
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()


@pytest.mark.parametrize("shop_id", ["0", "-1", "abc", "1.5"])
def test_invalid_public_shop_id(client: TestClient, shop_id: str):
    assert client.get(f"/shops/{shop_id}").status_code == 422


def test_storefront_catalog_is_scoped_filtered_and_uses_active_variant_prices(
    db_session: Session, client: TestClient
):
    shop = seed_shop(db_session, "catalog")
    other = seed_shop(db_session, "other")
    category = Category(name="Storefront Áo")
    second_category = Category(name="Storefront Quần")
    db_session.add_all([category, second_category])
    db_session.flush()

    products = []
    for index, (name, price, category_id, shop_id, active) in enumerate(
        [
            ("Áo cotton", 220000, category.id, shop.id, True),
            ("Áo linen", 180000, category.id, shop.id, True),
            ("Quần jean", 300000, second_category.id, shop.id, True),
            ("Áo ẩn", 100000, category.id, shop.id, False),
            ("Áo shop khác", 150000, category.id, other.id, True),
        ]
    ):
        product = Product(
            name=name,
            shop_id=shop_id,
            category_id=category_id,
            base_price=1,
            image_url="https://example.com/test.jpg",
            is_active=active,
        )
        db_session.add(product)
        db_session.flush()
        variant = ProductVariant(
            product_id=product.id, size="M", color="Đen", price=price, sku=f"storefront-{index}"
        )
        hidden_variant = ProductVariant(
            product_id=product.id,
            size="L",
            color="Đen",
            price=10,
            sku=f"storefront-hidden-{index}",
            is_active=False,
        )
        db_session.add_all([variant, hidden_variant])
        db_session.flush()
        db_session.add(Inventory(variant_id=variant.id, shop_id=shop_id, quantity=3))
        products.append(product)
    db_session.commit()

    params = {
        "shop_id": shop.id,
        "keyword": "ÁO",
        "category_id": category.id,
        "min_price": 170000,
        "max_price": 250000,
        "sort": "price_asc",
        "page_size": 1,
    }
    first = client.get("/products", params=params).json()
    second = client.get("/products", params={**params, "page": 2}).json()
    assert first["total"] == second["total"] == 2
    assert first["items"][0]["id"] == products[1].id
    assert second["items"][0]["id"] == products[0].id
    assert first["items"][0]["price_from"] == 180000
    assert first["items"][0]["shop_id"] == second["items"][0]["shop_id"] == shop.id
    assert client.get("/products", params={"shop_id": shop.id}).json()["total"] == 3
    assert client.get("/products", params={**params, "min_price": 260000}).json()["total"] == 0
    shop.is_active = False
    db_session.commit()
    assert client.get("/products", params={"shop_id": shop.id}).json()["total"] == 0
    assert client.get(f"/products/{products[0].id}").status_code == 404


def test_locked_shop_keeps_buyer_order_snapshot_and_permissions(
    db_session: Session, client: TestClient
):
    context = create_order(client, db_session)
    order_id = context["order"]["id"]
    before = client.get(f"/orders/{order_id}", headers=context["headers"]).json()
    context["shop"].is_active = False
    context["product"].name = "Tên hiện tại đã đổi"
    context["variant"].price = 999000
    db_session.commit()
    assert client.get(f"/shops/{context['shop'].id}").status_code == 404
    after = client.get(f"/orders/{order_id}", headers=context["headers"])
    assert after.status_code == 200
    assert after.json() == before
    assert (
        client.get("/orders/my", headers=context["headers"]).json()["items"][0]["shop_id"]
        == context["shop"].id
    )
    _, other_headers = user_with_token(db_session, "storefront-other-buyer@example.com", "BUYER")
    db_session.commit()
    assert client.get(f"/orders/{order_id}", headers=other_headers).status_code == 403
