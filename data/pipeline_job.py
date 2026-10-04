"""E1/E2 job orchestration on one serverless notebook session."""

import time

from cdc_ingest import CDCIngest
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
):
    if stage not in ("all", "bronze", "silver"):
        raise ValueError("Unknown pipeline stage")
    excluded_shop_ids = validate_shop_ids(excluded_shop_ids)
    ingest = CDCIngest(
        spark, source_catalog, checkpoint_root, source_schema, target_catalog, report=report
    )
    results = {}
    timings = {}
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
    )
