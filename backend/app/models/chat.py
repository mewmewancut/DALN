"""Private analytics conversations; tokens and OAuth secrets are never persisted."""

from sqlalchemy import JSON, BigInteger, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.common import CreatedAtMixin, IdMixin, UpdatedAtMixin


class ChatConversation(Base, IdMixin, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "chat_conversations"
    __table_args__ = (
        UniqueConstraint("user_id", "space_id", "remote_id", name="uq_chat_conversation_remote"),
        Index("ix_chat_conversations_user_updated", "user_id", "updated_at"),
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("shops.id"))
    title: Mapped[str] = mapped_column(String(120))
    remote_id: Mapped[str] = mapped_column(String(36))
    space_id: Mapped[str] = mapped_column(String(32))
    principal: Mapped[str] = mapped_column(String(255))
    host: Mapped[str] = mapped_column(String(255))


class ChatSavedMessage(Base, IdMixin, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "remote_id", name="uq_chat_message_remote"),
        Index("ix_chat_messages_conversation_id", "conversation_id"),
    )
    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chat_conversations.id", ondelete="CASCADE")
    )
    remote_id: Mapped[str] = mapped_column(String(36))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[dict] = mapped_column(JSON)
