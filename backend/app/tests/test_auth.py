from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_current_shop, get_db, require_role
from app.main import app
from app.models.shop import Shop
from app.models.user import User


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def add_user(
    db_session: Session,
    *,
    email: str,
    role: str = "BUYER",
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        password_hash=bcrypt.hashpw(b"Secret@123", bcrypt.gensalt()).decode(),
        full_name="Test User",
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_register_returns_public_user_and_rejects_duplicate_and_admin(
    db_session: Session,
    client: TestClient,
) -> None:
    payload = {
        "email": "new@example.com",
        "password": "Secret@123",
        "full_name": "New Buyer",
        "role": "BUYER",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "email": payload["email"],
        "full_name": payload["full_name"],
        "role": "BUYER",
        "is_active": True,
    }
    assert "password_hash" not in response.text
    assert client.post("/auth/register", json=payload).status_code == 400
    assert (
        client.post(
            "/auth/register", json={**payload, "email": "admin@example.com", "role": "ADMIN"}
        ).status_code
        == 400
    )
    assert db_session.get(User, response.json()["id"]) is not None


def test_login_token_me_and_invalid_credentials(
    db_session: Session,
    client: TestClient,
) -> None:
    owner = add_user(db_session, email="owner@example.com", role="SHOP_OWNER")
    shop = Shop(owner_id=owner.id, name="Test Shop")
    db_session.add(shop)
    db_session.flush()

    assert (
        client.post("/auth/login", json={"email": owner.email, "password": "wrong"}).status_code
        == 401
    )
    response = client.post("/auth/login", json={"email": owner.email, "password": "Secret@123"})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "SHOP_OWNER"
    assert body["shop_id"] == shop.id
    payload = jwt.decode(body["access_token"], get_settings().jwt_secret, algorithms=["HS256"])
    assert payload["sub"] == str(owner.id)
    assert payload["role"] == "SHOP_OWNER"
    assert payload["shop_id"] == shop.id
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == owner.email
    assert "password_hash" not in me.text


def test_locked_user_and_bad_tokens(db_session: Session, client: TestClient) -> None:
    user = add_user(db_session, email="locked@example.com", is_active=False)
    assert (
        client.post("/auth/login", json={"email": user.email, "password": "Secret@123"}).status_code
        == 403
    )
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    expired = jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "shop_id": None,
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    active_token = jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "shop_id": None,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    assert (
        client.get("/auth/me", headers={"Authorization": f"Bearer {active_token}"}).status_code
        == 403
    )


def test_register_and_login_are_case_insensitive_for_email(
    db_session: Session,
    client: TestClient,
) -> None:
    payload = {
        "email": "Case@Example.com",
        "password": "Secret@123",
        "full_name": "Case User",
        "role": "BUYER",
    }
    assert client.post("/auth/register", json=payload).status_code == 201
    assert (
        client.post("/auth/register", json={**payload, "email": "case@example.com"}).status_code
        == 400
    )
    response = client.post(
        "/auth/login", json={"email": "case@example.com", "password": "Secret@123"}
    )
    assert response.status_code == 200


def test_shared_role_and_shop_dependencies(db_session: Session) -> None:
    buyer = add_user(db_session, email="buyer@example.com")
    owner = add_user(db_session, email="owner2@example.com", role="SHOP_OWNER")
    shop = Shop(owner_id=owner.id, name="Owner Shop")
    db_session.add(shop)
    db_session.flush()

    protected_app = FastAPI()
    protected_app.dependency_overrides[get_db] = lambda: db_session

    @protected_app.get("/shop")
    def shop_endpoint(current_shop: Annotated[Shop, Depends(get_current_shop)]) -> int:
        return current_shop.id

    @protected_app.get("/admin")
    def admin_endpoint(user: Annotated[User, Depends(require_role("ADMIN"))]) -> int:
        return user.id

    def token_for(user: User) -> str:
        return jwt.encode(
            {
                "sub": str(user.id),
                "role": user.role,
                "shop_id": 999999,
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            get_settings().jwt_secret,
            algorithm="HS256",
        )

    with TestClient(protected_app) as client:
        assert (
            client.get("/shop", headers={"Authorization": f"Bearer {token_for(buyer)}"}).status_code
            == 403
        )
        assert (
            client.get(
                "/admin", headers={"Authorization": f"Bearer {token_for(owner)}"}
            ).status_code
            == 403
        )
        response = client.get("/shop", headers={"Authorization": f"Bearer {token_for(owner)}"})
        assert response.status_code == 200
        assert response.json() == shop.id
        db_session.delete(shop)
        db_session.flush()
        assert (
            client.get("/shop", headers={"Authorization": f"Bearer {token_for(owner)}"}).status_code
            == 403
        )
