# Databricks notebook source
# MAGIC %md
# MAGIC # E1 — Lakebase → Bronze
# MAGIC Mở toàn bộ thư mục `data` trong Databricks Git folder trước khi chạy.
# MAGIC Notebook điều phối SQL qua serverless SQL warehouse; xem `docs/DATA_PLATFORM.md`.
# MAGIC Notebook compute cần Python 3.11 trở lên.

# COMMAND ----------
# MAGIC %pip install databricks-sdk==0.139.0

# COMMAND ----------
# MAGIC %python
# MAGIC dbutils.library.restartPython()

# COMMAND ----------
"""Run Planning E1 against a Lakebase catalog registered in Unity Catalog."""

import argparse

from bronze_ingest import BronzeIngest, IngestionError
from warehouse_sql import WarehouseSQL


def positive_seconds(value):
    seconds = int(value)
    if seconds <= 0:
        raise argparse.ArgumentTypeError("timeout must be positive")
    return seconds


def run(
    source_catalog,
    warehouse_id,
    source_schema="public",
    target_catalog="fashion",
    check_twice=False,
    profile=None,
    statement_timeout=600,
):
    # Validate before authentication or any remote mutation.
    ingest = BronzeIngest(None, source_catalog, source_schema, target_catalog)
    from databricks.sdk import WorkspaceClient

    client = WorkspaceClient(profile=profile)
    ingest.sql = WarehouseSQL(client.statement_execution, warehouse_id, statement_timeout)
    first = ingest.run()
    if check_twice:
        second = ingest.run()
        if first != second:
            raise IngestionError("Source changed between runs; repeat with stable data")
        ingest.verify_source_counts(second)
    for table, count in first.items():
        print(f"{table}: {count} rows")
    print("Bronze MERGE completed" + ("; two-run count check passed" if check_twice else ""))
    return first


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--source-catalog", required=True)
    parser.add_argument("--source-schema", default="public")
    parser.add_argument("--target-catalog", default="fashion")
    parser.add_argument("--profile", help="Databricks unified-auth profile")
    parser.add_argument("--statement-timeout", type=positive_seconds, default=600)
    parser.add_argument("--check-twice", action="store_true")
    args = parser.parse_args(argv)

    try:
        BronzeIngest(None, args.source_catalog, args.source_schema, args.target_catalog)
    except ValueError as error:
        parser.error(str(error))
    try:
        run(
            args.source_catalog,
            args.warehouse_id,
            args.source_schema,
            args.target_catalog,
            args.check_twice,
            args.profile,
            args.statement_timeout,
        )
    except IngestionError as error:
        parser.exit(1, f"Bronze ingestion failed: {error}\n")
    except Exception as error:
        parser.exit(1, f"Bronze ingestion failed ({type(error).__name__}); inspect the warehouse\n")


def notebook_main(utils):
    utils.widgets.text("source_catalog", "")
    utils.widgets.text("source_schema", "public")
    utils.widgets.text("warehouse_id", "")
    utils.widgets.text("target_catalog", "fashion")
    utils.widgets.dropdown("check_twice", "true", ["true", "false"])
    source_catalog = utils.widgets.get("source_catalog").strip()
    warehouse_id = utils.widgets.get("warehouse_id").strip()
    if not source_catalog or not warehouse_id:
        raise ValueError("Điền source_catalog và warehouse_id trong widgets rồi chạy lại ô cuối")
    source_schema = utils.widgets.get("source_schema").strip()
    target_catalog = utils.widgets.get("target_catalog").strip()
    BronzeIngest(None, source_catalog, source_schema, target_catalog)
    try:
        return run(
            source_catalog,
            warehouse_id,
            source_schema,
            target_catalog,
            utils.widgets.get("check_twice") == "true",
        )
    except IngestionError:
        raise
    except Exception as error:
        raise IngestionError(
            f"Ingestion failed ({type(error).__name__}); inspect the warehouse"
        ) from None


# COMMAND ----------
if "dbutils" in globals():
    notebook_main(globals()["dbutils"])
elif __name__ == "__main__":
    main()
