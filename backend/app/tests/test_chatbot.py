import json
from unittest.mock import Mock
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.main import app
from app.services import chatbot_service
from app.services.genie_config import GenieConfig, load_genie_config
from app.tests.test_catalog import user_with_token
from app.tests.test_shop_stats import seed_shop

CONVERSATION = "c" * 32
MESSAGE = "a" * 32
ATTACHMENT = "d" * 32


def identity(number):
    return {
        "space_id": str(number) * 32,
        "client_id": f"fake-principal-{number}",
        "client_secret": f"fake-secret-{number}",
    }


@pytest.fixture
def ctx(db_session, monkeypatch):
    shop = seed_shop(db_session)
    other = seed_shop(db_session, suffix="other")
    admin, admin_headers = user_with_token(db_session, f"{uuid4()}@example.com", "ADMIN")
    buyer, buyer_headers = user_with_token(db_session, f"{uuid4()}@example.com", "BUYER")
    db_session.commit()
    config = GenieConfig.model_validate(
        {
            "host": "https://fake.cloud.databricks.com",
            "e4_passed": True,
            "admin": identity(1),
            "shops": {str(shop["shop"].id): identity(2), str(other["shop"].id): identity(3)},
        }
    )
    monkeypatch.setattr(chatbot_service, "load_genie_config", lambda: config)
    remote = Mock()
    remote.request.side_effect = lambda method, path, payload=None: (
        {"conversation_id": CONVERSATION, "message": {"message_id": MESSAGE, "status": "ASKING_AI"}}
        if path.endswith("start-conversation")
        else {
            "message_id": MESSAGE,
            "status": "COMPLETED",
            "attachments": [{"text": {"content": "Doanh thu shop"}}],
        }
    )
    factory = Mock(return_value=remote)
    monkeypatch.setattr(chatbot_service, "get_genie_client", factory)
    return {
        "shop": shop,
        "other": other,
        "admin": admin,
        "admin_headers": admin_headers,
        "buyer": buyer,
        "buyer_headers": buyer_headers,
        "config": config,
        "remote": remote,
        "factory": factory,
    }


@pytest.fixture
def client(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def start(client, headers, **extra):
    return client.post(
        "/analytics/chat/messages", headers=headers, json={"question": "Doanh thu?", **extra}
    )


def test_admin_and_shop_use_distinct_server_identities_and_database_shop_not_jwt(ctx, client):
    for headers, expected in [
        (ctx["admin_headers"], identity(1)),
        (ctx["shop"]["headers"], identity(2)),
    ]:
        config = client.get("/analytics/chat/config", headers=headers)
        assert config.status_code == 200 and config.json()["available"]
        assert "fake-secret" not in config.text and "space_id" not in config.text
        response = start(client, headers)
        assert response.status_code == 200
        assert response.json()["status"] == "PENDING"
        ctx["factory"].assert_called_with(
            ctx["config"].host, expected["client_id"], expected["client_secret"]
        )
        assert "fake-secret" not in response.text
        assert (
            ctx["remote"].request.call_args.args[1] == expected["space_id"] + "/start-conversation"
        )
        assert ctx["remote"].request.call_args.args[2] == {"content": "Doanh thu?"}


def test_followup_and_poll_keep_owned_conversation_context(ctx, client):
    headers = ctx["shop"]["headers"]
    token = start(client, headers).json()["conversation_token"]
    followed = start(client, headers, conversation_token=token)
    assert followed.status_code == 200 and followed.json()["text"] == "Doanh thu shop"
    base = identity(2)["space_id"] + "/conversations/" + CONVERSATION
    assert ctx["remote"].request.call_args.args[1] == base + "/messages"
    polled = client.post(
        f"/analytics/chat/messages/{MESSAGE}", headers=headers, json={"conversation_token": token}
    )
    assert polled.status_code == 200 and polled.json()["status"] == "COMPLETED"
    assert ctx["remote"].request.call_args.args[1] == base + f"/messages/{MESSAGE}"


def test_conversation_token_cannot_authenticate_as_login_token(ctx, client):
    token = start(client, ctx["shop"]["headers"]).json()["conversation_token"]
    headers = {"Authorization": f"Bearer {token}"}
    ctx["remote"].reset_mock()
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert start(client, headers).status_code == 401
    ctx["remote"].request.assert_not_called()
    assert (
        start(
            client,
            ctx["shop"]["headers"],
            conversation_token=ctx["shop"]["headers"]["Authorization"][7:],
        ).status_code
        == 403
    )


@pytest.mark.parametrize("target", ["other", "admin"])
def test_other_user_shop_or_admin_cannot_reuse_shop_conversation(ctx, client, target):
    token = start(client, ctx["shop"]["headers"]).json()["conversation_token"]
    headers = ctx["other"]["headers"] if target == "other" else ctx["admin_headers"]
    ctx["remote"].reset_mock()
    assert start(client, headers, conversation_token=token).status_code == 403
    assert (
        client.post(
            f"/analytics/chat/messages/{MESSAGE}",
            headers=headers,
            json={"conversation_token": token},
        ).status_code
        == 403
    )
    ctx["remote"].request.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [("exp", 0), ("purpose", "other"), ("aud", "other"), ("space", "4" * 32), ("shop_id", 999999)],
)
def test_expired_or_rebound_conversation_is_rejected_before_remote_call(ctx, client, field, value):
    headers = ctx["shop"]["headers"]
    token = start(client, headers).json()["conversation_token"]
    payload = jwt.decode(
        token,
        get_settings().jwt_secret,
        algorithms=["HS256"],
        audience="daln-genie-conversation",
    )
    payload[field] = value
    token = jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")
    ctx["remote"].reset_mock()
    assert start(client, headers, conversation_token=token).status_code == 403
    ctx["remote"].request.assert_not_called()


def test_invalid_signature_and_changed_role_or_shop_lock_rejected(ctx, client, db_session):
    headers = ctx["shop"]["headers"]
    token = start(client, headers).json()["conversation_token"]
    assert start(client, headers, conversation_token=token + "bad").status_code == 403
    ctx["shop"]["shop"].is_active = False
    db_session.commit()
    assert start(client, headers).status_code == 403
    assert (
        client.post(
            f"/analytics/chat/messages/{MESSAGE}",
            headers=headers,
            json={"conversation_token": token},
        ).status_code
        == 403
    )


def test_missing_scope_fails_closed_and_never_falls_back_to_admin(ctx, client, monkeypatch):
    ctx["config"].shops.clear()
    headers = ctx["shop"]["headers"]
    assert client.get("/analytics/chat/config", headers=headers).json()["available"] is False
    assert start(client, headers).status_code == 503
    ctx["factory"].assert_not_called()
    monkeypatch.setattr(chatbot_service, "load_genie_config", lambda: None)
    assert start(client, ctx["admin_headers"]).status_code == 503


def test_anonymous_buyer_locked_account_and_shopless_owner_cannot_call_genie(
    ctx, client, db_session
):
    assert start(client, {}).status_code == 401
    assert start(client, ctx["buyer_headers"]).status_code == 403
    assert client.get("/analytics/chat/config", headers=ctx["buyer_headers"]).status_code == 403
    owner, headers = user_with_token(db_session, f"{uuid4()}@example.com", "SHOP_OWNER")
    db_session.commit()
    assert start(client, headers).status_code == 403
    owner.is_active = False
    db_session.commit()
    assert start(client, headers).status_code == 403
    ctx["remote"].request.assert_not_called()


@pytest.mark.parametrize(
    "extra",
    [
        {"shop_id": 999},
        {"space_id": "1" * 32},
        {"client_secret": "fake"},
        {"question": " "},
        {"question": "x" * 2001},
    ],
)
def test_request_rejects_scope_forgery_and_invalid_question(ctx, client, extra):
    assert start(client, ctx["shop"]["headers"], **extra).status_code == 422
    ctx["remote"].request.assert_not_called()


@pytest.mark.parametrize("status", sorted(chatbot_service.PENDING))
def test_all_running_genie_states_return_pending(ctx, client, status):
    ctx["remote"].request.return_value = None
    ctx["remote"].request.side_effect = lambda *args: {
        "conversation_id": CONVERSATION,
        "message": {"id": MESSAGE, "status": status},
    }
    assert start(client, ctx["shop"]["headers"]).json()["status"] == "PENDING"


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED", "UNKNOWN"])
def test_failure_does_not_forward_raw_genie_errors(ctx, client, status):
    ctx["remote"].request.side_effect = lambda *args: {
        "conversation_id": CONVERSATION,
        "message": {
            "id": MESSAGE,
            "status": status,
            "error": {"error": "fake-secret operational SQL"},
        },
    }
    result = start(client, ctx["shop"]["headers"])
    assert result.status_code == 200 and result.json()["status"] == "FAILED"
    assert "operational SQL" not in result.text and "fake-secret" not in result.text


@pytest.mark.parametrize("row_count", [0, 2, 101])
def test_query_results_include_columns_rows_empty_and_truncation_without_credentials(
    ctx, client, row_count
):
    ctx["remote"].request.side_effect = [
        {
            "conversation_id": CONVERSATION,
            "message": {
                "id": MESSAGE,
                "status": "COMPLETED",
                "attachments": [
                    {"attachment_id": ATTACHMENT, "query": {"description": "Doanh thu"}}
                ],
            },
        },
        {
            "statement_response": {
                "status": {"state": "SUCCEEDED"},
                "manifest": {
                    "schema": {"columns": [{"name": "revenue", "type_name": "DECIMAL"}]},
                    "total_row_count": row_count,
                },
                "result": {
                    "data_array": [["123000"]] * row_count,
                    "external_links": [{"url": "fake-secret-url"}],
                },
            }
        },
    ]
    response = start(client, ctx["shop"]["headers"])
    assert response.status_code == 200
    table = response.json()["tables"][0]
    assert len(table["rows"]) == min(row_count, 100)
    assert table["truncated"] is (row_count > 100)
    assert table["columns"][0]["name"] == "revenue"
    assert "fake-secret-url" not in response.text
    assert (
        f"/messages/{MESSAGE}/attachments/{ATTACHMENT}/query-result"
        in ctx["remote"].request.call_args.args[1]
    )


@pytest.mark.parametrize(
    "state,expected", [("PENDING", 200), ("RUNNING", 200), ("FAILED", 502), ("CLOSED", 502)]
)
def test_query_results_pending_or_failure_do_not_pretend_complete(ctx, client, state, expected):
    ctx["remote"].request.side_effect = [
        {
            "conversation_id": CONVERSATION,
            "message": {
                "id": MESSAGE,
                "status": "COMPLETED",
                "attachments": [{"attachment_id": ATTACHMENT, "query": {}}],
            },
        },
        {"statement_response": {"status": {"state": state}}},
    ]
    response = start(client, ctx["shop"]["headers"])
    assert response.status_code == expected
    if expected == 200:
        assert response.json()["status"] == "PENDING"


def test_api_preserves_sanitized_remote_error(ctx, client):
    ctx["remote"].request.side_effect = HTTPException(429, "Genie đang quá tải")
    response = start(client, ctx["shop"]["headers"])
    assert response.status_code == 429 and response.json()["detail"] == "Genie đang quá tải"


def test_wrong_conversation_in_upstream_response_never_returns_its_contents(ctx, client):
    ctx["remote"].request.side_effect = lambda *args: {
        "conversation_id": CONVERSATION,
        "message": {
            "id": MESSAGE,
            "conversation_id": "f" * 32,
            "status": "COMPLETED",
            "attachments": [{"text": {"content": "private other conversation"}}],
        },
    }
    response = start(client, ctx["shop"]["headers"])
    assert response.status_code == 502
    assert "private other conversation" not in response.text


@pytest.mark.parametrize("change", ["gate", "identity", "space", "missing", "blank_secret"])
def test_runtime_config_invalid_or_unisolated_disables_genie_without_leaking_secret(
    tmp_path, monkeypatch, change
):
    data = {
        "host": "https://fake.cloud.databricks.com",
        "e4_passed": True,
        "admin": identity(1),
        "shops": {"7": identity(2)},
    }
    if change == "gate":
        data["e4_passed"] = False
    elif change == "identity":
        data["shops"]["7"]["client_id"] = data["admin"]["client_id"]
    elif change == "space":
        data["shops"]["7"]["space_id"] = data["admin"]["space_id"]
    elif change == "missing":
        del data["shops"]["7"]["client_secret"]
    else:
        data["shops"]["7"]["client_secret"] = " "
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(get_settings(), "genie_config_path", str(path))
    assert load_genie_config() is None
