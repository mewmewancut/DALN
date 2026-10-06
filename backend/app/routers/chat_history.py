from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.chat_history import ConversationDetail, ConversationRename, ConversationSummary
from app.services import chat_history_service, chatbot_service

router = APIRouter(prefix="/analytics/chat/conversations", tags=["chatbot history"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=list[ConversationSummary])
def conversations(
    db: Db, user: CurrentUser, limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)
):
    return chat_history_service.list_conversations(
        db, user, chatbot_service.scope_for(db, user), limit, offset
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
def conversation(
    conversation_id: int, db: Db, user: CurrentUser, before_id: int | None = Query(None, ge=1)
):
    return chat_history_service.detail(db, user, conversation_id, before_id)


@router.patch("/{conversation_id}", response_model=ConversationSummary)
def rename(conversation_id: int, payload: ConversationRename, db: Db, user: CurrentUser):
    return chat_history_service.rename(
        db, user, chatbot_service.scope_for(db, user), conversation_id, payload.title
    )


@router.delete("/{conversation_id}", status_code=204)
def remove(conversation_id: int, db: Db, user: CurrentUser):
    chat_history_service.remove(db, user, chatbot_service.scope_for(db, user), conversation_id)
    return Response(status_code=204)
