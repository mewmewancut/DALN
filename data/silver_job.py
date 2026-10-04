"""Skip unchanged Silver dependencies and preserve the Planning E2 dependency order."""

import json
import time
from pathlib import Path

from cdc_ingest import save_marker
from delta_metadata import describe_many, table_snapshot
from silver_queries import SILVER_TABLES
from silver_transform import SilverTransform

DEPENDENCIES = {
    "dim_shops": ("bronze.shops", "bronze.users"),
    "dim_products": ("bronze.products", "bronze.categories", "bronze.shops"),
    "dim_variants": ("bronze.product_variants",),
    "fact_orders": ("bronze.orders",),
    "fact_order_items": ("bronze.order_items", "silver.fact_orders"),
    "fact_inventory": ("bronze.inventory", "silver.dim_variants"),
    "fact_reviews": ("bronze.reviews",),
}
TRANSFORM_VERSION = 1


def silver_fingerprint(table, inputs, excluded_shop_ids):
    return {
        "inputs": inputs,
        "excluded_shop_ids": list(excluded_shop_ids) if table == "dim_shops" else [],
        "transform_version": TRANSFORM_VERSION,
    }


class SparkSQL:
    def __init__(self, spark):
        self.spark = spark

    def execute(self, statement):
        return self.spark.sql(statement).collect()


def run_silver(
    spark, target_catalog, checkpoint_root, excluded_shop_ids=(), *, report=print, snapshots=None
):
    started = time.monotonic()
    transform = SilverTransform(SparkSQL(spark), target_catalog, excluded_shop_ids, report=report)
    root = Path(checkpoint_root)
    if not root.is_absolute() or ".." in root.parts:
        raise ValueError("checkpoint_root must be an absolute durable path")
    root = root / target_catalog / "e2"
    root.mkdir(parents=True, exist_ok=True)
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {transform.silver}")
    snapshots = dict(snapshots or {})
    existing = {r.tableName for r in spark.sql(f"SHOW TABLES IN {transform.silver}").collect()}
    names = []
    for dependencies in DEPENDENCIES.values():
        for dependency in dependencies:
            namespace, name = dependency.split(".")
            if namespace != "silver" or name in existing:
                names.append(f"{getattr(transform, namespace)}.`{name}`")
    names += [f"{transform.silver}.`{table}`" for table in SILVER_TABLES if table in existing]
    snapshots.update(describe_many(spark, [name for name in names if name not in snapshots]))
    results = {}
    for table in SILVER_TABLES:
        inputs = {}
        for dependency in DEPENDENCIES[table]:
            namespace, name = dependency.split(".")
            qualified = f"{getattr(transform, namespace)}.`{name}`"
            if qualified not in snapshots:
                snapshots[qualified] = table_snapshot(spark, qualified)
            inputs[dependency] = snapshots[qualified]
        fingerprint = silver_fingerprint(table, inputs, transform.excluded_shop_ids)
        marker_path = root / (table + ".json")
        target = f"{transform.silver}.`{table}`"
        previous = json.loads(marker_path.read_text()) if marker_path.exists() else None
        current_target = snapshots.get(target)
        if (
            previous
            and previous["fingerprint"] == fingerprint
            and previous["target"] == current_target
        ):
            report(f"SKIP {table}: dependencies unchanged", flush=True)
            results[table] = "SKIP"
            continue
        table_started = time.monotonic()
        count = transform.transform_table(table)
        snapshots[target] = table_snapshot(spark, target)
        save_marker(marker_path, {"fingerprint": fingerprint, "target": snapshots[target]})
        report(f"DONE {table}: {count} rows; {time.monotonic() - table_started:.1f}s", flush=True)
        results[table] = count
    report(f"Silver completed: 7 tables; {time.monotonic() - started:.1f}s", flush=True)
    return results
