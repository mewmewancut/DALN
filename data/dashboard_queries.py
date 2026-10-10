"""Gold-only datasets for Planning E5; preserve C9 reporting dates and denominators."""

from bronze_ingest import identifier


def queries(catalog="fashion"):
    gold = f"{identifier(catalog)}.`gold`"
    summary = f"{gold}.orders_summary_daily"
    status_counts = {
        "PENDING": "pending",
        "CONFIRMED": "confirmed",
        "PREPARING": "preparing",
        "SHIPPING": "shipping",
        # delivered is counted by DELIVERY date in E3. The remainder below
        # counts currently delivered orders by CREATION date for this chart.
        "DELIVERED": "total_orders - pending - confirmed - preparing - shipping - cancelled",
        "CANCELLED": "cancelled",
    }
    return {
        "daily": f"""
            WITH revenue AS (
                SELECT date, SUM(revenue) AS revenue, SUM(delivered_orders) AS delivered_orders
                FROM {gold}.revenue_daily GROUP BY date
            ), created AS (
                SELECT date, SUM(total_orders) AS total_orders, SUM(cancelled) AS cancelled
                FROM {summary} GROUP BY date
            )
            SELECT COALESCE(r.date, c.date) AS date, COALESCE(r.revenue, 0) AS revenue,
                   COALESCE(r.delivered_orders, 0) AS delivered_orders,
                   COALESCE(c.total_orders, 0) AS total_orders,
                   COALESCE(c.cancelled, 0) AS cancelled
            FROM revenue r FULL OUTER JOIN created c ON r.date = c.date
        """,
        "shops": "SELECT shop_id, shop_name, CONCAT(COALESCE(shop_name, 'Shop'), ' (#', "
        "CAST(shop_id AS STRING), ')') "
        f"AS shop_label, revenue FROM {gold}.shop_performance "
        "ORDER BY revenue DESC, shop_id LIMIT 10",
        "products": "SELECT shop_id, product_id, product_name, "
        "CONCAT(COALESCE(product_name, 'Sản phẩm'), ' (#', CAST(product_id AS STRING), ', shop ', "
        "CAST(shop_id AS STRING), ')') AS product_label, total_quantity_sold "
        f"FROM {gold}.top_products ORDER BY total_quantity_sold DESC, shop_id, product_id LIMIT 10",
        "stock": f"SELECT shop_id, shop_name, product_name, size, color, quantity, threshold "
        f"FROM {gold}.low_stock_current ORDER BY shop_id, product_name, size, color",
        "statuses": " UNION ALL ".join(
            f"SELECT date, '{status}' AS status, SUM({expression}) AS order_count "
            f"FROM {summary} GROUP BY date"
            for status, expression in status_counts.items()
        ),
    }


def period_metrics(daily, start, end):
    """Caller supplies SQL date literals validated at its boundary."""
    return (
        "SELECT COALESCE(SUM(revenue),0), COALESCE(SUM(total_orders),0), "
        "COALESCE(SUM(cancelled),0), COALESCE(SUM(delivered_orders),0), "
        "SUM(cancelled)/NULLIF(SUM(total_orders),0), "
        "SUM(revenue)/NULLIF(SUM(delivered_orders),0) "
        f"FROM ({daily}) WHERE date BETWEEN {start} AND {end}"
    )
