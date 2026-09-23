"""Enforce at most one open low-stock alert per variant at the DB level.

Revision ID: 20260923_0004
Revises: 20260922_0003
Create Date: 2026-09-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260923_0004"
down_revision: str | None = "20260922_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_low_stock_alerts_open_variant",
        "low_stock_alerts",
        ["variant_id"],
        unique=True,
        postgresql_where="NOT is_resolved",
    )


def downgrade() -> None:
    op.drop_index("uq_low_stock_alerts_open_variant", table_name="low_stock_alerts")
