# Databricks notebook source
# MAGIC %md
# MAGIC # E2 Silver — Job task after Bronze
# MAGIC Configure databricks-sdk==0.139.0 in Environment / Dependencies.
# MAGIC Keep silver_transform.py, silver_queries.py, bronze_ingest.py
# MAGIC and warehouse_sql.py beside this notebook.

# COMMAND ----------
"""Run one Silver refresh on the SQL warehouse; no installation or Python restart."""

from silver_transform import SilverTransform, TransformationError
from warehouse_sql import WarehouseSQL


def run_job(target_catalog, warehouse_id, excluded_shop_ids=(), statement_timeout=600, *, sql=None):
    if not warehouse_id or not warehouse_id.strip():
        raise ValueError("warehouse_id is required")
    if statement_timeout <= 0:
        raise ValueError("statement_timeout must be positive")
    transform = SilverTransform(sql, target_catalog, excluded_shop_ids)
    try:
        if sql is None:
            from databricks.sdk import WorkspaceClient

            transform.sql = WarehouseSQL(
                WorkspaceClient().statement_execution, warehouse_id, statement_timeout
            )
        return transform.run()
    except TransformationError:
        raise
    except Exception as error:
        raise TransformationError(
            f"Silver job failed ({type(error).__name__}); inspect warehouse"
        ) from None


def notebook_main(utils):
    utils.widgets.text("target_catalog", "fashion")
    utils.widgets.text("warehouse_id", "")
    utils.widgets.text("excluded_shop_ids", "")
    utils.widgets.text("statement_timeout", "600")
    raw_ids = utils.widgets.get("excluded_shop_ids").strip()
    excluded = tuple(int(value.strip()) for value in raw_ids.split(",")) if raw_ids else ()
    return run_job(
        utils.widgets.get("target_catalog").strip(),
        utils.widgets.get("warehouse_id").strip(),
        excluded,
        int(utils.widgets.get("statement_timeout")),
    )


# COMMAND ----------
if "dbutils" in globals():
    notebook_main(globals()["dbutils"])
