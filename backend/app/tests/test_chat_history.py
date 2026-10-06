from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select

from app.models.chat import ChatConversation, ChatSavedMessage
from app.services.chat_question_service import prompt
from app.services.genie_config import GenieConfig
from app.tests.test_chatbot import MESSAGE, start
from app.tests.test_chatbot import client as client
from app.tests.test_chatbot import ctx as ctx


def test_month_without_year_has_current_vietnam_year_and_explicit_dates_are_preserved():
    question = "doanh thu thang 9"
    content = prompt(question, now=datetime(2025, 12, 31, 18, tzinfo=timezone.utc))
    assert "2026-01-01" in content and "defaults to 2026" in content
    assert content.endswith("User question: doanh thu thang 9")
    assert prompt("tháng 9 năm 2023").endswith("User question: tháng 9 năm 2023")


def test_shared_space_requires_private_principals_and_still_isolates_conversations(ctx, client):
    data = ctx["config"].model_dump(mode="json")
    # SecretStr serializes redacted; supply only clearly fake fixture values.
    for entry in [data["admin"], *data["shops"].values()]:
        entry["client_secret"] = "FAKE-SECRET"
    shared = "f" * 32
    data["shared_shop_space_id"] = shared
    for entry in data["shops"].values():
        entry["space_id"] = shared
    config = GenieConfig.model_validate(data)
    ctx["config"].shops = config.shops
    ctx["config"].shared_shop_space_id = shared
    token = start(client, ctx["shop"]["headers"]).json()["conversation_token"]
    ctx["remote"].reset_mock()
    assert start(client, ctx["other"]["headers"], conversation_token=token).status_code == 403
    ctx["remote"].request.assert_not_called()
    entries = list(data["shops"].values())
    entries[1]["client_id"] = entries[0]["client_id"]
    with pytest.raises(ValueError):
        GenieConfig.model_validate(data)


def test_history_survives_reload_resumes_with_fresh_token_and_rename_delete(
    ctx, client, db_session
):
    headers = ctx["shop"]["headers"]
    response = start(client, headers).json()
    conversation_id = response["conversation_id"]
    url = f"/analytics/chat/conversations/{conversation_id}"
    polled = client.post(
        f"/analytics/chat/messages/{MESSAGE}",
        headers=headers,
        json={"conversation_token": response["conversation_token"]},
    )
    assert polled.status_code == 200
    listing = client.get("/analytics/chat/conversations", headers=headers).json()
    assert listing[0]["id"] == conversation_id and listing[0]["title"] == "Doanh thu?"
    detail = client.get(url, headers=headers).json()
    assert detail["can_resume"] and detail["conversation_token"]
    assert len(detail["messages"]) == 1
    assert detail["messages"][0]["text"] == "Doanh thu shop"
    assert "conversation_token" not in db_session.scalar(select(ChatSavedMessage)).answer
    assert (
        client.patch(url, headers=headers, json={"title": " Báo cáo tháng 9 "}).json()["title"]
        == "Báo cáo tháng 9"
    )
    assert client.patch(url, headers=headers, json={"title": " "}).status_code == 422
    assert (
        start(client, headers, conversation_token=detail["conversation_token"]).status_code == 200
    )
    assert client.delete(url, headers=headers).status_code == 204
    assert client.get(url, headers=headers).status_code == 404
    assert db_session.scalar(select(func.count()).select_from(ChatSavedMessage)) == 0


@pytest.mark.parametrize("actor", ["other", "admin"])
def test_history_is_private_even_from_other_shop_and_admin(ctx, client, actor):
    headers = ctx["shop"]["headers"]
    conversation_id = start(client, headers).json()["conversation_id"]
    target = ctx[actor]["headers"] if actor == "other" else ctx["admin_headers"]
    url = f"/analytics/chat/conversations/{conversation_id}"
    assert client.get("/analytics/chat/conversations", headers=target).json() == []
    assert client.get(url, headers=target).status_code == 403
    assert client.patch(url, headers=target, json={"title": "forged"}).status_code == 403
    assert client.delete(url, headers=target).status_code == 403
    assert client.get(url, headers=headers).status_code == 200


def test_history_reads_old_results_without_resume_after_identity_change(ctx, client):
    headers = ctx["shop"]["headers"]
    conversation_id = start(client, headers).json()["conversation_id"]
    ctx["config"].shops[str(ctx["shop"]["shop"].id)].space_id = "f" * 32
    detail = client.get(f"/analytics/chat/conversations/{conversation_id}", headers=headers).json()
    assert detail["can_resume"] is False and detail["conversation_token"] is None
    assert detail["messages"][0]["question"] == "Doanh thu?"


def test_history_remains_readable_when_genie_configuration_is_missing(ctx, client, monkeypatch):
    headers = ctx["shop"]["headers"]
    conversation_id = start(client, headers).json()["conversation_id"]
    monkeypatch.setattr("app.services.chatbot_service.load_genie_config", lambda: None)
    detail = client.get(f"/analytics/chat/conversations/{conversation_id}", headers=headers).json()
    assert detail["can_resume"] is False and detail["conversation_token"] is None
    assert detail["messages"][0]["question"] == "Doanh thu?"


def test_missing_new_shop_scope_reports_automatic_provisioning_and_still_fails_closed(ctx, client):
    ctx["config"].shared_shop_space_id = "f" * 32
    del ctx["config"].shops[str(ctx["shop"]["shop"].id)]
    result = client.get("/analytics/chat/config", headers=ctx["shop"]["headers"]).json()
    assert result["available"] is False and result["provisioning"] is True
    assert start(client, ctx["shop"]["headers"]).status_code == 503
    ctx["remote"].request.assert_not_called()


def test_history_rolls_back_all_rows_on_persistence_failure(ctx, client, db_session, monkeypatch):
    monkeypatch.setattr(db_session, "commit", Mock(side_effect=RuntimeError("FAKE-DB-ERROR")))
    with pytest.raises(RuntimeError):
        start(client, ctx["shop"]["headers"])
    assert db_session.scalar(select(func.count()).select_from(ChatConversation)) == 0
    assert db_session.scalar(select(func.count()).select_from(ChatSavedMessage)) == 0


def test_history_pages_messages_without_loss_or_duplication(ctx, client, db_session):
    headers = ctx["shop"]["headers"]
    conversation_id = start(client, headers).json()["conversation_id"]
    original = db_session.scalar(select(ChatSavedMessage))
    for index in range(105):
        db_session.add(
            ChatSavedMessage(
                conversation_id=conversation_id,
                remote_id=f"{index + 1:032x}",
                question=f"Câu hỏi {index}",
                answer={**original.answer, "message_id": f"{index + 1:032x}"},
            )
        )
    db_session.commit()
    url = f"/analytics/chat/conversations/{conversation_id}"
    newest = client.get(url, headers=headers).json()
    assert len(newest["messages"]) == 100 and newest["has_more"]
    older = client.get(
        url, headers=headers, params={"before_id": newest["messages"][0]["saved_id"]}
    ).json()
    assert len(older["messages"]) == 6 and not older["has_more"]
    ids = [m["saved_id"] for m in older["messages"] + newest["messages"]]
    assert len(set(ids)) == 106 and ids == sorted(ids)
    assert client.get(url, headers=headers, params={"before_id": 0}).status_code == 422
