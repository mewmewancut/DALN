from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.deps import get_db
from app.main import app
from app.models import Shop
from app.tests.test_catalog import user_with_token


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def owner_context(db_session: Session, email: str) -> dict:
    owner, headers = user_with_token(db_session, email, "SHOP_OWNER")
    shop = Shop(owner_id=owner.id, name="Supplier Shop")
    db_session.add(shop)
    db_session.commit()
    return {"owner": owner, "headers": headers, "shop": shop}


def test_create_and_list_suppliers_scoped_to_shop(db_session: Session, client: TestClient) -> None:
    ctx = owner_context(db_session, "supplier-owner-1@example.com")
    other = owner_context(db_session, "supplier-owner-2@example.com")

    created = client.post(
        "/shop/suppliers",
        json={"name": "NCC Vải Việt", "phone": "0900000001", "address": "Q1, TP.HCM"},
        headers=ctx["headers"],
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "NCC Vải Việt"
    assert body["is_active"] is True

    client.post("/shop/suppliers", json={"name": "NCC của shop khác"}, headers=other["headers"])

    listed = client.get("/shop/suppliers", headers=ctx["headers"])
    assert listed.status_code == 200
    names = [s["name"] for s in listed.json()]
    assert names == ["NCC Vải Việt"]

    assert client.get("/shop/suppliers").status_code == 401
    _, buyer_headers = user_with_token(db_session, "supplier-buyer@example.com", "BUYER")
    db_session.commit()
    assert client.get("/shop/suppliers", headers=buyer_headers).status_code == 403


def test_update_supplier_validates_ownership_and_required_name(
    db_session: Session, client: TestClient
) -> None:
    ctx = owner_context(db_session, "supplier-owner-3@example.com")
    other = owner_context(db_session, "supplier-owner-4@example.com")
    supplier_id = client.post(
        "/shop/suppliers", json={"name": "NCC A"}, headers=ctx["headers"]
    ).json()["id"]

    updated = client.put(
        f"/shop/suppliers/{supplier_id}",
        json={"phone": "0911111111"},
        headers=ctx["headers"],
    )
    assert updated.status_code == 200
    assert updated.json()["phone"] == "0911111111"
    assert updated.json()["name"] == "NCC A"

    assert (
        client.put(
            f"/shop/suppliers/{supplier_id}",
            json={"name": None},
            headers=ctx["headers"],
        ).status_code
        == 400
    )
    assert (
        client.put(
            f"/shop/suppliers/{supplier_id}",
            json={"name": "Chiếm NCC"},
            headers=other["headers"],
        ).status_code
        == 403
    )
    assert (
        client.put(
            "/shop/suppliers/999999999",
            json={"name": "Không tồn tại"},
            headers=ctx["headers"],
        ).status_code
        == 404
    )


def test_delete_supplier_is_soft_delete(db_session: Session, client: TestClient) -> None:
    ctx = owner_context(db_session, "supplier-owner-5@example.com")
    other = owner_context(db_session, "supplier-owner-6@example.com")
    supplier_id = client.post(
        "/shop/suppliers", json={"name": "NCC B"}, headers=ctx["headers"]
    ).json()["id"]

    assert (
        client.delete(f"/shop/suppliers/{supplier_id}", headers=other["headers"]).status_code == 403
    )
    deleted = client.delete(f"/shop/suppliers/{supplier_id}", headers=ctx["headers"])
    assert deleted.status_code == 204

    listed = client.get("/shop/suppliers", headers=ctx["headers"]).json()
    assert listed[0]["id"] == supplier_id
    assert listed[0]["is_active"] is False
