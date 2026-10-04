"""E1/E2 job orchestration on one serverless notebook session."""

import time

from cdc_ingest import CDCIngest
from pipeline_preflight import preflight
from silver_job import run_silver
from silver_transform import validate_shop_ids


def run_pipeline(
    spark,
    source_catalog,
    checkpoint_root,
    source_schema="bronze",
    target_catalog="fashion",
    excluded_shop_ids=(),
    *,
    stage="all",
    report=print,
    metadata_warehouse_id="",
):
    if stage not in ("all", "bronze", "silver"):
        raise ValueError("Unknown pipeline stage")
    excluded_shop_ids = validate_shop_ids(excluded_shop_ids)
    ingest = CDCIngest(
        spark, source_catalog, checkpoint_root, source_schema, target_catalog, report=report
    )
    results = {}
    timings = {}
    if metadata_warehouse_id:
        started = time.monotonic()
        report("Checking Delta versions/checkpoints before starting Spark", flush=True)
        unchanged = preflight(
            metadata_warehouse_id,
            ingest.source,
            target_catalog,
            checkpoint_root,
            excluded_shop_ids,
            stage,
            report=report,
        )
        timings["preflight"] = round(time.monotonic() - started, 3)
        if unchanged is not None:
            timings.update(dict.fromkeys(unchanged, 0.0))
            timings["spark_startup"] = 0.0
            report("All requested tables unchanged; notebook Spark session not needed", flush=True)
            return {**unchanged, "timings_seconds": timings}
    report("Starting Spark session; waiting for first query", flush=True)
    started = time.monotonic()
    spark.sql("SELECT 1").collect()
    timings["spark_startup"] = round(time.monotonic() - started, 3)
    report(f"Spark ready: {timings['spark_startup']:.1f}s", flush=True)
    if stage in ("all", "bronze"):
        started = time.monotonic()
        results["bronze"] = ingest.run()
        timings["bronze"] = round(time.monotonic() - started, 3)
    if stage in ("all", "silver"):
        started = time.monotonic()
        results["silver"] = run_silver(
            spark,
            target_catalog,
            checkpoint_root,
            excluded_shop_ids,
            report=report,
            snapshots=ingest.target_snapshots if stage == "all" else None,
        )
        timings["silver"] = round(time.monotonic() - started, 3)
    results["timings_seconds"] = timings
    return results


def notebook_main(utils, spark, stage="all"):
    utils.widgets.text("source_catalog", "fashion_cdc")
    utils.widgets.text("source_schema", "bronze")
    utils.widgets.text("target_catalog", "fashion")
    utils.widgets.text("checkpoint_root", "/Volumes/fashion_cdc/bronze/pipeline_checkpoints")
    utils.widgets.text("excluded_shop_ids", "")
    utils.widgets.text("metadata_warehouse_id", "")
    root = utils.widgets.get("checkpoint_root").strip()
    if not root.startswith("/Volumes/"):
        raise ValueError("Use a persistent Unity Catalog Volume for checkpoint_root")
    raw = utils.widgets.get("excluded_shop_ids").strip()
    excluded = tuple(int(value.strip()) for value in raw.split(",")) if raw else ()
    return run_pipeline(
        spark,
        utils.widgets.get("source_catalog").strip(),
        root,
        utils.widgets.get("source_schema").strip(),
        utils.widgets.get("target_catalog").strip(),
        excluded,
        stage=stage,
        metadata_warehouse_id=utils.widgets.get("metadata_warehouse_id").strip(),
    )
