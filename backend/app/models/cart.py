from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import CreatedAtMixin, IdMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from app.models.catalog import ProductVariant
    from app.models.shop import Shop
    from app.models.user import User


class Cart(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "carts"

    buyer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
    )
    shop_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("shops.id"),
    )

    buyer: Mapped["User"] = relationship(back_populates="cart")
    shop: Mapped["Shop | None"] = relationship(back_populates="carts")
    items: Mapped[list["CartItem"]] = relationship(back_populates="cart")


class CartItem(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        UniqueConstraint(
            "cart_id",
            "variant_id",
            name="uq_cart_items_cart_variant",
        ),
    )

    cart_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("carts.id"),
        nullable=False,
    )
    variant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_variants.id"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    cart: Mapped["Cart"] = relationship(back_populates="items")
    variant: Mapped["ProductVariant"] = relationship(back_populates="cart_items")
