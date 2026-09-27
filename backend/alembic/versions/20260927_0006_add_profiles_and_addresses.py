"""Add profile fields and buyer address book.

Revision ID: 20260927_0006
Revises: 20260927_0005
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260927_0006"
down_revision: str | None = "20260927_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=20)))
    op.add_column("users", sa.Column("avatar_url", sa.Text()))
    op.create_table(
        "user_addresses",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("receiver_name", sa.String(length=255), nullable=False),
        sa.Column("receiver_phone", sa.String(length=20), nullable=False),
        sa.Column("province_code", sa.String(length=2), nullable=False),
        sa.Column("province_name", sa.String(length=100), nullable=False),
        sa.Column("commune_code", sa.String(length=5), nullable=False),
        sa.Column("commune_name", sa.String(length=100), nullable=False),
        sa.Column("address_detail", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name=op.f("fk_user_addresses_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_addresses")),
    )
    op.create_index(op.f("ix_user_addresses_user_id"), "user_addresses", ["user_id"])
    op.create_index(
        "uq_user_addresses_default_user",
        "user_addresses",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )


def downgrade() -> None:
    op.drop_index("uq_user_addresses_default_user", table_name="user_addresses")
    op.drop_index(op.f("ix_user_addresses_user_id"), table_name="user_addresses")
    op.drop_table("user_addresses")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "phone")
