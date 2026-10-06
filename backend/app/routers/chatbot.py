from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.chatbot import ChatConfig, ChatMessage, ChatPoll, ChatQuestion
from app.services import chatbot_service

router = APIRouter(prefix="/analytics/chat", tags=["chatbot"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/config", response_model=ChatConfig)
def configuration(db: Db, user: CurrentUser):
    return chatbot_service.configuration(db, user)


@router.post("/messages", response_model=ChatMessage)
def ask(payload: ChatQuestion, db: Db, user: CurrentUser):
    return chatbot_service.ask(db, user, payload.question, payload.conversation_token)


@router.post("/messages/{message_id}", response_model=ChatMessage)
def poll(message_id: str, payload: ChatPoll, db: Db, user: CurrentUser):
    return chatbot_service.poll(db, user, message_id, payload.conversation_token)
