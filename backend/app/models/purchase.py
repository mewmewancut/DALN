from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import CreatedAtMixin, IdMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from app.models.catalog import ProductVariant
    from app.models.shop import Shop
    from app.models.supplier import Supplier


class PurchaseOrder(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'ORDERED', 'RECEIVED', 'CANCELLED')",
            name="status",
        ),
    )

    shop_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shops.id"),
        nullable=False,
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("suppliers.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="DRAFT",
        server_default="DRAFT",
    )
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)

    shop: Mapped["Shop"] = relationship(back_populates="purchase_orders")
    supplier: Mapped["Supplier"] = relationship(back_populates="purchase_orders")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order"
    )


class PurchaseOrderItem(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "purchase_order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        UniqueConstraint(
            "purchase_order_id",
            "variant_id",
            name="uq_purchase_order_items_purchase_order_variant",
        ),
    )

    purchase_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("purchase_orders.id"),
        nullable=False,
    )
    variant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_variants.id"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 0), nullable=False)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="items")
    variant: Mapped["ProductVariant"] = relationship(
        back_populates="purchase_order_items"
    )
