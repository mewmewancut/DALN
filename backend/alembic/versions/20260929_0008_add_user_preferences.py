"""Add buyer shopping preferences.

Revision ID: 20260929_0008
Revises: 20260929_0007
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_0008"
down_revision: str | None = "20260929_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column("buyer_id", sa.BigInteger(), nullable=False),
        sa.Column("min_price", sa.Numeric(precision=12, scale=0)),
        sa.Column("max_price", sa.Numeric(precision=12, scale=0)),
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
        sa.CheckConstraint(
            "max_price IS NULL OR max_price >= 0",
            name=op.f("ck_user_preferences_max_price_non_negative"),
        ),
        sa.CheckConstraint(
            "min_price IS NULL OR min_price >= 0",
            name=op.f("ck_user_preferences_min_price_non_negative"),
        ),
        sa.CheckConstraint(
            "min_price IS NULL OR max_price IS NULL OR min_price <= max_price",
            name=op.f("ck_user_preferences_price_range_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["buyer_id"],
            ["users.id"],
            ondelete="CASCADE",
            name=op.f("fk_user_preferences_buyer_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_preferences")),
        sa.UniqueConstraint("buyer_id", name=op.f("uq_user_preferences_buyer_id")),
    )
    op.create_table(
        "user_preferred_categories",
        sa.Column("preference_id", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_user_preferred_categories_category_id_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["preference_id"],
            ["user_preferences.id"],
            ondelete="CASCADE",
            name=op.f("fk_user_preferred_categories_preference_id_user_preferences"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_preferred_categories")),
        sa.UniqueConstraint(
            "preference_id",
            "category_id",
            name="uq_user_preferred_categories_preference_category",
        ),
    )
    op.create_index(
        op.f("ix_user_preferred_categories_category_id"),
        "user_preferred_categories",
        ["category_id"],
    )
    op.create_index(
        op.f("ix_user_preferred_categories_preference_id"),
        "user_preferred_categories",
        ["preference_id"],
    )
    op.create_table(
        "user_preferred_colors",
        sa.Column("preference_id", sa.BigInteger(), nullable=False),
        sa.Column("color", sa.String(length=30), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["preference_id"],
            ["user_preferences.id"],
            ondelete="CASCADE",
            name=op.f("fk_user_preferred_colors_preference_id_user_preferences"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_preferred_colors")),
        sa.UniqueConstraint(
            "preference_id",
            "color",
            name="uq_user_preferred_colors_preference_color",
        ),
    )
    op.create_index(
        op.f("ix_user_preferred_colors_preference_id"),
        "user_preferred_colors",
        ["preference_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_preferred_colors_preference_id"),
        table_name="user_preferred_colors",
    )
    op.drop_table("user_preferred_colors")
    op.drop_index(
        op.f("ix_user_preferred_categories_preference_id"),
        table_name="user_preferred_categories",
    )
    op.drop_index(
        op.f("ix_user_preferred_categories_category_id"),
        table_name="user_preferred_categories",
    )
    op.drop_table("user_preferred_categories")
    op.drop_table("user_preferences")
