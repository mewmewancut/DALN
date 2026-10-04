import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest

from bronze_ingest import TABLES, IngestionError
from cdc_ingest import CDCIngest, table_snapshot
from cdc_merge import merge_changes, process_batch

SCHEMA = """
id BIGINT, name STRING, amount DECIMAL(12,2), is_active BOOLEAN, created_at TIMESTAMP,
_pg_change_type STRING, _pg_lsn BIGINT, _pg_xid INT, _timestamp TIMESTAMP, _sort_by BIGINT
"""


def history(sql, table="users", empty=False):
    sql.execute(f"CREATE TABLE source.lb_{table}_history ({SCHEMA}) USING DELTA")
    if not empty:
        event(sql, table, 1, "insert", 1, "original", amount="12.50")


def event(sql, table, key, kind, order, name="updated", amount="99.99"):
    sql.execute(
        f"INSERT INTO source.lb_{table}_history VALUES "
        f"({key}, '{name}', {amount}, false, TIMESTAMP '2026-09-30 20:00:00', "
        f"'{kind}', {order}, 1, TIMESTAMP '2026-10-01 01:00:00', {order})"
    )


def ingester(sql, root):
    return CDCIngest(
        sql.spark, "spark_catalog", str(root), "source", "spark_catalog", report=Mock()
    )


def test_all_thirteen_bootstrap_and_second_run_skip_without_rewriting(sql, tmp_path):
    assert len(TABLES) == 13 and "auth_tokens" not in TABLES
    for table in TABLES:
        history(sql, table, empty=table == "reviews")
    ingest = ingester(sql, tmp_path)
    assert set(ingest.run().values()) == {"BOOTSTRAP"}
    versions = {table: table_snapshot(sql.spark, f"bronze.{table}") for table in TABLES}
    assert set(ingest.run().values()) == {"SKIP"}
    assert versions == {table: table_snapshot(sql.spark, f"bronze.{table}") for table in TABLES}
    for table in TABLES:
        assert sql.execute(f"SELECT COUNT(*) FROM bronze.{table}")[0][0] == (
            0 if table == "reviews" else 1
        )
    row = sql.execute("SELECT * FROM bronze.users")[0]
    assert row.name == "original" and row.amount == Decimal("12.50")
    assert row.created_at == datetime(2026, 9, 30, 20)
    assert not any(c.startswith("_pg_") for c in row.asDict())


def test_checkpoint_resume_updates_inserts_deletes_and_collapses_multiple_events(sql, tmp_path):
    history(sql)
    ingest = ingester(sql, tmp_path)
    assert ingest.ingest_table("users") == "BOOTSTRAP"
    event(sql, "users", 1, "update_preimage", 2, "original")
    event(sql, "users", 1, "update_postimage", 3, "new")
    event(sql, "users", 2, "insert", 4, "second")
    assert ingest.ingest_table("users") == "CDC"
    assert [
        (r.id, r.name) for r in sql.execute("SELECT id, name FROM bronze.users ORDER BY id")
    ] == [(1, "new"), (2, "second")]
    # A new instance must reuse offsets, not resnapshot the source.
    resumed = ingester(sql, tmp_path)
    event(sql, "users", 1, "delete", 5)
    event(sql, "users", 2, "update_postimage", 6, "latest")
    assert resumed.ingest_table("users") == "CDC"
    assert sql.execute("SELECT id, name FROM bronze.users")[0] == (2, "latest")
    assert resumed.ingest_table("users") == "SKIP"


def test_replay_is_deterministic_and_preimage_removes_old_primary_key(sql, tmp_path):
    history(sql)
    ingest = ingester(sql, tmp_path)
    ingest.ingest_table("users")
    event(sql, "users", 1, "update_preimage", 2)
    event(sql, "users", 2, "update_postimage", 3, "moved")
    frame = sql.spark.table("source.lb_users_history").filter("_pg_lsn > 1")
    process_batch(frame, 0, target="bronze.users")
    before = sql.execute("SELECT * FROM bronze.users")
    process_batch(frame, 0, target="bronze.users")
    assert sql.execute("SELECT * FROM bronze.users") == before
    assert before[0].id == 2 and before[0].name == "moved"


def test_bootstrap_removes_stale_legacy_rows_and_empty_snapshot_reconciles(sql, tmp_path):
    history(sql)
    ingest = ingester(sql, tmp_path)
    ingest.ingest_table("users")
    sql.execute(
        "INSERT INTO bronze.users "
        "SELECT 9, name, amount, is_active, created_at, _ingested_at FROM bronze.users"
    )
    fresh = ingester(sql, tmp_path / "new-checkpoint")
    fresh.ingest_table("users")
    assert sql.execute("SELECT id FROM bronze.users") == [(1,)]
    history(sql, "reviews", empty=True)
    sql.execute("CREATE TABLE bronze.reviews USING DELTA AS SELECT * FROM bronze.users")
    fresh.ingest_table("reviews")
    assert sql.execute("SELECT COUNT(*) FROM bronze.reviews")[0][0] == 0


@pytest.mark.parametrize("key,kind", [("NULL", "insert"), ("1", "invalid")])
def test_invalid_events_preserve_target_and_manifest(sql, tmp_path, key, kind):
    history(sql)
    ingest = ingester(sql, tmp_path)
    ingest.ingest_table("users")
    marker = tmp_path / "spark_catalog/e1/users/source.json"
    before_marker = marker.read_text()
    before_rows = sql.execute("SELECT * FROM bronze.users")
    event(sql, "users", key, kind, 2)
    with pytest.raises(Exception):
        ingest.ingest_table("users")
    assert marker.read_text() == before_marker
    assert sql.execute("SELECT * FROM bronze.users") == before_rows


def test_failed_merge_preserves_data_and_checkpoint_and_can_retry(sql, tmp_path):
    history(sql)
    ingest = ingester(sql, tmp_path)
    ingest.ingest_table("users")
    sql.execute("ALTER TABLE bronze.users ADD CONSTRAINT positive_amount CHECK (amount >= 0)")
    marker = tmp_path / "spark_catalog/e1/users/source.json"
    before_marker = json.loads(marker.read_text())
    event(sql, "users", 1, "update_postimage", 2, amount="-1")
    with pytest.raises(Exception):
        ingest.ingest_table("users")
    assert json.loads(marker.read_text()) == before_marker
    assert sql.execute("SELECT amount FROM bronze.users")[0][0] == Decimal("12.50")
    sql.execute("ALTER TABLE bronze.users DROP CONSTRAINT positive_amount")
    assert ingest.ingest_table("users") == "CDC"
    assert sql.execute("SELECT amount FROM bronze.users")[0][0] == Decimal("-1")


def test_schema_drift_is_rejected_before_mutation(sql, tmp_path):
    history(sql)
    ingest = ingester(sql, tmp_path)
    ingest.ingest_table("users")
    before = sql.execute("SELECT * FROM bronze.users")
    frame = sql.spark.table("source.lb_users_history").withColumnRenamed("name", "renamed")
    with pytest.raises(IngestionError, match="schema differs"):
        merge_changes(frame, "bronze.users")
    assert sql.execute("SELECT * FROM bronze.users") == before


@pytest.mark.parametrize("recreated", ["source", "target"])
def test_recreated_source_or_target_cannot_reuse_old_offsets(sql, tmp_path, recreated):
    history(sql)
    ingest = ingester(sql, tmp_path)
    ingest.ingest_table("users")
    if recreated == "source":
        sql.execute("DROP TABLE source.lb_users_history")
        history(sql)
    else:
        sql.execute("DROP TABLE bronze.users")
        sql.execute(
            "CREATE TABLE bronze.users USING DELTA AS "
            "SELECT id, name, amount, is_active, created_at, _timestamp AS _ingested_at "
            "FROM source.lb_users_history"
        )
    with pytest.raises(IngestionError, match="identity changed"):
        ingest.ingest_table("users")


@pytest.mark.parametrize("catalog", ["bad.name", "a`b", "", "a b"])
def test_invalid_namespace_and_checkpoint_fail_before_spark(catalog):
    with pytest.raises(ValueError):
        CDCIngest(None, catalog, "/tmp/checkpoints")
    with pytest.raises(ValueError):
        CDCIngest(None, "source", "../relative")


def test_only_e1_allowlist_can_be_ingested(tmp_path):
    with pytest.raises(ValueError, match="outside Planning E1"):
        CDCIngest(None, "source", str(tmp_path)).ingest_table("auth_tokens")
