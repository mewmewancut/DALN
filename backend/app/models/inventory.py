from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Integer, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import CreatedAtMixin, IdMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from app.models.catalog import ProductVariant
    from app.models.shop import Shop


class Inventory(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "inventory"
    __table_args__ = (CheckConstraint("quantity >= 0", name="quantity_non_negative"),)

    variant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_variants.id"),
        nullable=False,
        unique=True,
    )
    shop_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shops.id"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        server_default="5",
    )

    variant: Mapped["ProductVariant"] = relationship(back_populates="inventory")
    shop: Mapped["Shop"] = relationship(back_populates="inventory_items")


class LowStockAlert(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "low_stock_alerts"

    variant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_variants.id"),
        nullable=False,
    )
    shop_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shops.id"),
        nullable=False,
    )
    quantity_at_alert: Mapped[int] = mapped_column(Integer, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    variant: Mapped["ProductVariant"] = relationship(back_populates="low_stock_alerts")
    shop: Mapped["Shop"] = relationship(back_populates="low_stock_alerts")
