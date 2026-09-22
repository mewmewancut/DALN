"""Add timestamps to mutable operational tables.

Revision ID: 20260922_0003
Revises: 20260922_0002
Create Date: 2026-09-22
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260922_0003"
down_revision: str | None = "20260922_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MUTABLE_TABLES = (
    "users",
    "shops",
    "categories",
    "product_variants",
    "suppliers",
    "purchase_orders",
    "carts",
    "cart_items",
    "low_stock_alerts",
)


def upgrade() -> None:
    for table_name in MUTABLE_TABLES:
        op.add_column(
            table_name,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    for table_name in reversed(MUTABLE_TABLES):
        op.drop_column(table_name, "updated_at")
