# Databricks notebook source
# MAGIC %md
# MAGIC # E4 — quality gate before Dashboard/Genie
# MAGIC Run manually with stable Lakebase data and no concurrent pipeline writers.
# MAGIC This notebook runs E1/E2/E3 twice through the existing pipeline notebook.

# COMMAND ----------
import json

from quality_check import run_gate
from warehouse_sql import WarehouseSQL


def notebook_main(utils):
    from databricks.sdk import WorkspaceClient

    utils.widgets.text("source_catalog", "daln_source")
    utils.widgets.text("target_catalog", "fashion")
    utils.widgets.text("warehouse_id", "")
    utils.widgets.text("pipeline_notebook", "")
    utils.widgets.text("cdc_catalog", "fashion_cdc")
    utils.widgets.text("checkpoint_root", "/Volumes/fashion_cdc/bronze/pipeline_checkpoints")
    warehouse = utils.widgets.get("warehouse_id").strip()
    notebook = utils.widgets.get("pipeline_notebook").strip()
    if not warehouse or not notebook:
        raise ValueError("warehouse_id and pipeline_notebook are required")
    sql = WarehouseSQL(WorkspaceClient().statement_execution, warehouse)
    result = run_gate(
        sql,
        lambda: utils.notebook.run(
            notebook,
            1800,
            {
                "source_catalog": utils.widgets.get("cdc_catalog").strip(),
                "source_schema": "bronze",
                "target_catalog": utils.widgets.get("target_catalog").strip(),
                "checkpoint_root": utils.widgets.get("checkpoint_root").strip(),
                "excluded_shop_ids": "",
                "metadata_warehouse_id": warehouse,
            },
        ),
        utils.widgets.get("source_catalog").strip(),
        utils.widgets.get("target_catalog").strip(),
    )
    return {
        "passed": True,
        "checks": 5,
        "revenue": str(result["revenue"]),
        "orders": result["orders"],
    }


if "dbutils" in globals():
    globals()["dbutils"].notebook.exit(json.dumps(notebook_main(globals()["dbutils"])))
