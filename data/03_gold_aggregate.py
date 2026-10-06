# Databricks notebook source
# MAGIC %md
# MAGIC # E3 — Gold
# MAGIC Refresh all six Gold tables from current Silver; does not ingest E1/E2.
# MAGIC Keep repository modules beside this notebook. See docs/E3_GOLD.md.

# COMMAND ----------
import json

from pipeline_job import notebook_main

if "dbutils" in globals() and "spark" in globals():
    result = notebook_main(globals()["dbutils"], globals()["spark"], stage="gold")
    globals()["dbutils"].notebook.exit(json.dumps(result))
