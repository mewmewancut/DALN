from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import CreatedAtMixin, IdMixin

if TYPE_CHECKING:
    from app.models.catalog import Product
    from app.models.user import User


class WishlistItem(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "wishlist_items"
    __table_args__ = (
        UniqueConstraint(
            "buyer_id",
            "product_id",
            name="uq_wishlist_items_buyer_product",
        ),
    )

    buyer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id"),
        nullable=False,
        index=True,
    )

    buyer: Mapped["User"] = relationship(back_populates="wishlist_items")
    product: Mapped["Product"] = relationship(back_populates="wishlist_items")
