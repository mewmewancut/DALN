import json
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.main import app
from app.models import User, UserAddress
from app.services.profile_service import set_default_address
from app.tests.conftest import test_engine
from app.tests.test_catalog import user_with_token

ADDRESS = {
    "label": "Nhà riêng",
    "receiver_name": "Nguyễn Văn A",
    "receiver_phone": "0901234567",
    "province_code": "01",
    "commune_code": "00004",
    "address_detail": "12 phố Đội Cấn",
}


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_local_admin_dataset_has_valid_two_level_hierarchy() -> None:
    path = Path(__file__).resolve().parents[1] / "data" / "vn_admin_units_2025.json"
    dataset = json.loads(path.read_text(encoding="utf-8"))
    provinces = dataset["provinces"]
    communes = [commune for province in provinces for commune in province["communes"]]

    assert len(provinces) == dataset["metadata"]["province_count"] == 34
    assert len(communes) == dataset["metadata"]["commune_count"] == 3321
    assert len({province["code"] for province in provinces}) == 34
    assert len({commune["code"] for commune in communes}) == 3321
    assert all(len(province["code"]) == 2 for province in provinces)
    assert all(len(commune["code"]) == 5 for commune in communes)
    assert all(province["name"].startswith(("Tỉnh ", "Thành phố ")) for province in provinces)
    assert all(commune["name"].startswith(("Xã ", "Phường ", "Đặc khu ")) for commune in communes)


def test_location_endpoints_filter_communes_and_reject_unknown_province(
    client: TestClient,
) -> None:
    provinces = client.get("/locations/provinces")
    assert provinces.status_code == 200
    assert len(provinces.json()) == 34
    assert {"code": "01", "name": "Thành phố Hà Nội"} in provinces.json()

    communes = client.get("/locations/communes", params={"province_code": "01"})
    assert communes.status_code == 200
    assert {"code": "00004", "name": "Phường Ba Đình"} in communes.json()
    assert client.get("/locations/communes", params={"province_code": "00"}).status_code == 400


@pytest.mark.parametrize("role", ["BUYER", "SHOP_OWNER", "ADMIN"])
def test_all_authenticated_roles_can_read_and_update_profile(
    db_session: Session, client: TestClient, role: str
) -> None:
    user, headers = user_with_token(db_session, f"profile-{role.lower()}@example.com", role)
    db_session.commit()
    response = client.patch(
        "/users/me/profile",
        json={
            "full_name": "  Tên mới  ",
            "phone": "0901234567",
            "avatar_url": "https://example.com/avatar.png",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Tên mới"
    assert response.json()["email"] == user.email
    assert client.get("/users/me/profile", headers=headers).json()["phone"] == "0901234567"
    assert (
        client.patch("/users/me/profile", json={"role": "ADMIN"}, headers=headers).status_code
        == 422
    )


def test_address_crud_default_promotion_and_ownership(
    db_session: Session, client: TestClient
) -> None:
    buyer, headers = user_with_token(db_session, "address-owner@example.com", "BUYER")
    _, other_headers = user_with_token(db_session, "address-other@example.com", "BUYER")
    _, shop_headers = user_with_token(db_session, "address-shop@example.com", "SHOP_OWNER")
    db_session.commit()

    first = client.post("/users/me/addresses", json=ADDRESS, headers=headers)
    assert first.status_code == 201
    assert first.json()["is_default"] is True
    assert first.json()["province_name"] == "Thành phố Hà Nội"
    assert first.json()["commune_name"] == "Phường Ba Đình"

    second = client.post(
        "/users/me/addresses",
        json={**ADDRESS, "label": "Công ty", "commune_code": "00008"},
        headers=headers,
    )
    assert second.status_code == 201
    second_id = second.json()["id"]
    assert (
        client.put(f"/users/me/addresses/{second_id}/default", headers=headers).status_code == 200
    )
    assert (
        client.put(f"/users/me/addresses/{second_id}/default", headers=headers).status_code == 200
    )

    listed = client.get("/users/me/addresses", headers=headers).json()
    assert listed[0]["id"] == second_id
    assert sum(item["is_default"] for item in listed) == 1
    assert (
        client.patch(
            f"/users/me/addresses/{second_id}",
            json={"address_detail": "99 phố Huế"},
            headers=headers,
        ).json()["address_detail"]
        == "99 phố Huế"
    )
    assert client.get("/users/me/addresses", headers=other_headers).status_code == 200
    assert (
        client.patch(
            f"/users/me/addresses/{second_id}",
            json={"label": "Không được"},
            headers=other_headers,
        ).status_code
        == 404
    )
    assert client.get("/users/me/addresses", headers=shop_headers).status_code == 403

    assert client.delete(f"/users/me/addresses/{second_id}", headers=headers).status_code == 200
    remaining = client.get("/users/me/addresses", headers=headers).json()
    assert len(remaining) == 1
    assert remaining[0]["is_default"] is True
    assert (
        db_session.scalar(
            select(func.count()).select_from(UserAddress).where(UserAddress.user_id == buyer.id)
        )
        == 1
    )


def test_address_validates_hierarchy_and_enforces_limit(
    db_session: Session, client: TestClient
) -> None:
    _, headers = user_with_token(db_session, "address-limit@example.com", "BUYER")
    db_session.commit()
    invalid = client.post(
        "/users/me/addresses",
        json={**ADDRESS, "province_code": "79"},
        headers=headers,
    )
    assert invalid.status_code == 400

    for index in range(10):
        response = client.post(
            "/users/me/addresses",
            json={**ADDRESS, "label": f"Địa chỉ {index}"},
            headers=headers,
        )
        assert response.status_code == 201
    assert client.post("/users/me/addresses", json=ADDRESS, headers=headers).status_code == 400


def test_concurrent_default_changes_leave_exactly_one_default() -> None:
    with Session(test_engine) as setup:
        user = User(
            email=f"default-race-{uuid4().hex}@example.com",
            password_hash="unused",
            full_name="Default Race",
            role="BUYER",
        )
        setup.add(user)
        setup.flush()
        addresses = [
            UserAddress(
                user_id=user.id,
                label=f"Địa chỉ {index}",
                receiver_name="Nguyễn An",
                receiver_phone="0900000000",
                province_code="01",
                province_name="Thành phố Hà Nội",
                commune_code="00004",
                commune_name="Phường Ba Đình",
                address_detail=f"Số {index} Đội Cấn",
                is_default=index == 0,
            )
            for index in range(3)
        ]
        setup.add_all(addresses)
        setup.commit()
        user_id = user.id
        target_ids = [addresses[1].id, addresses[2].id]

    barrier = Barrier(2)

    def change_default(address_id: int) -> None:
        with Session(test_engine) as session:
            barrier.wait()
            set_default_address(session, user_id, address_id)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(change_default, target_ids))
        with Session(test_engine) as check:
            defaults = list(
                check.scalars(
                    select(UserAddress).where(
                        UserAddress.user_id == user_id,
                        UserAddress.is_default.is_(True),
                    )
                )
            )
            assert len(defaults) == 1
            assert defaults[0].id in target_ids
    finally:
        with Session(test_engine) as cleanup:
            saved_user = cleanup.get(User, user_id)
            if saved_user is not None:
                cleanup.delete(saved_user)
                cleanup.commit()
