"""Planning E3 aggregates; use Silver dates and aggregate facts before dimension joins."""

GOLD_TABLES = (
    "revenue_daily",
    "revenue_monthly",
    "orders_summary_daily",
    "top_products",
    "low_stock_current",
    "shop_performance",
)


def build_query(table, silver, gold):
    if table == "revenue_daily":
        return f"""
            WITH revenue AS (
                SELECT delivered_date_vn AS date, shop_id,
                       SUM(total_amount) AS revenue, COUNT(*) AS delivered_orders
                FROM {silver}.fact_orders WHERE status = 'DELIVERED'
                GROUP BY delivered_date_vn, shop_id
            )
            SELECT r.date, r.shop_id, s.name AS shop_name, r.revenue, r.delivered_orders
            FROM revenue r LEFT JOIN {silver}.dim_shops s ON r.shop_id = s.id
        """
    if table == "revenue_monthly":
        return f"""
            SELECT trunc(date, 'MONTH') AS month, shop_id, shop_name,
                   SUM(revenue) AS revenue, SUM(delivered_orders) AS delivered_orders
            FROM {gold}.revenue_daily GROUP BY trunc(date, 'MONTH'), shop_id, shop_name
        """
    if table == "top_products":
        return f"""
            WITH sales AS (
                SELECT i.shop_id, v.product_id, SUM(i.quantity) AS total_quantity_sold,
                       SUM(i.unit_price * i.quantity) AS total_revenue
                FROM {silver}.fact_order_items i
                JOIN {silver}.dim_variants v ON i.variant_id = v.id
                WHERE i.status = 'DELIVERED'
                GROUP BY i.shop_id, v.product_id
            ), ratings AS (
                SELECT product_id, AVG(rating) AS avg_rating
                FROM {silver}.fact_reviews GROUP BY product_id
            )
            SELECT s.shop_id, s.product_id, p.name AS product_name,
                   s.total_quantity_sold, s.total_revenue, r.avg_rating
            FROM sales s LEFT JOIN {silver}.dim_products p ON s.product_id = p.id
            LEFT JOIN ratings r ON s.product_id = r.product_id
        """
    if table == "orders_summary_daily":
        return f"""
            WITH created AS (
                SELECT created_date_vn AS date, shop_id, COUNT(*) AS total_orders,
                       COUNT(CASE WHEN status = 'CANCELLED' THEN 1 END) AS cancelled,
                       COUNT(CASE WHEN status = 'PENDING' THEN 1 END) AS pending,
                       COUNT(CASE WHEN status = 'CONFIRMED' THEN 1 END) AS confirmed,
                       COUNT(CASE WHEN status = 'PREPARING' THEN 1 END) AS preparing,
                       COUNT(CASE WHEN status = 'SHIPPING' THEN 1 END) AS shipping
                FROM {silver}.fact_orders GROUP BY created_date_vn, shop_id
            )
            SELECT COALESCE(c.date, r.date) AS date, COALESCE(c.shop_id, r.shop_id) AS shop_id,
                   COALESCE(c.total_orders, 0) AS total_orders,
                   COALESCE(r.delivered_orders, 0) AS delivered,
                   COALESCE(c.cancelled, 0) AS cancelled,
                   c.cancelled / NULLIF(c.total_orders, 0) AS cancel_rate,
                   r.revenue / NULLIF(r.delivered_orders, 0) AS aov,
                   COALESCE(c.pending, 0) AS pending,
                   COALESCE(c.confirmed, 0) AS confirmed,
                   COALESCE(c.preparing, 0) AS preparing,
                   COALESCE(c.shipping, 0) AS shipping
            FROM created c FULL OUTER JOIN {gold}.revenue_daily r
                ON c.date = r.date AND c.shop_id = r.shop_id
        """
    if table == "low_stock_current":
        return f"""
            SELECT i.shop_id, s.name AS shop_name, p.name AS product_name,
                   i.size, i.color, i.quantity, i.threshold
            FROM {silver}.fact_inventory i
            LEFT JOIN {silver}.dim_shops s ON i.shop_id = s.id
            LEFT JOIN {silver}.dim_products p ON i.product_id = p.id
            WHERE i.is_low
        """
    if table == "shop_performance":
        return f"""
            WITH orders AS (
                SELECT shop_id, COUNT(*) AS total_orders,
                       COUNT(CASE WHEN status = 'CANCELLED' THEN 1 END) AS cancelled,
                       COUNT(CASE WHEN status = 'DELIVERED' THEN 1 END) AS delivered,
                       SUM(CASE WHEN status = 'DELIVERED' THEN total_amount ELSE 0 END) AS revenue
                FROM {silver}.fact_orders GROUP BY shop_id
            ), products AS (
                SELECT shop_id, COUNT(*) AS product_count
                FROM {silver}.dim_products GROUP BY shop_id
            ), shops AS (
                SELECT id AS shop_id FROM {silver}.dim_shops
                UNION SELECT shop_id FROM orders
                UNION SELECT shop_id FROM products
            )
            SELECT s.shop_id, d.name AS shop_name, COALESCE(o.revenue, 0) AS revenue,
                   COALESCE(o.total_orders, 0) AS total_orders,
                   o.cancelled / NULLIF(o.total_orders, 0) AS cancel_rate,
                   o.revenue / NULLIF(o.delivered, 0) AS aov,
                   COALESCE(p.product_count, 0) AS product_count
            FROM shops s LEFT JOIN {silver}.dim_shops d ON s.shop_id = d.id
            LEFT JOIN orders o ON s.shop_id = o.shop_id
            LEFT JOIN products p ON s.shop_id = p.shop_id
        """
    raise ValueError("Table is outside Planning E3")
