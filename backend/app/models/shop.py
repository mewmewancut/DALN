from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import CreatedAtMixin, IdMixin

if TYPE_CHECKING:
    from app.models.cart import Cart
    from app.models.catalog import Product
    from app.models.inventory import Inventory, LowStockAlert
    from app.models.order import Order
    from app.models.purchase import PurchaseOrder
    from app.models.supplier import Supplier
    from app.models.user import User


class Shop(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "shops"

    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    owner: Mapped["User"] = relationship(back_populates="shop")
    products: Mapped[list["Product"]] = relationship(back_populates="shop")
    inventory_items: Mapped[list["Inventory"]] = relationship(back_populates="shop")
    suppliers: Mapped[list["Supplier"]] = relationship(back_populates="shop")
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="shop")
    carts: Mapped[list["Cart"]] = relationship(back_populates="shop")
    orders: Mapped[list["Order"]] = relationship(back_populates="shop")
    low_stock_alerts: Mapped[list["LowStockAlert"]] = relationship(
        back_populates="shop"
    )
