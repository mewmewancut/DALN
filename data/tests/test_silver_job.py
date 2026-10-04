import json
from unittest.mock import Mock

import pytest
from test_silver_transform import seed
from test_silver_transform import silver_sql as silver_sql

from cdc_ingest import table_snapshot
from silver_job import run_silver
from silver_queries import SILVER_TABLES
from silver_transform import TransformationError


def test_second_run_skips_all_seven_without_writes(silver_sql, tmp_path):
    sql = silver_sql
    seed(sql)
    first = run_silver(sql.spark, "spark_catalog", str(tmp_path), (2,), report=Mock())
    versions = {t: table_snapshot(sql.spark, f"silver.{t}") for t in SILVER_TABLES}
    second = run_silver(sql.spark, "spark_catalog", str(tmp_path), (2,), report=Mock())
    assert all(isinstance(count, int) for count in first.values())
    assert set(second.values()) == {"SKIP"}
    assert versions == {t: table_snapshot(sql.spark, f"silver.{t}") for t in SILVER_TABLES}


def test_order_change_refreshes_orders_and_items_only_and_recovers(silver_sql, tmp_path):
    sql = silver_sql
    seed(sql)
    run_silver(sql.spark, "spark_catalog", str(tmp_path), report=Mock())
    sql.execute("UPDATE bronze.orders SET total_amount = 0 WHERE id = 1")
    result = run_silver(sql.spark, "spark_catalog", str(tmp_path), report=Mock())
    assert {t for t, value in result.items() if value != "SKIP"} == {
        "fact_orders",
        "fact_order_items",
    }
    assert not sql.execute("SELECT id FROM silver.fact_orders WHERE id = 1")
    assert not sql.execute("SELECT id FROM silver.fact_order_items WHERE order_id = 1")
    sql.execute("UPDATE bronze.orders SET total_amount = 100 WHERE id = 1")
    run_silver(sql.spark, "spark_catalog", str(tmp_path), report=Mock())
    assert sql.execute("SELECT id FROM silver.fact_order_items WHERE order_id = 1")


def test_variant_change_updates_inventory_dependency_and_shop_config_is_scoped(
    silver_sql, tmp_path
):
    sql = silver_sql
    seed(sql)
    run_silver(sql.spark, "spark_catalog", str(tmp_path), report=Mock())
    sql.execute("UPDATE bronze.product_variants SET color = ' new COLOR ' WHERE id = 1")
    result = run_silver(sql.spark, "spark_catalog", str(tmp_path), report=Mock())
    assert {t for t, value in result.items() if value != "SKIP"} == {
        "dim_variants",
        "fact_inventory",
    }
    assert (
        sql.execute("SELECT color FROM silver.fact_inventory WHERE variant_id = 1")[0][0]
        == "New Color"
    )
    result = run_silver(sql.spark, "spark_catalog", str(tmp_path), (2,), report=Mock())
    assert {t for t, value in result.items() if value != "SKIP"} == {"dim_shops"}
    assert not sql.execute("SELECT id FROM silver.dim_shops WHERE id = 2")


def test_failed_transform_does_not_advance_marker_and_manual_target_change_recovers(
    silver_sql, tmp_path
):
    sql = silver_sql
    seed(sql)
    run_silver(sql.spark, "spark_catalog", str(tmp_path), report=Mock())
    marker = tmp_path / "spark_catalog/e2/fact_reviews.json"
    before = json.loads(marker.read_text())
    sql.execute("INSERT INTO bronze.reviews VALUES (1, 1, 3, 'duplicate')")
    with pytest.raises(TransformationError):
        run_silver(sql.spark, "spark_catalog", str(tmp_path), report=Mock())
    assert json.loads(marker.read_text()) == before
    sql.execute("DELETE FROM bronze.reviews WHERE comment = 'duplicate'")
    run_silver(sql.spark, "spark_catalog", str(tmp_path), report=Mock())
    sql.execute("DELETE FROM silver.fact_orders WHERE id = 1")
    result = run_silver(sql.spark, "spark_catalog", str(tmp_path), report=Mock())
    assert result["fact_orders"] != "SKIP"
    assert sql.execute("SELECT id FROM silver.fact_orders WHERE id = 1")
