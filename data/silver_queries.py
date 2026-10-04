"""Planning E2 projections; timestamps remain UTC, only analytical dates use UTC+7."""

from bronze_ingest import identifier

SILVER_TABLES = (
    "dim_shops",
    "dim_products",
    "dim_variants",
    "fact_orders",
    "fact_order_items",
    "fact_inventory",
    "fact_reviews",
)
ORDER_STATUSES = ("PENDING", "CONFIRMED", "PREPARING", "SHIPPING", "DELIVERED", "CANCELLED")
STATUS_SQL = ", ".join(f"'{status}'" for status in ORDER_STATUSES)


def vn_date(column):
    # TIMESTAMP is an instant: epoch arithmetic avoids a second offset from the SQL session.
    # UTC TIMESTAMP_NTZ is a wall clock: date extraction must not interpret it in session TZ.
    return (
        f"CASE WHEN typeof({column}) = 'timestamp_ntz' THEN "
        f"CAST(CAST({column} AS TIMESTAMP_NTZ) + INTERVAL 7 HOURS AS DATE) ELSE "
        "date_add(DATE '1970-01-01', "
        f"CAST(FLOOR((unix_micros(CAST({column} AS TIMESTAMP_LTZ)) + 25200000000) "
        "/ 86400000000) AS INT)) END"
    )


def projection(alias, columns, replacements=None):
    replacements = replacements or {}
    return ", ".join(
        f"{replacements[column]} AS {identifier(column)}"
        if column in replacements
        else f"{alias}.{identifier(column)}"
        for column in columns
    )


def build_query(table, bronze, silver, columns, excluded_shop_ids):
    """Return a projection and an optional validity predicate over its materialized rows."""
    if table == "dim_shops":
        exclusion = (
            f" WHERE s.id NOT IN ({', '.join(map(str, excluded_shop_ids))})"
            if excluded_shop_ids
            else ""
        )
        return (
            f"SELECT s.*, u.full_name AS owner_name FROM {bronze}.shops s "
            f"LEFT JOIN {bronze}.users u ON s.owner_id = u.id{exclusion}",
            None,
        )
    if table == "dim_products":
        return (
            f"SELECT p.*, c.name AS category_name, s.name AS shop_name FROM {bronze}.products p "
            f"LEFT JOIN {bronze}.categories c ON p.category_id = c.id "
            f"LEFT JOIN {bronze}.shops s ON p.shop_id = s.id",
            None,
        )
    if table == "dim_variants":
        fields = projection(
            "v",
            columns("product_variants"),
            {"size": "UPPER(TRIM(v.size))", "color": "INITCAP(LOWER(TRIM(v.color)))"},
        )
        return f"SELECT {fields} FROM {bronze}.product_variants v", None
    if table == "fact_orders":
        fields = projection("o", columns("orders"), {"status": "UPPER(TRIM(o.status))"})
        return (
            f"SELECT {fields}, {vn_date('o.created_at')} AS created_date_vn, "
            f"{vn_date('o.delivered_at')} AS delivered_date_vn FROM {bronze}.orders o",
            f"status IN ({STATUS_SQL}) AND total_amount > 0",
        )
    if table == "fact_order_items":
        return (
            "SELECT i.*, o.status, o.shop_id, o.created_date_vn, o.delivered_date_vn "
            f"FROM {bronze}.order_items i JOIN {silver}.fact_orders o ON i.order_id = o.id",
            None,
        )
    if table == "fact_inventory":
        return (
            "SELECT i.*, v.product_id, v.size, v.color, v.sku, "
            "i.low_stock_threshold AS threshold, i.quantity < i.low_stock_threshold AS is_low "
            f"FROM {bronze}.inventory i JOIN {silver}.dim_variants v ON i.variant_id = v.id",
            None,
        )
    if table == "fact_reviews":
        return f"SELECT r.* FROM {bronze}.reviews r", "rating BETWEEN 1 AND 5"
    raise ValueError("Table is outside Planning E2")
