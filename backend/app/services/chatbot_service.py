import re
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.shop import Shop
from app.models.user import User
from app.schemas.chatbot import ChatConfig, ChatMessage, ChatTable
from app.services.genie_client import get_genie_client
from app.services.genie_config import load_genie_config

PENDING = {
    "SUBMITTED",
    "FETCHING_METADATA",
    "FILTERING_CONTEXT",
    "ASKING_AI",
    "PENDING_WAREHOUSE",
    "EXECUTING_QUERY",
}


def scope_for(db: Session, user: User):
    if user.role == "ADMIN":
        return None
    if user.role != "SHOP_OWNER":
        raise HTTPException(403, "Chỉ admin và chủ shop được dùng chatbot")
    shop = db.scalar(select(Shop).where(Shop.owner_id == user.id))
    if shop is None or not shop.is_active:
        raise HTTPException(403, "Shop chưa được tạo hoặc đã bị khóa")
    return shop.id


def context(db: Session, user: User, *, required=True):
    shop_id = scope_for(db, user)
    config = load_genie_config()
    identity = (
        config.admin
        if config and shop_id is None
        else (config.shops.get(str(shop_id)) if config else None)
    )
    if required and identity is None:
        raise HTTPException(503, "Chatbot chưa được cấu hình cho tài khoản này")
    return shop_id, config, identity


def configuration(db: Session, user: User) -> ChatConfig:
    shop_id, _, identity = context(db, user, required=False)
    return ChatConfig(
        available=identity is not None,
        scope="Toàn hệ thống" if shop_id is None else "Shop của bạn",
        message=(
            "Hỏi dữ liệu kinh doanh. Số liệu cập nhật theo lần đồng bộ dữ liệu."
            if identity
            else "Chatbot chưa được cấu hình cho tài khoản này."
        ),
    )


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-fA-F0-9]{32}|[a-fA-F0-9-]{36}", value):
        raise HTTPException(502, "Genie trả về mã dữ liệu không hợp lệ")
    return value


def binding(user, shop_id, config, identity):
    return {
        "sub": str(user.id),
        "role": user.role,
        "shop_id": shop_id,
        "space": identity.space_id,
        "principal": identity.client_id,
        "host": config.host,
        "purpose": "genie-conversation",
        "aud": "daln-genie-conversation",
    }


def sign_conversation(conversation, user, shop_id, config, identity):
    return jwt.encode(
        {
            **binding(user, shop_id, config, identity),
            "conversation": identifier(conversation),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        get_settings().jwt_secret,
        algorithm="HS256",
    )


def read_conversation(token, user, shop_id, config, identity):
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=["HS256"],
            audience="daln-genie-conversation",
            options={"require": ["exp", "sub", "conversation", "purpose", "aud"]},
        )
        if any(
            payload.get(key) != value
            for key, value in binding(user, shop_id, config, identity).items()
        ):
            raise ValueError("Conversation belongs to another scope")
        return identifier(payload["conversation"])
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(
            403, "Cuộc trò chuyện không hợp lệ hoặc đã hết hạn. Hãy tạo cuộc trò chuyện mới."
        ) from None


def render_message(client, base, message, token) -> ChatMessage:
    if message.get("conversation_id") not in (None, base.rsplit("/", 1)[-1]):
        raise HTTPException(502, "Genie trả về cuộc trò chuyện không hợp lệ")
    message_id = identifier(message.get("message_id") or message.get("id"))
    status = message.get("status")
    result = ChatMessage(message_id=message_id, conversation_token=token, status="PENDING")
    if status in PENDING:
        return result
    if status != "COMPLETED":
        # Error fields can contain SQL and operational details; never forward the payload.
        result.status = "FAILED"
        result.text = "Genie chưa trả lời được câu hỏi này. Hãy tạo câu hỏi mới hoặc thử lại sau."
        return result
    texts = []
    for attachment in message.get("attachments", []):
        text = attachment.get("text", {}).get("content")
        if text:
            texts.append(text)
        query = attachment.get("query")
        if query is None:
            continue
        attachment_id = identifier(attachment.get("attachment_id"))
        response = client.request(
            "GET", f"{base}/messages/{message_id}/attachments/{attachment_id}/query-result"
        )
        statement = response.get("statement_response", {})
        state = statement.get("status", {}).get("state")
        if state in {"PENDING", "RUNNING"}:
            return result
        if state != "SUCCEEDED":
            raise HTTPException(502, "Không thể đọc kết quả Genie. Vui lòng thử lại sau.")
        manifest = statement.get("manifest", {})
        chunk = statement.get("result", {})
        rows = chunk.get("data_array") or []
        result.tables.append(
            ChatTable(
                description=query.get("description", "Kết quả truy vấn"),
                columns=[
                    {"name": c["name"], "type_name": c.get("type_name", "STRING")}
                    for c in manifest.get("schema", {}).get("columns", [])
                ],
                rows=rows[:100],
                truncated=bool(
                    manifest.get("truncated")
                    or chunk.get("next_chunk_index") is not None
                    or len(rows) > 100
                    or int(manifest.get("total_row_count", len(rows))) > len(rows)
                ),
            )
        )
    result.status = "COMPLETED"
    result.text = "\n\n".join(texts) or (
        "Kết quả từ dữ liệu Gold:"
        if result.tables
        else "Genie không trả về dữ liệu cho câu hỏi này."
    )
    return result


def ask(db: Session, user: User, question: str, conversation_token: str | None):
    shop_id, config, identity = context(db, user)
    client = get_genie_client(
        config.host, identity.client_id, identity.client_secret.get_secret_value()
    )
    if conversation_token:
        conversation = read_conversation(conversation_token, user, shop_id, config, identity)
        base = f"{identity.space_id}/conversations/{conversation}"
        message = client.request("POST", f"{base}/messages", {"content": question})
    else:
        response = client.request(
            "POST", f"{identity.space_id}/start-conversation", {"content": question}
        )
        conversation = identifier(
            response.get("conversation_id")
            or response.get("conversation", {}).get("conversation_id")
        )
        message = response.get("message", {})
        base = f"{identity.space_id}/conversations/{conversation}"
    token = sign_conversation(conversation, user, shop_id, config, identity)
    return render_message(client, base, message, token)


def poll(db: Session, user: User, message_id: str, conversation_token: str):
    shop_id, config, identity = context(db, user)
    conversation = read_conversation(conversation_token, user, shop_id, config, identity)
    message_id = identifier(message_id)
    client = get_genie_client(
        config.host, identity.client_id, identity.client_secret.get_secret_value()
    )
    base = f"{identity.space_id}/conversations/{conversation}"
    message = client.request("GET", f"{base}/messages/{message_id}")
    return render_message(client, base, message, conversation_token)
