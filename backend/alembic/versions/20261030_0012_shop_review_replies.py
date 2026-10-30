"""Add shop review replies and read status.

Revision ID: 20261030_0012
Revises: 20261007_0011
"""

from alembic import op
import sqlalchemy as sa

revision = "20261030_0012"
down_revision = "20261007_0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reviews",
        sa.Column("shop_reply", sa.Text(), nullable=True),
    )
    op.add_column(
        "reviews",
        sa.Column("shop_replied_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "reviews",
        sa.Column("shop_review_read_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("reviews", "shop_review_read_at")
    op.drop_column("reviews", "shop_replied_at")
    op.drop_column("reviews", "shop_reply")