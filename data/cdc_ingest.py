"""Bounded Delta CDC ingestion with durable offsets; no recurring Lakebase scans."""

import json
import time
from functools import partial
from pathlib import Path

from bronze_ingest import TABLES, IngestionError, identifier
from cdc_merge import business_frame, merge_changes, process_batch
from delta_metadata import describe_many, table_snapshot


def save_marker(path, marker):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(marker), encoding="utf-8")
    temporary.replace(path)


def validate_marker(marker, source, target, current, target_snapshot):
    if (
        marker["source"] != source
        or marker["target"] != target
        or marker["source_id"] != current["id"]
        or marker["target_id"] != target_snapshot["id"]
        or current["version"] < marker["processed_version"]
    ):
        raise IngestionError("Source/target identity changed; explicit rebuild required")


class CDCIngest:
    def __init__(
        self,
        spark,
        source_catalog,
        checkpoint_root,
        source_schema="bronze",
        target_catalog="fashion",
        *,
        report=print,
    ):
        self.spark = spark
        self.source = f"{identifier(source_catalog)}.{identifier(source_schema)}"
        self.target = f"{identifier(target_catalog)}.`bronze`"
        if self.source.lower() == self.target.lower():
            raise ValueError("CDC source and Bronze target must differ")
        root = Path(checkpoint_root)
        if not root.is_absolute() or ".." in root.parts:
            raise ValueError("checkpoint_root must be an absolute durable path")
        self.root = root / target_catalog / "e1"
        self.report = report
        self.target_snapshots = {}

    def run(self):
        self.spark.sql("SET TIME ZONE 'UTC'")
        self.spark.sql(f"CREATE SCHEMA IF NOT EXISTS {self.target}")
        started = time.monotonic()
        existing = {r.tableName for r in self.spark.sql(f"SHOW TABLES IN {self.target}").collect()}
        names = [f"{self.source}.{identifier('lb_' + table + '_history')}" for table in TABLES]
        names += [f"{self.target}.{identifier(table)}" for table in TABLES if table in existing]
        snapshots = describe_many(self.spark, names)
        self.target_snapshots = {
            name: value for name, value in snapshots.items() if name.startswith(self.target + ".")
        }
        results = {}
        for table in TABLES:
            table_started = time.monotonic()
            try:
                results[table] = self.ingest_table(table, snapshots=snapshots)
            except IngestionError:
                raise
            except Exception as error:
                raise IngestionError(
                    f"{table}: CDC failed ({type(error).__name__}); inspect job diagnostics"
                ) from None
            self.report(
                f"{results[table]} {table}; {time.monotonic() - table_started:.1f}s", flush=True
            )
        self.report(f"Bronze completed: 13 tables; {time.monotonic() - started:.1f}s", flush=True)
        return results

    def ingest_table(self, table, *, snapshots=None):
        if table not in TABLES:
            raise ValueError("Table is outside Planning E1")
        source = f"{self.source}.{identifier('lb_' + table + '_history')}"
        target = f"{self.target}.{identifier(table)}"
        snapshots = snapshots or {}
        current = snapshots[source] if source in snapshots else table_snapshot(self.spark, source)
        directory = self.root / table
        directory.mkdir(parents=True, exist_ok=True)
        marker_path = directory / "source.json"
        if not marker_path.exists():
            if (directory / "stream").exists():
                raise IngestionError("Checkpoint manifest missing; explicit rebuild required")
            snapshot = self.spark.read.option("versionAsOf", current["version"]).table(source)
            # Bootstrap at one fixed Delta version, then start reading strictly after it.
            business_frame(snapshot).limit(0).write.format("delta").mode("ignore").saveAsTable(
                target
            )
            merge_changes(snapshot, target, bootstrap=True)
            target_snapshot = table_snapshot(self.spark, target)
            self.target_snapshots[target] = target_snapshot
            target_id = target_snapshot["id"]
            marker = {
                "source": source,
                "target": target,
                "source_id": current["id"],
                "target_id": target_id,
                "starting_version": current["version"] + 1,
                "processed_version": current["version"],
            }
            save_marker(marker_path, marker)
            return "BOOTSTRAP"
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        target_snapshot = (
            snapshots[target] if target in snapshots else table_snapshot(self.spark, target)
        )
        self.target_snapshots[target] = target_snapshot
        validate_marker(marker, source, target, current, target_snapshot)
        if current["version"] == marker["processed_version"]:
            return "SKIP"
        query = (
            self.spark.readStream.option("startingVersion", marker["starting_version"])
            .option("maxBytesPerTrigger", "64m")
            .table(source)
            .writeStream.foreachBatch(partial(process_batch, target=target))
            .option("checkpointLocation", str(directory / "stream"))
            .trigger(availableNow=True)
            .start()
        )
        try:
            query.awaitTermination()
        finally:
            if query.isActive:
                query.stop()
        # Capture before starting the query: newer commits may not belong to AvailableNow.
        marker["processed_version"] = current["version"]
        save_marker(marker_path, marker)
        self.target_snapshots[target] = table_snapshot(self.spark, target)
        return "CDC"
