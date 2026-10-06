from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest

from gold_queries import GOLD_TABLES, build_query
from gold_transform import GoldTransform

SCHEMAS = {
    "dim_shops": "id BIGINT, name STRING, is_active BOOLEAN",
    "dim_products": "id BIGINT, shop_id BIGINT, name STRING, is_active BOOLEAN",
    "dim_variants": "id BIGINT, product_id BIGINT",
    "fact_orders": (
        "id BIGINT, shop_id BIGINT, status STRING, total_amount DECIMAL(12,0), "
        "created_date_vn DATE, delivered_date_vn DATE"
    ),
    "fact_order_items": (
        "id BIGINT, variant_id BIGINT, shop_id BIGINT, status STRING, "
        "unit_price DECIMAL(12,0), quantity INT"
    ),
    "fact_inventory": (
        "id BIGINT, shop_id BIGINT, product_id BIGINT, size STRING, color STRING, "
        "quantity INT, threshold INT, is_low BOOLEAN"
    ),
    "fact_reviews": "id BIGINT, product_id BIGINT, rating INT",
}


@pytest.fixture
def gold_sql(sql):
    sql.execute("CREATE DATABASE silver")
    sql.execute("CREATE DATABASE gold")
    for table, schema in SCHEMAS.items():
        sql.execute(f"CREATE TABLE silver.{table} ({schema}) USING DELTA")
    yield sql
    sql.execute("SET TIME ZONE 'UTC'")
    sql.execute("DROP DATABASE gold CASCADE")
    sql.execute("DROP DATABASE silver CASCADE")


def transform(sql):
    return GoldTransform(sql, "spark_catalog", report=Mock())


def rows(sql, table, order):
    return sql.execute(f"SELECT * FROM gold.{table} ORDER BY {order}")


def seed(sql):
    sql.execute(
        "INSERT INTO silver.dim_shops VALUES (1, 'Hidden', false), (2, 'Shop', true), "
        "(3, 'Empty', true)"
    )
    sql.execute(
        "INSERT INTO silver.dim_products VALUES (1, 1, 'Current name', false), "
        "(2, 1, 'Unsold', true), (3, 2, 'Bag', true)"
    )
    sql.execute("INSERT INTO silver.dim_variants VALUES (1, 1), (2, 1), (3, 3)")
    sql.execute("""
        INSERT INTO silver.fact_orders VALUES
        (1, 1, 'DELIVERED', 200, DATE '2026-09-30', DATE '2026-10-01'),
        (2, 1, 'DELIVERED', 300, DATE '2026-10-01', DATE '2026-10-02'),
        (3, 1, 'CANCELLED', 900, DATE '2026-10-01', NULL),
        (4, 2, 'DELIVERED', 800, DATE '2026-09-30', DATE '2026-09-30'),
        (5, 2, 'PENDING', 100, DATE '2026-10-01', NULL),
        (6, 4, 'DELIVERED', 50, DATE '2026-10-01', DATE '2026-10-01'),
        (7, 1, 'DELIVERED', 100, DATE '2026-10-01', DATE '2026-10-01')
    """)
    sql.execute("""
        INSERT INTO silver.fact_order_items VALUES
        (1, 1, 1, 'DELIVERED', 100, 2), (2, 2, 1, 'DELIVERED', 150, 2),
        (3, 1, 1, 'CANCELLED', 900, 1), (4, 3, 2, 'DELIVERED', 800, 1),
        (5, 1, 1, 'DELIVERED', 100, 1)
    """)
    sql.execute("INSERT INTO silver.fact_reviews VALUES (1, 1, 1), (2, 1, 5), (3, 2, 2)")
    sql.execute("""
        INSERT INTO silver.fact_inventory VALUES
        (1, 1, 1, 'XL', 'Blue', 4, 5, true),
        (2, 1, 1, 'S', 'Red', 5, 5, false),
        (3, 2, 3, 'M', 'Black', 0, 2, true)
    """)


def test_six_tables_match_c9_without_review_variant_or_product_fanout(gold_sql):
    sql = gold_sql
    seed(sql)
    sql.execute("SET TIME ZONE 'America/Los_Angeles'")
    assert transform(sql).run() == dict(zip(GOLD_TABLES, (4, 3, 6, 2, 2, 4), strict=True))
    daily = rows(sql, "revenue_daily", "shop_id, date")
    assert [(r.date, r.shop_id, r.revenue, r.delivered_orders) for r in daily] == [
        (date(2026, 10, 1), 1, Decimal(300), 2),
        (date(2026, 10, 2), 1, Decimal(300), 1),
        (date(2026, 9, 30), 2, Decimal(800), 1),
        (date(2026, 10, 1), 4, Decimal(50), 1),
    ]
    assert daily[0].shop_name == "Hidden" and daily[-1].shop_name is None
    monthly = rows(sql, "revenue_monthly", "shop_id, month")
    assert [(r.month, r.revenue, r.delivered_orders) for r in monthly] == [
        (date(2026, 10, 1), Decimal(600), 3),
        (date(2026, 9, 1), Decimal(800), 1),
        (date(2026, 10, 1), Decimal(50), 1),
    ]
    summary = rows(sql, "orders_summary_daily", "shop_id, date")
    assert [
        (r.date, r.shop_id, r.total_orders, r.delivered, r.cancelled, r.cancel_rate, r.aov)
        for r in summary
    ] == [
        (date(2026, 9, 30), 1, 1, 0, 0, 0, None),
        (date(2026, 10, 1), 1, 3, 2, 1, 1 / 3, Decimal(150)),
        (date(2026, 10, 2), 1, 0, 1, 0, None, Decimal(300)),
        (date(2026, 9, 30), 2, 1, 1, 0, 0, Decimal(800)),
        (date(2026, 10, 1), 2, 1, 0, 0, 0, None),
        (date(2026, 10, 1), 4, 1, 1, 0, 0, Decimal(50)),
    ]
    top = rows(sql, "top_products", "shop_id, product_id")
    assert [
        (r.product_id, r.product_name, r.total_quantity_sold, r.total_revenue, r.avg_rating)
        for r in top
    ] == [
        (1, "Current name", 5, Decimal(600), 3),
        (3, "Bag", 1, Decimal(800), None),
    ]
    stock = rows(sql, "low_stock_current", "shop_id, size")
    assert [
        (r.shop_id, r.product_name, r.size, r.color, r.quantity, r.threshold) for r in stock
    ] == [(1, "Current name", "XL", "Blue", 4, 5), (2, "Bag", "M", "Black", 0, 2)]
    shops = rows(sql, "shop_performance", "shop_id")
    assert [
        (r.shop_id, r.revenue, r.total_orders, r.cancel_rate, r.aov, r.product_count) for r in shops
    ] == [
        (1, Decimal(600), 4, 0.25, Decimal(200), 2),
        (2, Decimal(800), 2, 0, Decimal(800), 1),
        (3, Decimal(0), 0, None, None, 0),
        (4, Decimal(50), 1, 0, Decimal(50), 0),
    ]
    # Product catalog prices are absent; all sales revenue comes from item snapshots.
    assert sum(r.revenue for r in daily) == Decimal(1450)
    assert sum(r.total_orders for r in summary) == 7


def test_overwrite_is_repeatable_and_removes_old_groups_even_when_sources_empty(gold_sql):
    sql = gold_sql
    seed(sql)
    runner = transform(sql)
    first = runner.run()
    snapshot = {table: sql.execute(f"SELECT * FROM gold.{table}") for table in GOLD_TABLES}
    assert runner.run() == first
    for table in GOLD_TABLES:
        assert sql.execute(f"SELECT * FROM gold.{table}") == snapshot[table]
    # Removing delivered sales must remove revenue/top groups, while pending/cancelled
    # orders remain counted. Shops with orders but no deliveries have NULL AOV.
    sql.execute("DELETE FROM silver.fact_orders WHERE status = 'DELIVERED'")
    sql.execute("DELETE FROM silver.fact_order_items WHERE status = 'DELIVERED'")
    sql.execute("UPDATE silver.fact_inventory SET quantity = threshold, is_low = false")
    assert runner.run() == dict(zip(GOLD_TABLES, (0, 0, 2, 0, 0, 3), strict=True))
    shops = rows(sql, "shop_performance", "shop_id")
    assert [(r.total_orders, r.revenue, r.cancel_rate, r.aov) for r in shops] == [
        (1, Decimal(0), 1, None),
        (1, Decimal(0), 0, None),
        (0, Decimal(0), None, None),
    ]
    for table in SCHEMAS:
        sql.execute(f"DELETE FROM silver.{table}")
    assert runner.run() == dict.fromkeys(GOLD_TABLES, 0)
    assert all(not sql.execute(f"SELECT * FROM gold.{table}") for table in GOLD_TABLES)


@pytest.mark.parametrize(
    "created,delivered", [("NULL", "DATE '2026-10-01'"), ("DATE '2026-10-01'", "NULL")]
)
def test_missing_reporting_dates_fail_before_any_gold_table_is_written(
    gold_sql, created, delivered
):
    sql = gold_sql
    sql.execute(
        f"INSERT INTO silver.fact_orders VALUES (1, 1, 'DELIVERED', 100, {created}, {delivered})"
    )
    with pytest.raises(ValueError, match="Gold requires"):
        transform(sql).run()
    assert not sql.execute("SHOW TABLES IN gold")


def test_unknown_table_and_unsafe_catalog_are_rejected():
    with pytest.raises(ValueError):
        build_query("unexpected", "silver", "gold")
    with pytest.raises(ValueError):
        GoldTransform(Mock(), "fashion; DROP TABLE orders")


def test_failed_overwrite_stops_later_tables_and_reports_no_success():
    sql, report = Mock(), Mock()
    sql.execute.side_effect = [[], [[0]], [], RuntimeError("overwrite failed")]
    with pytest.raises(RuntimeError, match="overwrite failed"):
        GoldTransform(sql, report=report).run()
    assert not any("DONE" in call.args[0] for call in report.call_args_list)
    assert not any("revenue_monthly" in call.args[0] for call in sql.execute.call_args_list)
