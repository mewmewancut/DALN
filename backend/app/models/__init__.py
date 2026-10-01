"""SQLAlchemy models exposed for metadata discovery and migrations."""

from app.models.address import UserAddress
from app.models.auth import AuthToken
from app.models.cart import Cart, CartItem
from app.models.catalog import Category, Product, ProductVariant
from app.models.inventory import Inventory, LowStockAlert
from app.models.order import Order, OrderItem, OrderStatusHistory
from app.models.preference import UserPreference, UserPreferredCategory, UserPreferredColor
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.review import Review
from app.models.shop import Shop
from app.models.supplier import Supplier
from app.models.user import User
from app.models.wishlist import WishlistItem

__all__ = [
    "Category",
    "AuthToken",
    "UserAddress",
    "Cart",
    "CartItem",
    "Inventory",
    "LowStockAlert",
    "Order",
    "OrderItem",
    "OrderStatusHistory",
    "Product",
    "ProductVariant",
    "UserPreference",
    "UserPreferredCategory",
    "UserPreferredColor",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "Review",
    "Shop",
    "Supplier",
    "User",
    "WishlistItem",
]
