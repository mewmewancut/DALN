"""Add ordered detail images while preserving the catalog CDC schema."""

import sqlalchemy as sa
from alembic import op

revision = "20261007_0011"
down_revision = "20261007_0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "product_detail_images",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_product_detail_images"),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name="fk_product_detail_images_product_id_products"
        ),
        sa.CheckConstraint(
            "position BETWEEN 1 AND 10", name="ck_product_detail_images_position_range"
        ),
        sa.UniqueConstraint(
            "product_id", "position", name="uq_product_detail_images_product_position"
        ),
    )


def downgrade():
    op.drop_table("product_detail_images")
