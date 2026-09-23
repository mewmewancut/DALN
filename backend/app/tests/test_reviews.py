from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.deps import get_db
from app.main import app
from app.tests.test_catalog import user_with_token
from app.tests.test_orders import change_status, create_order


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def deliver_order(client: TestClient, context: dict) -> None:
    for status in ("CONFIRMED", "PREPARING", "SHIPPING", "DELIVERED"):
        assert change_status(client, context, status).status_code == 200


def test_review_requires_delivered_order(db_session: Session, client: TestClient) -> None:
    context = create_order(client, db_session)
    order_item_id = context["order"]["items"][0]["id"]
    assert change_status(client, context, "CONFIRMED").status_code == 200
    assert change_status(client, context, "PREPARING").status_code == 200
    assert change_status(client, context, "SHIPPING").status_code == 200

    response = client.post(
        "/reviews",
        json={"order_item_id": order_item_id, "rating": 5, "comment": "Đẹp"},
        headers=context["headers"],
    )
    assert response.status_code == 400


def test_review_rejects_other_buyer_order_item(db_session: Session, client: TestClient) -> None:
    context = create_order(client, db_session)
    deliver_order(client, context)
    order_item_id = context["order"]["items"][0]["id"]
    _, other_headers = user_with_token(db_session, "other-review-buyer@example.com", "BUYER")
    db_session.commit()

    response = client.post(
        "/reviews",
        json={"order_item_id": order_item_id, "rating": 4},
        headers=other_headers,
    )
    assert response.status_code == 403
    assert (
        client.post("/reviews", json={"order_item_id": order_item_id, "rating": 4}).status_code
        == 401
    )
    assert (
        client.post(
            "/reviews",
            json={"order_item_id": 999999999, "rating": 4},
            headers=context["headers"],
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/reviews",
            json={"order_item_id": order_item_id, "rating": 6},
            headers=context["headers"],
        ).status_code
        == 422
    )


def test_review_valid_then_duplicate_rejected_and_rating_average_updates(
    db_session: Session, client: TestClient
) -> None:
    context = create_order(client, db_session)
    deliver_order(client, context)
    order_item_id = context["order"]["items"][0]["id"]
    product_id = context["product"].id
    before_review = client.get(
        f"/orders/{context['order']['id']}", headers=context["headers"]
    ).json()
    assert before_review["items"][0]["review_id"] is None

    created = client.post(
        "/reviews",
        json={"order_item_id": order_item_id, "rating": 4, "comment": "Ổn"},
        headers=context["headers"],
    )
    assert created.status_code == 200
    body = created.json()
    assert body["product_id"] == product_id
    assert body["rating"] == 4
    assert body["buyer_id"] == context["buyer"].id
    after_review = client.get(
        f"/orders/{context['order']['id']}", headers=context["headers"]
    ).json()
    assert after_review["items"][0]["review_id"] == body["id"]

    duplicate = client.post(
        "/reviews",
        json={"order_item_id": order_item_id, "rating": 5},
        headers=context["headers"],
    )
    assert duplicate.status_code == 400

    reviews = client.get(f"/products/{product_id}/reviews")
    assert reviews.status_code == 200
    reviews_body = reviews.json()
    assert reviews_body["total"] == 1
    assert reviews_body["rating_average"] == 4.0
    assert reviews_body["items"][0]["comment"] == "Ổn"

    product_detail = client.get(f"/products/{product_id}")
    assert product_detail.json()["rating_average"] == 4.0


def test_product_reviews_endpoint_defaults_and_missing_product(
    db_session: Session, client: TestClient
) -> None:
    context = create_order(client, db_session)
    product_id = context["product"].id

    empty = client.get(f"/products/{product_id}/reviews")
    assert empty.status_code == 200
    assert empty.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "rating_average": None,
    }

    assert client.get("/products/999999999/reviews").status_code == 404
