from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import CreatedAtMixin, IdMixin

if TYPE_CHECKING:
    from app.models.catalog import Product


class ProductDetailImage(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "product_detail_images"
    __table_args__ = (
        CheckConstraint("position BETWEEN 1 AND 10", name="position_range"),
        UniqueConstraint(
            "product_id", "position", name="uq_product_detail_images_product_position"
        ),
    )

    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    product: Mapped["Product"] = relationship(back_populates="detail_images")
