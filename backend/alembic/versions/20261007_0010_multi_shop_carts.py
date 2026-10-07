"""Support multi-shop carts and idempotent guest imports.

Revision ID: 20261007_0010
Revises: 20261006_0009
"""
import sqlalchemy as sa
from alembic import op

revision = "20261007_0010"
down_revision = "20261006_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("fk_carts_shop_id_shops", "carts", type_="foreignkey")
    op.drop_column("carts", "shop_id")
    op.create_table(
        "cart_merges",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("buyer_id", sa.BigInteger(), nullable=False),
        sa.Column("merge_id", sa.String(36), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_cart_merges"),
        sa.ForeignKeyConstraint(["buyer_id"], ["users.id"], ondelete="CASCADE", name="fk_cart_merges_buyer_id_users"),
        sa.UniqueConstraint("buyer_id", "merge_id", name="uq_cart_merges_buyer_merge"),
    )


def downgrade():
    mixed = op.get_bind().scalar(sa.text("""
        SELECT COUNT(*) FROM (
            SELECT ci.cart_id FROM cart_items ci
            JOIN product_variants v ON v.id = ci.variant_id
            JOIN products p ON p.id = v.product_id
            GROUP BY ci.cart_id HAVING COUNT(DISTINCT p.shop_id) > 1
        ) mixed
    """))
    if mixed:
        raise RuntimeError("Không thể downgrade khi còn giỏ nhiều shop; giữ nguyên giỏ trước khi hạ phiên bản")
    op.add_column("carts", sa.Column("shop_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_carts_shop_id_shops", "carts", "shops", ["shop_id"], ["id"])
    op.execute(sa.text("""
        UPDATE carts SET shop_id = (
            SELECT MIN(p.shop_id) FROM cart_items ci
            JOIN product_variants v ON v.id = ci.variant_id
            JOIN products p ON p.id = v.product_id WHERE ci.cart_id = carts.id
        )
    """))
    op.drop_table("cart_merges")
