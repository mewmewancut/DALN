from datetime import datetime
from decimal import Decimal

import pytest

from bronze_ingest import TABLES, BronzeIngest, IngestionError

VALUES = "(1, 'original', 12.50, false, TIMESTAMP '2026-09-30 20:00:00')"


def source_table(sql, table="users", values=VALUES):
    sql.execute(
        f"CREATE TABLE source.{table} "
        "(id BIGINT, name STRING, amount DECIMAL(12,2), is_active BOOLEAN, created_at TIMESTAMP) "
        "USING DELTA"
    )
    if values:
        sql.execute(f"INSERT INTO source.{table} VALUES {values}")


def ingester(sql):
    return BronzeIngest(sql, "spark_catalog", "source", "spark_catalog")


def assert_no_stages(sql):
    assert not any(
        row.tableName.startswith("_ingest_") for row in sql.execute("SHOW TABLES IN bronze")
    )


def test_all_thirteen_tables_twice_have_source_counts_and_preserve_data(sql):
    assert TABLES == (
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
    for table in TABLES:
        source_table(sql, table, values="" if table == "reviews" else VALUES)
    ingest = ingester(sql)
    first = ingest.run()
    first_stamp = sql.execute("SELECT _ingested_at FROM bronze.users")[0][0]
    second = ingest.run()
    ingest.verify_source_counts(second)
    assert first == second == {table: 0 if table == "reviews" else 1 for table in TABLES}
    row = sql.execute("SELECT * FROM bronze.users")[0]
    assert row.name == "original"
    assert row.amount == Decimal("12.50")
    assert row.is_active is False
    assert row.created_at == datetime(2026, 9, 30, 20)
    assert row._ingested_at > first_stamp
    assert_no_stages(sql)
    sql.execute("INSERT INTO source.orders VALUES (2, 'concurrent', 1, true, NULL)")
    with pytest.raises(IngestionError, match="source/Bronze counts differ"):
        ingest.verify_source_counts(second)


def test_updates_existing_id_inserts_new_id_without_duplicates(sql):
    source_table(sql)
    ingest = ingester(sql)
    ingest.ingest_table("users")
    sql.execute("UPDATE source.users SET name = 'updated', amount = 99.99 WHERE id = 1")
    sql.execute("INSERT INTO source.users VALUES (2, 'new', 0, true, NULL)")
    assert ingest.ingest_table("users") == 2
    rows = sql.execute("SELECT id, name, amount FROM bronze.users ORDER BY id")
    assert [(row.id, row.name, row.amount) for row in rows] == [
        (1, "updated", Decimal("99.99")),
        (2, "new", Decimal("0.00")),
    ]
    assert ingest.ingest_table("users") == 2
    assert_no_stages(sql)


@pytest.mark.parametrize("invalid_id", ["NULL", "1"])
def test_invalid_source_keys_leave_existing_bronze_unchanged(sql, invalid_id):
    source_table(sql)
    ingest = ingester(sql)
    ingest.ingest_table("users")
    before = sql.execute("SELECT * FROM bronze.users")
    sql.execute(f"INSERT INTO source.users VALUES ({invalid_id}, 'invalid', 0, true, NULL)")
    with pytest.raises(IngestionError, match="non-null and unique"):
        ingest.ingest_table("users")
    assert sql.execute("SELECT * FROM bronze.users") == before
    assert_no_stages(sql)


def test_source_hard_delete_is_reported_without_deleting_history(sql):
    source_table(sql)
    ingest = ingester(sql)
    ingest.ingest_table("users")
    sql.execute("DELETE FROM source.users")
    with pytest.raises(IngestionError, match="count 1 differs from snapshot 0"):
        ingest.ingest_table("users")
    assert sql.execute("SELECT name FROM bronze.users")[0][0] == "original"
    assert_no_stages(sql)


def test_missing_source_column_leaves_bronze_unchanged_and_cleans_staging(sql):
    source_table(sql)
    ingest = ingester(sql)
    ingest.ingest_table("users")
    before = sql.execute("SELECT * FROM bronze.users")
    sql.execute("DROP TABLE source.users")
    sql.execute("CREATE TABLE source.users (id BIGINT) USING DELTA")
    sql.execute("INSERT INTO source.users VALUES (1)")
    with pytest.raises(IngestionError, match="schema differs"):
        ingest.ingest_table("users")
    assert sql.execute("SELECT * FROM bronze.users") == before
    assert_no_stages(sql)


def test_extra_source_column_is_not_silently_discarded(sql):
    source_table(sql)
    ingest = ingester(sql)
    ingest.ingest_table("users")
    before = sql.execute("SELECT * FROM bronze.users")
    sql.execute("ALTER TABLE source.users ADD COLUMNS (new_attribute STRING)")
    with pytest.raises(IngestionError, match="schema differs"):
        ingest.ingest_table("users")
    assert sql.execute("SELECT * FROM bronze.users") == before
    assert_no_stages(sql)


def test_merge_failure_is_atomic_and_cleans_staging(sql):
    source_table(sql)
    ingest = ingester(sql)
    ingest.ingest_table("users")
    before = sql.execute("SELECT * FROM bronze.users")
    sql.execute("ALTER TABLE bronze.users ADD CONSTRAINT positive_amount CHECK (amount >= 0)")
    sql.execute("UPDATE source.users SET amount = -1")
    with pytest.raises(Exception, match="positive_amount"):
        ingest.ingest_table("users")
    assert sql.execute("SELECT * FROM bronze.users") == before
    assert_no_stages(sql)


def test_source_change_after_extraction_does_not_change_merge_input(sql):
    source_table(sql)

    class SourceChangingSQL:
        def execute(self, statement):
            result = sql.execute(statement)
            if statement.startswith("CREATE TABLE `spark_catalog`.`bronze`.`_ingest_"):
                sql.execute("UPDATE source.users SET name = 'changed after extraction'")
            return result

    assert ingester(SourceChangingSQL()).ingest_table("users") == 1
    assert sql.execute("SELECT name FROM bronze.users")[0][0] == "original"
    assert_no_stages(sql)


@pytest.mark.parametrize("catalog", ["bad.name", "a`b", "a;DROP SCHEMA fashion", "", "a b"])
def test_rejects_unsafe_identifiers_before_sql(catalog):
    with pytest.raises(ValueError, match="identifiers"):
        BronzeIngest(None, catalog)


def test_rejects_source_target_collision_and_tables_outside_e1():
    with pytest.raises(ValueError, match="must differ"):
        BronzeIngest(None, "FASHION", "bronze")
    with pytest.raises(ValueError, match="outside Planning E1"):
        BronzeIngest(None, "lakebase").ingest_table("auth_tokens")
