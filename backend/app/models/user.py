from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import CreatedAtMixin, IdMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from app.models.address import UserAddress
    from app.models.auth import AuthToken
    from app.models.cart import Cart
    from app.models.order import Order, OrderStatusHistory
    from app.models.review import Review
    from app.models.shop import Shop
    from app.models.wishlist import WishlistItem


class User(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('BUYER', 'SHOP_OWNER', 'ADMIN')",
            name="role",
        ),
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auth_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    shop: Mapped["Shop | None"] = relationship(back_populates="owner", uselist=False)
    cart: Mapped["Cart | None"] = relationship(back_populates="buyer", uselist=False)
    orders: Mapped[list["Order"]] = relationship(back_populates="buyer")
    order_status_changes: Mapped[list["OrderStatusHistory"]] = relationship(
        back_populates="changed_by_user"
    )
    reviews: Mapped[list["Review"]] = relationship(back_populates="buyer")
    auth_tokens: Mapped[list["AuthToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    addresses: Mapped[list["UserAddress"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    wishlist_items: Mapped[list["WishlistItem"]] = relationship(
        back_populates="buyer",
        cascade="all, delete-orphan",
    )
