"""Add buyer wishlist items.

Revision ID: 20260929_0007
Revises: 20260927_0006
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_0007"
down_revision: str | None = "20260927_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wishlist_items",
        sa.Column("buyer_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["buyer_id"],
            ["users.id"],
            ondelete="CASCADE",
            name=op.f("fk_wishlist_items_buyer_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_wishlist_items_product_id_products"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wishlist_items")),
        sa.UniqueConstraint(
            "buyer_id",
            "product_id",
            name="uq_wishlist_items_buyer_product",
        ),
    )
    op.create_index(op.f("ix_wishlist_items_buyer_id"), "wishlist_items", ["buyer_id"])
    op.create_index(op.f("ix_wishlist_items_product_id"), "wishlist_items", ["product_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_wishlist_items_product_id"), table_name="wishlist_items")
    op.drop_index(op.f("ix_wishlist_items_buyer_id"), table_name="wishlist_items")
    op.drop_table("wishlist_items")
