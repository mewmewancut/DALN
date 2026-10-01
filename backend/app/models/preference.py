from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import CreatedAtMixin, IdMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from app.models.catalog import Category
    from app.models.user import User


class UserPreference(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint("min_price IS NULL OR min_price >= 0", name="min_price_non_negative"),
        CheckConstraint("max_price IS NULL OR max_price >= 0", name="max_price_non_negative"),
        CheckConstraint(
            "min_price IS NULL OR max_price IS NULL OR min_price <= max_price",
            name="price_range_valid",
        ),
    )

    buyer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    min_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 0))
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 0))

    buyer: Mapped["User"] = relationship(back_populates="preferences")
    categories: Mapped[list["UserPreferredCategory"]] = relationship(
        back_populates="preference",
        cascade="all, delete-orphan",
    )
    colors: Mapped[list["UserPreferredColor"]] = relationship(
        back_populates="preference",
        cascade="all, delete-orphan",
    )


class UserPreferredCategory(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "user_preferred_categories"
    __table_args__ = (
        UniqueConstraint(
            "preference_id",
            "category_id",
            name="uq_user_preferred_categories_preference_category",
        ),
    )

    preference_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_preferences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("categories.id"),
        nullable=False,
        index=True,
    )

    preference: Mapped["UserPreference"] = relationship(back_populates="categories")
    category: Mapped["Category"] = relationship()


class UserPreferredColor(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "user_preferred_colors"
    __table_args__ = (
        UniqueConstraint(
            "preference_id",
            "color",
            name="uq_user_preferred_colors_preference_color",
        ),
    )

    preference_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_preferences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    color: Mapped[str] = mapped_column(String(30), nullable=False)

    preference: Mapped["UserPreference"] = relationship(back_populates="colors")
