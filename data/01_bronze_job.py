# Databricks notebook source
# MAGIC %md
# MAGIC # E1 Bronze — scheduled Job
# MAGIC Configure databricks-sdk==0.139.0 in the serverless environment before running.
# MAGIC Keep bronze_ingest.py and warehouse_sql.py beside this notebook.
# MAGIC Use 01_bronze_ingest.py separately for the mandatory two-run E1 acceptance check.

# COMMAND ----------
"""Run one Bronze refresh with bounded parallelism and isolated SQL clients."""

import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from threading import local

from bronze_ingest import TABLES, BronzeIngest, IngestionError
from warehouse_sql import WarehouseSQL


def run_job(
    source_catalog,
    warehouse_id,
    source_schema="public",
    target_catalog="fashion",
    parallelism=2,
    statement_timeout=600,
    *,
    sql_factory=None,
    report=print,
):
    if (
        isinstance(parallelism, bool)
        or not isinstance(parallelism, int)
        or not 1 <= parallelism <= 4
    ):
        raise ValueError("parallelism must be an integer from 1 to 4")
    if statement_timeout <= 0:
        raise ValueError("statement_timeout must be positive")
    if not warehouse_id or not warehouse_id.strip():
        raise ValueError("warehouse_id is required")
    # Validate namespaces before authentication, worker creation or SQL mutations.
    bootstrap = BronzeIngest(None, source_catalog, source_schema, target_catalog)
    if sql_factory is None:
        from databricks.sdk import WorkspaceClient

        def sql_factory():
            return WarehouseSQL(
                WorkspaceClient().statement_execution, warehouse_id, statement_timeout
            )

    started = time.monotonic()
    workers = local()

    def ingest_table(table):
        if not hasattr(workers, "ingest"):
            workers.ingest = BronzeIngest(
                sql_factory(), source_catalog, source_schema, target_catalog
            )
        table_started = time.monotonic()
        report(f"START {table}", flush=True)
        count = workers.ingest.ingest_table(table)
        report(f"DONE {table}: {count} rows; {time.monotonic() - table_started:.1f}s", flush=True)
        return count

    try:
        bootstrap.sql = sql_factory()
        bootstrap.sql.execute(f"CREATE SCHEMA IF NOT EXISTS {bootstrap.target}")
        counts = {}
        tables = iter(TABLES)
        # Submit only one wave at a time. On failure, don't schedule more tables;
        # await already-running workers so their staging cleanup finishes before returning.
        with ThreadPoolExecutor(max_workers=parallelism) as pool:
            pending = {}
            for _ in range(parallelism):
                table = next(tables)
                pending[pool.submit(ingest_table, table)] = table
            while pending:
                finished, _ = wait(pending, return_when=FIRST_COMPLETED)
                completed = {pending[future]: future.result() for future in finished}
                counts.update(completed)
                for future in finished:
                    del pending[future]
                for _ in finished:
                    table = next(tables, None)
                    if table is not None:
                        pending[pool.submit(ingest_table, table)] = table
    except IngestionError:
        raise
    except Exception as error:
        # Raw SQL/server errors may contain operational data. Job logs expose only the type.
        raise IngestionError(
            f"Bronze job failed ({type(error).__name__}); inspect warehouse"
        ) from None
    report(
        f"Bronze job completed: {len(counts)} tables; {time.monotonic() - started:.1f}s", flush=True
    )
    return {table: counts[table] for table in TABLES}


def notebook_main(utils):
    utils.widgets.text("source_catalog", "")
    utils.widgets.text("source_schema", "public")
    utils.widgets.text("warehouse_id", "")
    utils.widgets.text("target_catalog", "fashion")
    utils.widgets.dropdown("parallelism", "2", ["1", "2", "3", "4"])
    utils.widgets.text("statement_timeout", "600")
    source_catalog = utils.widgets.get("source_catalog").strip()
    warehouse_id = utils.widgets.get("warehouse_id").strip()
    if not source_catalog or not warehouse_id:
        raise ValueError("Configure source_catalog and warehouse_id as Job task parameters")
    return run_job(
        source_catalog,
        warehouse_id,
        utils.widgets.get("source_schema").strip(),
        utils.widgets.get("target_catalog").strip(),
        int(utils.widgets.get("parallelism")),
        int(utils.widgets.get("statement_timeout")),
    )


# COMMAND ----------
if "dbutils" in globals():
    notebook_main(globals()["dbutils"])
