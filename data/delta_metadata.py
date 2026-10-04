"""Bounded metadata prefetch; avoids duplicate describe calls between pipeline stages."""

from concurrent.futures import ThreadPoolExecutor

from bronze_ingest import IngestionError


def table_snapshot(spark, name):
    detail = spark.sql(f"DESCRIBE DETAIL {name}").first()
    version = spark.sql(f"DESCRIBE HISTORY {name} LIMIT 1").first().version
    return {"id": detail.id, "version": int(version)}


def describe_many(spark, names):
    # Metadata only: writers/stream callbacks remain sequential, on the same session.
    names = tuple(dict.fromkeys(names))
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = pool.map(lambda name: table_snapshot(spark, name), names)
            return dict(zip(names, values, strict=True))
    except Exception as error:
        raise IngestionError(f"Delta metadata failed ({type(error).__name__})") from None
