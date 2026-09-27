from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import CreatedAtMixin, IdMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserAddress(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "user_addresses"
    __table_args__ = (
        Index(
            "uq_user_addresses_default_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    receiver_name: Mapped[str] = mapped_column(String(255), nullable=False)
    receiver_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    province_code: Mapped[str] = mapped_column(String(2), nullable=False)
    province_name: Mapped[str] = mapped_column(String(100), nullable=False)
    commune_code: Mapped[str] = mapped_column(String(5), nullable=False)
    commune_name: Mapped[str] = mapped_column(String(100), nullable=False)
    address_detail: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    user: Mapped["User"] = relationship(back_populates="addresses")
