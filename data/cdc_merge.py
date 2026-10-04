"""Deterministic CDC reduction and atomic Bronze MERGE, including hard deletes."""

from uuid import uuid4

from pyspark.sql import Window
from pyspark.sql import functions as F

from bronze_ingest import IngestionError, identifier

CDC_COLUMNS = {"_pg_change_type", "_pg_lsn", "_pg_xid", "_timestamp", "_sort_by"}
EVENTS = ("insert", "delete", "update_preimage", "update_postimage")


def latest_changes(frame):
    if not CDC_COLUMNS.issubset(frame.columns) or "id" not in frame.columns:
        raise IngestionError("CDC columns or id missing")
    if {"_rank", "_deleted", "_ingested_at"}.intersection(set(frame.columns) - CDC_COLUMNS):
        raise IngestionError("Source contains reserved pipeline columns")
    invalid = (
        F.col("id").isNull()
        | F.col("_pg_change_type").isNull()
        | ~F.col("_pg_change_type").isin(*EVENTS)
        | F.col("_pg_lsn").isNull()
        | F.col("_sort_by").isNull()
        | F.col("_timestamp").isNull()
    )
    if frame.filter(invalid).limit(1).count():
        raise IngestionError("CDC contains an invalid key, event or ordering value")
    window = Window.partitionBy("id").orderBy(F.col("_pg_lsn").desc(), F.col("_sort_by").desc())
    return frame.withColumn("_rank", F.row_number().over(window)).filter("_rank = 1").drop("_rank")


def business_frame(frame):
    if "_ingested_at" in set(frame.columns) - CDC_COLUMNS:
        raise IngestionError("Source contains reserved _ingested_at column")
    return frame.select(
        *[F.col(identifier(c)) for c in frame.columns if c not in CDC_COLUMNS],
        F.col("_timestamp").cast("timestamp").alias("_ingested_at"),
    )


def merge_changes(frame, target, *, bootstrap=False):
    """Retries produce the same values; checkpoint advances only after this MERGE succeeds."""
    spark = frame.sparkSession
    changes = latest_changes(frame)
    # Keep tombstones in the MERGE source so replay and PK changes remain safe.
    payload = changes.select(
        *[F.col(identifier(c)) for c in frame.columns if c not in CDC_COLUMNS],
        F.col("_timestamp").cast("timestamp").alias("_ingested_at"),
        F.col("_pg_change_type").isin("delete", "update_preimage").alias("_deleted"),
    )
    fields = [c for c in payload.columns if c != "_deleted"]
    actual = spark.table(target)
    expected_types = {f.name: f.dataType for f in payload.schema.fields if f.name != "_deleted"}
    if {f.name: f.dataType for f in actual.schema.fields} != expected_types:
        raise IngestionError("CDC/Bronze schema differs; migrate explicitly")
    assignments = ", ".join(f"t.{identifier(c)} = s.{identifier(c)}" for c in fields)
    insert_columns = ", ".join(identifier(c) for c in fields)
    insert_values = ", ".join(f"s.{identifier(c)}" for c in fields)
    different = " OR ".join(f"NOT (t.{identifier(c)} <=> s.{identifier(c)})" for c in fields)
    view = "_cdc_batch_" + uuid4().hex
    payload.createOrReplaceTempView(view)
    try:
        spark.sql(
            f"MERGE INTO {target} t USING {view} s ON t.id = s.id "
            "WHEN MATCHED AND s._deleted THEN DELETE "
            f"WHEN MATCHED AND NOT s._deleted AND ({different}) THEN UPDATE SET {assignments} "
            f"WHEN NOT MATCHED AND NOT s._deleted THEN INSERT ({insert_columns}) "
            f"VALUES ({insert_values}) "
            + ("WHEN NOT MATCHED BY SOURCE THEN DELETE" if bootstrap else "")
        ).collect()
    finally:
        spark.catalog.dropTempView(view)


def process_batch(frame, batch_id, *, target):
    # Use the callback's Spark session, never serialize the notebook's session or dbutils.
    frame.sparkSession.sql("SET TIME ZONE 'UTC'")
    if not frame.isEmpty():
        merge_changes(frame, target)
