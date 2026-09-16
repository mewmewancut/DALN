"""SQLAlchemy models exposed for metadata discovery and migrations."""

from app.models.catalog import Category, Product, ProductVariant
from app.models.inventory import Inventory
from app.models.shop import Shop
from app.models.user import User

__all__ = [
    "Category",
    "Inventory",
    "Product",
    "ProductVariant",
    "Shop",
    "User",
]
