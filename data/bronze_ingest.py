"""Planning E1 table allow-list and shared validation."""

import re

TABLES = (
    "users",
    "shops",
    "categories",
    "products",
    "product_variants",
    "inventory",
    "suppliers",
    "purchase_orders",
    "purchase_order_items",
    "orders",
    "order_items",
    "order_status_history",
    "reviews",
)


class IngestionError(RuntimeError):
    """A run failed validation or could not safely finish."""


def identifier(value):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", value):
        raise ValueError("Catalog/schema identifiers must contain only letters, digits, _ or -")
    return f"`{value}`"
