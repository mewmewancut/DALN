from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.main import app
from app.models import (
    Category,
    Product,
    ProductVariant,
    Shop,
    UserPreference,
    UserPreferredCategory,
    UserPreferredColor,
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


def create_preference_catalog(db_session: Session):
    buyer, headers = user_with_token(db_session, "preference-buyer@example.com", "BUYER")
    _, other_headers = user_with_token(db_session, "preference-other@example.com", "BUYER")
    owner, owner_headers = user_with_token(db_session, "preference-owner@example.com", "SHOP_OWNER")
    shop = Shop(owner_id=owner.id, name="Shop sở thích")
    shirts = Category(name="Áo sở thích")
    shoes = Category(name="Giày sở thích")
    db_session.add_all([shop, shirts, shoes])
    db_session.flush()
    product = Product(
        shop_id=shop.id,
        category_id=shirts.id,
        name="Áo nhiều màu",
        base_price=100000,
    )
    db_session.add(product)
    db_session.flush()
    variants = [
        ProductVariant(
            product_id=product.id,
            size="M",
            color="Đen",
            price=100000,
            sku="preference-black",
        ),
        ProductVariant(
            product_id=product.id,
            size="L",
            color="Trắng",
            price=120000,
            sku="preference-white",
            is_active=False,
        ),
    ]
    db_session.add_all(variants)
    db_session.commit()
    return buyer, headers, other_headers, owner_headers, shirts, shoes, variants


def test_buyer_reads_empty_options_and_replaces_preferences(
    client: TestClient, db_session: Session
) -> None:
    buyer, headers, other_headers, _, shirts, shoes, _ = create_preference_catalog(db_session)

    assert client.get("/users/me/preferences", headers=headers).json() == {
        "category_ids": [],
        "colors": [],
        "min_price": None,
        "max_price": None,
    }
    options = client.get("/users/me/preferences/options", headers=headers)
    assert options.status_code == 200
    assert options.json()["categories"] == [
        {"id": shirts.id, "name": shirts.name},
        {"id": shoes.id, "name": shoes.name},
    ]
    assert options.json()["colors"] == ["Đen"]

    saved = client.put(
        "/users/me/preferences",
        headers=headers,
        json={
            "category_ids": [shoes.id, shirts.id, shirts.id],
            "colors": [" Đen ", "Đen"],
            "min_price": 100000,
            "max_price": 500000,
        },
    )
    assert saved.status_code == 200
    assert saved.json() == {
        "category_ids": [shirts.id, shoes.id],
        "colors": ["Đen"],
        "min_price": 100000,
        "max_price": 500000,
    }
    assert client.get("/users/me/preferences", headers=other_headers).json()["colors"] == []
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(UserPreference)
            .where(UserPreference.buyer_id == buyer.id)
        )
        == 1
    )
    assert db_session.scalar(select(func.count()).select_from(UserPreferredCategory)) == 2
    assert db_session.scalar(select(func.count()).select_from(UserPreferredColor)) == 1

    replaced = client.put(
        "/users/me/preferences",
        headers=headers,
        json={"category_ids": [shoes.id], "colors": [], "min_price": None, "max_price": 300000},
    )
    assert replaced.status_code == 200
    assert replaced.json()["category_ids"] == [shoes.id]
    assert replaced.json()["colors"] == []
    assert replaced.json()["min_price"] is None
    assert db_session.scalar(select(func.count()).select_from(UserPreferredCategory)) == 1
    assert db_session.scalar(select(func.count()).select_from(UserPreferredColor)) == 0


def test_saved_color_remains_an_option_after_catalog_hides_it(
    client: TestClient, db_session: Session
) -> None:
    _, headers, _, _, shirts, _, variants = create_preference_catalog(db_session)
    assert (
        client.put(
            "/users/me/preferences",
            headers=headers,
            json={"category_ids": [shirts.id], "colors": ["Đen"]},
        ).status_code
        == 200
    )
    variants[0].is_active = False
    db_session.commit()

    options = client.get("/users/me/preferences/options", headers=headers).json()
    assert options["colors"] == ["Đen"]
    assert (
        client.put(
            "/users/me/preferences",
            headers=headers,
            json={"category_ids": [shirts.id], "colors": ["Đen"]},
        ).status_code
        == 200
    )


def test_preferences_reject_invalid_values_and_preserve_existing_data(
    client: TestClient, db_session: Session
) -> None:
    _, headers, _, _, shirts, _, _ = create_preference_catalog(db_session)
    original = client.put(
        "/users/me/preferences",
        headers=headers,
        json={"category_ids": [shirts.id], "colors": ["Đen"], "max_price": 200000},
    ).json()

    assert (
        client.put(
            "/users/me/preferences",
            headers=headers,
            json={"category_ids": [999999999], "colors": ["Đen"]},
        ).status_code
        == 400
    )
    assert (
        client.put(
            "/users/me/preferences",
            headers=headers,
            json={"category_ids": [shirts.id], "colors": ["Không có"]},
        ).status_code
        == 400
    )
    assert (
        client.put(
            "/users/me/preferences",
            headers=headers,
            json={"min_price": 300000, "max_price": 200000},
        ).status_code
        == 422
    )
    assert client.get("/users/me/preferences", headers=headers).json() == original


def test_preferences_roll_back_the_whole_replacement_on_database_failure(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    _, headers, _, _, shirts, shoes, _ = create_preference_catalog(db_session)
    original = client.put(
        "/users/me/preferences",
        headers=headers,
        json={
            "category_ids": [shirts.id],
            "colors": ["Đen"],
            "min_price": 100000,
            "max_price": 200000,
        },
    ).json()

    def fail_commit() -> None:
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="simulated commit failure"):
        client.put(
            "/users/me/preferences",
            headers=headers,
            json={"category_ids": [shoes.id], "colors": [], "max_price": 900000},
        )
    assert client.get("/users/me/preferences", headers=headers).json() == original


def test_preferences_require_buyer_role(client: TestClient, db_session: Session) -> None:
    _, headers, _, owner_headers, _, _, _ = create_preference_catalog(db_session)
    for method, path, body in [
        ("get", "/users/me/preferences", None),
        ("get", "/users/me/preferences/options", None),
        ("put", "/users/me/preferences", {"category_ids": [], "colors": []}),
    ]:
        assert client.request(method, path, json=body).status_code == 401
        assert client.request(method, path, headers=owner_headers, json=body).status_code == 403
    assert client.get("/users/me/preferences", headers=headers).status_code == 200
