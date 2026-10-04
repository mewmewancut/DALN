"""Prove an entire requested stage is unchanged before touching Spark."""

from pathlib import PurePosixPath

from bronze_ingest import TABLES, identifier
from cdc_ingest import validate_marker
from silver_job import DEPENDENCIES, silver_fingerprint
from silver_queries import SILVER_TABLES
from warehouse_metadata import WarehouseMetadata


def unchanged_stages(metadata, source, target_catalog, checkpoint_root, excluded, stage):
    catalog = identifier(target_catalog)
    bronze = f"{catalog}.`bronze`"
    silver = f"{catalog}.`silver`"
    root = PurePosixPath(checkpoint_root) / target_catalog
    paths, names = [], []
    if stage in ("all", "bronze"):
        paths += [str(root / "e1" / table / "source.json") for table in TABLES]
        names += [f"{source}.{identifier('lb_' + table + '_history')}" for table in TABLES]
        names += [f"{bronze}.{identifier(table)}" for table in TABLES]
    if stage in ("all", "silver"):
        paths += [str(root / "e2" / (table + ".json")) for table in SILVER_TABLES]
        names += [f"{silver}.{identifier(table)}" for table in SILVER_TABLES]
        for dependencies in DEPENDENCIES.values():
            names += [
                f"{catalog}." + ".".join(map(identifier, dep.split("."))) for dep in dependencies
            ]

    # Missing/malformed checkpoints must go through the regular recovery path.
    markers = metadata.read_many(metadata.marker, paths)
    snapshots = metadata.snapshot_many(names)
    results = {}
    if stage in ("all", "bronze"):
        for table in TABLES:
            source_name = f"{source}.{identifier('lb_' + table + '_history')}"
            target_name = f"{bronze}.{identifier(table)}"
            marker = markers[str(root / "e1" / table / "source.json")]
            current = snapshots[source_name]
            validate_marker(marker, source_name, target_name, current, snapshots[target_name])
            if current["version"] != marker["processed_version"]:
                return None
        results["bronze"] = dict.fromkeys(TABLES, "SKIP")

    if stage in ("all", "silver"):
        for table in SILVER_TABLES:
            inputs = {
                dep: snapshots[f"{catalog}." + ".".join(map(identifier, dep.split(".")))]
                for dep in DEPENDENCIES[table]
            }
            marker = markers[str(root / "e2" / (table + ".json"))]
            if (
                marker["fingerprint"] != silver_fingerprint(table, inputs, excluded)
                or marker["target"] != snapshots[f"{silver}.{identifier(table)}"]
            ):
                return None
        results["silver"] = dict.fromkeys(SILVER_TABLES, "SKIP")
    return results


def preflight(warehouse_id, source, target_catalog, checkpoint_root, excluded, stage, *, report):
    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.core import Config

        client = WorkspaceClient(config=Config(http_timeout_seconds=15, retry_timeout_seconds=15))
        metadata = WarehouseMetadata(client, warehouse_id)
        return unchanged_stages(metadata, source, target_catalog, checkpoint_root, excluded, stage)
    except Exception as error:
        # An unavailable warehouse, bootstrap or uncertain metadata can never certify SKIP.
        # Do not expose SQL payloads, checkpoint contents or authentication errors in logs.
        report(f"Preflight unavailable ({type(error).__name__}); checking with Spark", flush=True)
        return None
