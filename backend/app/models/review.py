from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import CreatedAtMixin, IdMixin

if TYPE_CHECKING:
    from app.models.catalog import Product
    from app.models.order import OrderItem
    from app.models.user import User


class Review(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),)

    order_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("order_items.id"),
        nullable=False,
        unique=True,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id"),
        nullable=False,
    )
    buyer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    order_item: Mapped["OrderItem"] = relationship(back_populates="review")
    product: Mapped["Product"] = relationship(back_populates="reviews")
    buyer: Mapped["User"] = relationship(back_populates="reviews")
