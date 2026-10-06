"""Ownership and persistence for analytics chat, independently of remote token lifetime."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.chat import ChatConversation, ChatSavedMessage


def owned(db, user, shop_id, conversation_id):
    conversation = db.get(ChatConversation, conversation_id)
    if conversation is None:
        raise HTTPException(404, "Không tìm thấy cuộc trò chuyện")
    if (
        conversation.user_id != user.id
        or conversation.role != user.role
        or conversation.shop_id != shop_id
    ):
        raise HTTPException(403, "Bạn không có quyền truy cập cuộc trò chuyện này")
    return conversation


def save(db: Session, user, shop_id, config, identity, remote_id, question, result):
    conversation = db.scalar(
        select(ChatConversation).where(
            ChatConversation.user_id == user.id,
            ChatConversation.space_id == identity.space_id,
            ChatConversation.remote_id == remote_id,
        )
    )
    try:
        if conversation is None:
            conversation = ChatConversation(
                user_id=user.id,
                role=user.role,
                shop_id=shop_id,
                title=(question or "Cuộc trò chuyện")[:120],
                remote_id=remote_id,
                space_id=identity.space_id,
                principal=identity.client_id,
                host=config.host,
            )
            db.add(conversation)
            db.flush()
        elif (
            conversation.principal != identity.client_id
            or conversation.role != user.role
            or conversation.shop_id != shop_id
            or conversation.host != config.host
        ):
            raise HTTPException(403, "Cuộc trò chuyện đã thay đổi phạm vi")
        message = db.scalar(
            select(ChatSavedMessage).where(
                ChatSavedMessage.conversation_id == conversation.id,
                ChatSavedMessage.remote_id == result.message_id,
            )
        )
        snapshot = result.model_dump(exclude={"conversation_token", "conversation_id"})
        if message is None:
            if question is None:
                raise HTTPException(404, "Tin nhắn chưa được lưu")
            message = ChatSavedMessage(
                conversation_id=conversation.id,
                remote_id=result.message_id,
                question=question,
                answer=snapshot,
            )
            db.add(message)
        else:
            message.answer = snapshot
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()
        result.conversation_id = conversation.id
        return result
    except Exception:
        db.rollback()
        raise


def list_conversations(db, user, shop_id, limit, offset):
    rows = db.scalars(
        select(ChatConversation)
        .where(
            ChatConversation.user_id == user.id,
            ChatConversation.role == user.role,
            ChatConversation.shop_id == shop_id,
        )
        .order_by(ChatConversation.updated_at.desc(), ChatConversation.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [{"id": c.id, "title": c.title, "updated_at": c.updated_at} for c in rows]


def remove(db, user, shop_id, conversation_id):
    conversation = owned(db, user, shop_id, conversation_id)
    try:
        db.execute(
            delete(ChatSavedMessage).where(ChatSavedMessage.conversation_id == conversation.id)
        )
        db.delete(conversation)
        db.commit()
    except Exception:
        db.rollback()
        raise


def detail(db, user, conversation_id, before_id=None):
    from app.services.chatbot_service import context, sign_conversation

    shop_id, config, identity = context(db, user, required=False)
    conversation = owned(db, user, shop_id, conversation_id)
    statement = select(ChatSavedMessage).where(ChatSavedMessage.conversation_id == conversation.id)
    if before_id is not None:
        statement = statement.where(ChatSavedMessage.id < before_id)
    rows = db.scalars(statement.order_by(ChatSavedMessage.id.desc()).limit(101)).all()
    can_resume = bool(
        identity
        and conversation.space_id == identity.space_id
        and conversation.principal == identity.client_id
        and conversation.host == config.host
    )
    return {
        "id": conversation.id,
        "title": conversation.title,
        "updated_at": conversation.updated_at,
        "can_resume": can_resume,
        "conversation_token": sign_conversation(
            conversation.remote_id, user, shop_id, config, identity
        )
        if can_resume
        else None,
        "has_more": len(rows) > 100,
        "messages": [
            {
                **m.answer,
                "question": m.question,
                "saved_id": m.id,
                "conversation_id": conversation.id,
            }
            for m in reversed(rows[:100])
        ],
    }


def rename(db, user, shop_id, conversation_id, title):
    conversation = owned(db, user, shop_id, conversation_id)
    conversation.title = title
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "id": conversation.id,
        "title": conversation.title,
        "updated_at": conversation.updated_at,
    }
