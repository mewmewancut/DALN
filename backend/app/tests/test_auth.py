from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_current_shop, get_db, require_role
from app.main import app
from app.models.auth import AuthToken
from app.models.shop import Shop
from app.models.user import User
from app.services.email_service import EmailDeliveryError, get_email_sender


@pytest.fixture
def client(db_session: Session, fake_email_sender) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_email_sender] = lambda: fake_email_sender
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
    verified: bool = True,
) -> User:
    user = User(
        email=email,
        password_hash=bcrypt.hashpw(b"Secret@123", bcrypt.gensalt()).decode(),
        full_name="Test User",
        role=role,
        is_active=is_active,
        email_verified_at=datetime.now(timezone.utc) if verified else None,
    )
    db_session.add(user)
    db_session.flush()
    return user


def registration_payload(email: str = "new@example.com") -> dict[str, str]:
    return {
        "email": email,
        "password": "Secret@123",
        "full_name": "New Buyer",
        "role": "BUYER",
    }


def test_register_hashes_password_sends_verification_and_rejects_invalid_registration(
    db_session: Session,
    client: TestClient,
    fake_email_sender,
) -> None:
    payload = registration_payload()
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "email": payload["email"],
        "full_name": payload["full_name"],
        "role": "BUYER",
        "is_active": True,
        "email_verified_at": None,
    }
    user = db_session.get(User, response.json()["id"])
    assert user is not None
    assert user.password_hash != payload["password"]
    assert bcrypt.checkpw(payload["password"].encode(), user.password_hash.encode())
    assert fake_email_sender.verifications[0][0] == payload["email"]
    assert "password_hash" not in response.text

    assert client.post("/auth/register", json=payload).status_code == 400
    admin = {**payload, "email": "admin@example.com", "role": "ADMIN"}
    assert client.post("/auth/register", json=admin).status_code == 400


def test_user_must_verify_email_before_login_and_token_is_single_use(
    client: TestClient,
    fake_email_sender,
) -> None:
    credentials = {"email": "verify@example.com", "password": "Secret@123"}
    assert (
        client.post(
            "/auth/register",
            json={**credentials, "full_name": "Verify", "role": "BUYER"},
        ).status_code
        == 201
    )
    blocked = client.post("/auth/login", json=credentials)
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "Email chưa được xác nhận"

    token = fake_email_sender.verifications[-1][1]
    verified = client.post("/auth/verify-email", json={"token": token})
    assert verified.status_code == 200
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 400

    logged_in = client.post("/auth/login", json=credentials)
    assert logged_in.status_code == 200
    payload = jwt.decode(
        logged_in.json()["access_token"],
        get_settings().jwt_secret,
        algorithms=["HS256"],
    )
    assert payload["auth_version"] == 0


def test_resend_invalidates_previous_token_and_is_rate_limited(
    client: TestClient,
    fake_email_sender,
) -> None:
    email = "resend@example.com"
    assert client.post("/auth/register", json=registration_payload(email)).status_code == 201
    first_token = fake_email_sender.verifications[-1][1]

    resent = client.post("/auth/resend-verification", json={"email": email})
    assert resent.status_code == 200
    second_token = fake_email_sender.verifications[-1][1]
    assert second_token != first_token
    assert client.post("/auth/verify-email", json={"token": first_token}).status_code == 400
    assert client.post("/auth/verify-email", json={"token": second_token}).status_code == 200

    limited_email = "limited@example.com"
    assert (
        client.post("/auth/register", json=registration_payload(limited_email)).status_code == 201
    )
    assert (
        client.post("/auth/resend-verification", json={"email": limited_email}).status_code == 200
    )
    assert (
        client.post("/auth/resend-verification", json={"email": limited_email}).status_code == 429
    )


def test_forgot_password_is_generic_and_reset_revokes_old_jwt(
    db_session: Session,
    client: TestClient,
    fake_email_sender,
) -> None:
    user = add_user(db_session, email="reset@example.com")
    old_login = client.post("/auth/login", json={"email": user.email, "password": "Secret@123"})
    assert old_login.status_code == 200
    old_token = old_login.json()["access_token"]

    missing = client.post("/auth/forgot-password", json={"email": "missing@example.com"})
    existing = client.post("/auth/forgot-password", json={"email": user.email})
    assert missing.status_code == existing.status_code == 200
    assert missing.json() == existing.json()
    assert len(fake_email_sender.password_resets) == 1

    reset_token = fake_email_sender.password_resets[0][1]
    reset = client.post(
        "/auth/reset-password",
        json={"token": reset_token, "new_password": "NewSecret@123"},
    )
    assert reset.status_code == 200
    assert fake_email_sender.password_changes == [user.email]
    assert (
        client.post(
            "/auth/reset-password",
            json={"token": reset_token, "new_password": "Another@123"},
        ).status_code
        == 400
    )
    assert (
        client.post("/auth/login", json={"email": user.email, "password": "Secret@123"}).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/login", json={"email": user.email, "password": "NewSecret@123"}
        ).status_code
        == 200
    )
    assert (
        client.get("/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
    )


def test_expired_password_reset_token_is_rejected(
    db_session: Session,
    client: TestClient,
    fake_email_sender,
) -> None:
    user = add_user(db_session, email="expired@example.com")
    client.post("/auth/forgot-password", json={"email": user.email})
    raw_token = fake_email_sender.password_resets[0][1]
    token_row = db_session.scalar(select(AuthToken).where(AuthToken.user_id == user.id))
    assert token_row is not None
    token_row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.flush()
    response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "NewSecret@123"},
    )
    assert response.status_code == 400


def test_login_token_me_and_invalid_credentials(
    db_session: Session,
    client: TestClient,
) -> None:
    owner = add_user(db_session, email="owner@example.com", role="SHOP_OWNER")
    shop = Shop(owner_id=owner.id, name="Test Shop")
    db_session.add(shop)
    db_session.flush()

    assert (
        client.post("/auth/login", json={"email": owner.email, "password": "wrongpass"}).status_code
        == 401
    )
    response = client.post("/auth/login", json={"email": owner.email, "password": "Secret@123"})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "SHOP_OWNER"
    assert body["shop_id"] == shop.id
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


def test_register_and_login_are_case_insensitive_for_email(
    db_session: Session,
    client: TestClient,
    fake_email_sender,
) -> None:
    payload = registration_payload("Case@Example.com")
    registered = client.post("/auth/register", json=payload)
    assert registered.status_code == 201
    assert registered.json()["email"] == "case@example.com"
    assert db_session.get(User, registered.json()["id"]).email == "case@example.com"
    assert (
        client.post("/auth/register", json={**payload, "email": "case@example.com"}).status_code
        == 400
    )
    client.post("/auth/verify-email", json={"token": fake_email_sender.verifications[0][1]})
    response = client.post(
        "/auth/login", json={"email": "case@example.com", "password": "Secret@123"}
    )
    assert response.status_code == 200


def test_auth_rejects_password_outside_bcrypt_limits_and_unknown_fields(
    client: TestClient,
) -> None:
    payload = registration_payload("password@example.com")
    assert client.post("/auth/register", json={**payload, "password": "short"}).status_code == 422
    assert client.post("/auth/register", json={**payload, "password": "a" * 73}).status_code == 422
    assert (
        client.post("/auth/register", json={**payload, "email": "not-an-email"}).status_code == 422
    )
    assert client.post("/auth/register", json={**payload, "id": 1}).status_code == 422
    assert (
        client.post(
            "/auth/login",
            json={"email": "missing@example.com", "password": "a" * 73},
        ).status_code
        == 422
    )


def test_registration_email_failure_keeps_account_for_resend(
    db_session: Session,
    client: TestClient,
) -> None:
    class BrokenSender:
        def send_verification(self, recipient: str, token: str) -> None:
            raise EmailDeliveryError

    app.dependency_overrides[get_email_sender] = BrokenSender
    response = client.post("/auth/register", json=registration_payload("smtp-fail@example.com"))
    assert response.status_code == 503
    user = db_session.scalar(select(User).where(User.email == "smtp-fail@example.com"))
    assert user is not None
    assert user.email_verified_at is None


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

    with TestClient(protected_app) as protected_client:
        assert (
            protected_client.get(
                "/shop", headers={"Authorization": f"Bearer {token_for(buyer)}"}
            ).status_code
            == 403
        )
        assert (
            protected_client.get(
                "/admin", headers={"Authorization": f"Bearer {token_for(owner)}"}
            ).status_code
            == 403
        )
        response = protected_client.get(
            "/shop", headers={"Authorization": f"Bearer {token_for(owner)}"}
        )
        assert response.status_code == 200
        assert response.json() == shop.id
