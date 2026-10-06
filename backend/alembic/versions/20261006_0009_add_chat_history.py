"""Persist private chat history.

Revision ID: 20261006_0009
Revises: 20260929_0008
"""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0009"
down_revision = "20260929_0008"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade():
    op.create_table(
        "chat_conversations", *timestamps(),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("shop_id", sa.BigInteger(), sa.ForeignKey("shops.id")),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("remote_id", sa.String(36), nullable=False),
        sa.Column("space_id", sa.String(32), nullable=False),
        sa.Column("principal", sa.String(255), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.UniqueConstraint("user_id", "space_id", "remote_id", name="uq_chat_conversation_remote"),
    )
    op.create_index("ix_chat_conversations_user_updated", "chat_conversations", ["user_id", "updated_at"])
    op.create_table(
        "chat_messages", *timestamps(),
        sa.Column("conversation_id", sa.BigInteger(), sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("remote_id", sa.String(36), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=False),
        sa.UniqueConstraint("conversation_id", "remote_id", name="uq_chat_message_remote"),
    )
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])


def downgrade():
    op.drop_table("chat_messages")
    op.drop_table("chat_conversations")
