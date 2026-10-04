from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest

from silver_queries import ORDER_STATUSES, SILVER_TABLES, vn_date
from silver_transform import SilverTransform, TransformationError

SCHEMAS = {
    "users": "id BIGINT, full_name STRING",
    "shops": "id BIGINT, owner_id BIGINT, name STRING, is_active BOOLEAN",
    "categories": "id BIGINT, name STRING",
    "products": "id BIGINT, shop_id BIGINT, category_id BIGINT, name STRING, is_active BOOLEAN",
    "product_variants": (
        "id BIGINT, product_id BIGINT, size STRING, color STRING, price DECIMAL(12,2), "
        "sku STRING, is_active BOOLEAN"
    ),
    "orders": (
        "id BIGINT, shop_id BIGINT, status STRING, total_amount DECIMAL(12,2), "
        "created_at TIMESTAMP, delivered_at TIMESTAMP"
    ),
    "order_items": (
        "id BIGINT, order_id BIGINT, variant_id BIGINT, product_name STRING, size STRING, "
        "color STRING, unit_price DECIMAL(12,2), quantity INT"
    ),
    "inventory": (
        "id BIGINT, shop_id BIGINT, variant_id BIGINT, quantity INT, low_stock_threshold INT"
    ),
    "reviews": "id BIGINT, product_id BIGINT, rating INT, comment STRING",
}


@pytest.fixture
def silver_sql(sql):
    sql.execute("CREATE DATABASE silver")
    for table, schema in SCHEMAS.items():
        sql.execute(f"CREATE TABLE bronze.{table} ({schema}) USING DELTA")
    yield sql
    sql.execute("SET TIME ZONE 'UTC'")
    sql.execute("DROP DATABASE silver CASCADE")


def transformer(sql, excluded=(), report=None):
    return SilverTransform(sql, "spark_catalog", excluded, report=report or Mock())


def no_stages(sql):
    assert not any(
        row.tableName.startswith("_silver_") for row in sql.execute("SHOW TABLES IN silver")
    )


def seed(sql):
    sql.execute("INSERT INTO bronze.users VALUES (1, 'Owner'), (2, 'Test owner')")
    sql.execute("INSERT INTO bronze.shops VALUES (1, 1, 'Shop', false), (2, 2, 'Test', true)")
    sql.execute("INSERT INTO bronze.categories VALUES (1, 'Clothing')")
    sql.execute("INSERT INTO bronze.products VALUES (1, 1, 1, 'Hidden shirt', false)")
    sql.execute(
        "INSERT INTO bronze.product_variants VALUES "
        "(1, 1, ' xl ', ' DARK bLUE ', 125.50, 'shirt-xl', false), "
        "(2, 1, ' s ', ' RED ', 50, 'shirt-s', true)"
    )
    sql.execute("INSERT INTO bronze.inventory VALUES (1, 1, 1, 4, 5), (2, 1, 2, 5, 5)")
    statuses = (*ORDER_STATUSES, "UNKNOWN", None, "DELIVERED", "DELIVERED", "DELIVERED")
    amounts = ["125.50"] * 8 + ["0", "-1", "NULL"]
    for key, (status, amount) in enumerate(zip(statuses, amounts, strict=True), 1):
        status_value = "NULL" if status is None else f"' {status.lower()} '"
        sql.execute(
            f"INSERT INTO bronze.orders VALUES ({key}, 1, {status_value}, {amount}, "
            "TIMESTAMP '2026-09-30 17:00:00Z', "
            "TIMESTAMP '2026-10-01 16:59:59.999999Z')"
        )
        sql.execute(
            f"INSERT INTO bronze.order_items VALUES ({key}, {key}, 1, 'Old name', 'OLD', "
            "'old color', 99.99, 2)"
        )
    sql.execute(
        "INSERT INTO bronze.reviews VALUES "
        "(1, 1, 1, 'ok'), (2, 1, 5, 'ok'), (3, 1, 0, 'bad'), "
        "(4, 1, 6, 'bad'), (5, 1, NULL, 'bad')"
    )


def test_all_seven_tables_clean_merge_and_refresh_without_stale_facts(silver_sql):
    sql = silver_sql
    seed(sql)
    # The warehouse need not have UTC as its session time zone.
    sql.execute("SET TIME ZONE 'Asia/Ho_Chi_Minh'")
    report = Mock()
    transform = transformer(sql, excluded=(2,), report=report)
    expected = dict(zip(SILVER_TABLES, (1, 1, 2, 6, 6, 2, 2), strict=True))
    assert transform.run() == transform.run() == expected
    shop = sql.execute("SELECT * FROM silver.dim_shops")[0]
    assert shop.owner_name == "Owner" and shop.is_active is False
    product = sql.execute("SELECT * FROM silver.dim_products")[0]
    assert (product.category_name, product.shop_name, product.is_active) == (
        "Clothing",
        "Shop",
        False,
    )
    variant = sql.execute("SELECT * FROM silver.dim_variants WHERE id = 1")[0]
    assert (variant.size, variant.color, variant.price, variant.is_active) == (
        "XL",
        "Dark Blue",
        Decimal("125.50"),
        False,
    )
    orders = sql.execute("SELECT * FROM silver.fact_orders ORDER BY id")
    assert tuple(row.status for row in orders) == ORDER_STATUSES
    assert all(row.created_date_vn == date(2026, 10, 1) for row in orders)
    assert all(row.delivered_date_vn == date(2026, 10, 1) for row in orders)
    assert orders[0].created_at == datetime(2026, 9, 30, 17)  # UTC instant unchanged
    assert orders[0].total_amount == Decimal("125.50")
    items = sql.execute("SELECT * FROM silver.fact_order_items ORDER BY id")
    assert tuple(item.status for item in items) == ORDER_STATUSES
    assert all(item.shop_id == 1 and item.created_date_vn == date(2026, 10, 1) for item in items)
    assert (items[0].product_name, items[0].size, items[0].color, items[0].unit_price) == (
        "Old name",
        "OLD",
        "old color",
        Decimal("99.99"),
    )
    inventory = sql.execute("SELECT * FROM silver.fact_inventory ORDER BY id")
    assert [(row.quantity, row.threshold, row.is_low) for row in inventory] == [
        (4, 5, True),
        (5, 5, False),
    ]
    assert (inventory[0].product_id, inventory[0].size, inventory[0].color) == (
        1,
        "XL",
        "Dark Blue",
    )
    assert [row.rating for row in sql.execute("SELECT * FROM silver.fact_reviews ORDER BY id")] == [
        1,
        5,
    ]
    messages = [call.args[0] for call in report.call_args_list]
    assert (
        "REJECT fact_orders: invalid_status=2; nonpositive_or_null_amount=3 (counts may overlap)"
        in messages
    )
    assert "REJECT fact_reviews: invalid_rating=3" in messages
    assert not any("Old name" in message for message in messages)

    # Updates, new rows, and valid -> rejected rows are reflected on the next refresh.
    sql.execute("UPDATE bronze.orders SET status = 'invalid' WHERE id = 1")
    sql.execute("UPDATE bronze.orders SET total_amount = 0 WHERE id = 2")
    sql.execute("UPDATE bronze.reviews SET rating = 6 WHERE id = 1")
    sql.execute("UPDATE bronze.product_variants SET size = ' m ', color = ' GREEN ' WHERE id = 1")
    sql.execute("UPDATE bronze.inventory SET quantity = 8 WHERE id = 1")
    sql.execute(
        "INSERT INTO bronze.orders VALUES (12, 1, 'DELIVERED', 200, "
        "TIMESTAMP '2026-10-01 17:00:00Z', NULL)"
    )
    sql.execute("INSERT INTO bronze.order_items VALUES (12, 12, 1, 'New', 'M', 'Green', 100, 2)")
    assert transform.run() == {
        **expected,
        "fact_orders": 5,
        "fact_order_items": 5,
        "fact_reviews": 1,
    }
    assert [
        row.id for row in sql.execute("SELECT id FROM silver.fact_order_items ORDER BY id")
    ] == [3, 4, 5, 6, 12]
    assert (
        sql.execute("SELECT delivered_date_vn FROM silver.fact_orders WHERE id = 12")[0][0] is None
    )
    assert sql.execute("SELECT size, color, is_low FROM silver.fact_inventory WHERE id = 1")[0] == (
        "M",
        "Green",
        False,
    )
    assert sql.execute("SELECT COUNT(*) FROM bronze.orders")[0][0] == 12  # Bronze remains untouched
    no_stages(sql)


def test_empty_bronze_produces_seven_empty_delta_tables(silver_sql):
    assert transformer(silver_sql).run() == dict.fromkeys(SILVER_TABLES, 0)
    no_stages(silver_sql)


@pytest.mark.parametrize("timezone", ["UTC", "Asia/Ho_Chi_Minh", "America/Los_Angeles"])
@pytest.mark.parametrize("timestamp_type", ["TIMESTAMP", "TIMESTAMP_NTZ"])
def test_vn_date_boundaries_null_and_pre_epoch_are_session_independent(
    sql, timezone, timestamp_type
):
    sql.execute(f"SET TIME ZONE '{timezone}'")
    try:
        for clock, expected in [
            ("2026-09-30 16:59:59.999999", date(2026, 9, 30)),
            ("2026-09-30 17:00:00", date(2026, 10, 1)),
            ("2026-12-31 20:00:00", date(2027, 1, 1)),
            ("1969-12-31 16:59:59", date(1969, 12, 31)),
        ]:
            suffix = "Z" if timestamp_type == "TIMESTAMP" else ""
            value = f"{timestamp_type} '{clock}{suffix}'"
            assert sql.execute(f"SELECT {vn_date(value)}")[0][0] == expected
        assert sql.execute(f"SELECT {vn_date(f'CAST(NULL AS {timestamp_type})')}")[0][0] is None
    finally:
        sql.execute("SET TIME ZONE 'UTC'")


@pytest.mark.parametrize("bad_key", ["NULL", "1"])
def test_bad_keys_preserve_existing_silver_and_cleanup(silver_sql, bad_key):
    sql = silver_sql
    sql.execute("INSERT INTO bronze.reviews VALUES (1, 1, 3, 'ok')")
    transform = transformer(sql)
    transform.transform_table("fact_reviews")
    before = sql.execute("SELECT * FROM silver.fact_reviews")
    sql.execute(f"INSERT INTO bronze.reviews VALUES ({bad_key}, 1, 4, 'bad key')")
    with pytest.raises(TransformationError, match="non-null and unique"):
        transform.transform_table("fact_reviews")
    assert sql.execute("SELECT * FROM silver.fact_reviews") == before
    no_stages(sql)


def test_schema_drift_and_failed_merge_preserve_target_and_cleanup(silver_sql):
    sql = silver_sql
    sql.execute("INSERT INTO bronze.reviews VALUES (1, 1, 3, 'ok')")
    transform = transformer(sql)
    transform.transform_table("fact_reviews")
    before = sql.execute("SELECT * FROM silver.fact_reviews")
    sql.execute("ALTER TABLE silver.fact_reviews ADD CONSTRAINT test_rating CHECK (rating <= 3)")
    sql.execute("UPDATE bronze.reviews SET rating = 4 WHERE id = 1")
    with pytest.raises(Exception, match="CHECK constraint"):
        transform.transform_table("fact_reviews")
    assert sql.execute("SELECT * FROM silver.fact_reviews") == before
    no_stages(sql)
    sql.execute("ALTER TABLE bronze.reviews ADD COLUMNS (extra STRING)")
    with pytest.raises(TransformationError, match="schema differs"):
        transform.transform_table("fact_reviews")
    assert sql.execute("SELECT * FROM silver.fact_reviews") == before
    no_stages(sql)


def test_all_rejected_snapshot_removes_old_rows_and_recovery_reinserts(silver_sql):
    sql = silver_sql
    sql.execute("INSERT INTO bronze.reviews VALUES (1, 1, 3, 'ok')")
    transform = transformer(sql)
    assert transform.transform_table("fact_reviews") == 1
    sql.execute("UPDATE bronze.reviews SET rating = 0")
    assert transform.transform_table("fact_reviews") == 0
    sql.execute("UPDATE bronze.reviews SET rating = 5")
    assert transform.transform_table("fact_reviews") == 1
    assert sql.execute("SELECT rating FROM silver.fact_reviews")[0][0] == 5
    no_stages(sql)


def test_join_fanout_is_rejected_and_run_stops_before_downstream(silver_sql):
    sql = silver_sql
    sql.execute("INSERT INTO bronze.users VALUES (1, 'Owner'), (1, 'Duplicate')")
    sql.execute("INSERT INTO bronze.shops VALUES (1, 1, 'Shop', true)")
    report = Mock()
    with pytest.raises(TransformationError, match="non-null and unique"):
        transformer(sql, report=report).run()
    assert not sql.execute("SHOW TABLES IN silver")
    assert not any("Silver completed" in call.args[0] for call in report.call_args_list)


def test_unknown_table_and_unsafe_namespace_fail_before_sql():
    sql = Mock()
    with pytest.raises(ValueError):
        SilverTransform(sql, "bad.name")
    with pytest.raises(ValueError, match="outside Planning E2"):
        SilverTransform(sql).transform_table("users")
    sql.execute.assert_not_called()


def test_shop_exclusion_only_removes_explicit_ids_on_refresh(silver_sql):
    sql = silver_sql
    sql.execute("INSERT INTO bronze.users VALUES (1, 'Owner'), (2, 'Test owner')")
    sql.execute(
        "INSERT INTO bronze.shops VALUES (1, 1, 'Test shop name', false), (2, 2, 'Shop', true)"
    )
    assert transformer(sql).transform_table("dim_shops") == 2
    assert transformer(sql, excluded=(2, 2)).transform_table("dim_shops") == 1
    assert sql.execute("SELECT id, name, is_active FROM silver.dim_shops")[0] == (
        1,
        "Test shop name",
        False,
    )
    assert sql.execute("SELECT COUNT(*) FROM bronze.shops")[0][0] == 2
    no_stages(sql)


def test_merge_and_rejection_counts_use_materialized_snapshot(silver_sql):
    sql = silver_sql
    sql.execute("INSERT INTO bronze.reviews VALUES (1, 1, 3, 'ok')")
    original = sql.execute

    def change_bronze_after_materialization(statement):
        if statement.startswith("SELECT COUNT(*), COUNT(id)"):
            original("UPDATE bronze.reviews SET rating = 0")
        return original(statement)

    sql.execute = change_bronze_after_materialization
    report = Mock()
    assert transformer(sql, report=report).transform_table("fact_reviews") == 1
    assert original("SELECT rating FROM silver.fact_reviews")[0][0] == 3
    report.assert_called_once_with("REJECT fact_reviews: invalid_rating=0", flush=True)
    no_stages(sql)
