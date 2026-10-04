# Databricks notebook source
# MAGIC %md
# MAGIC # E1 → E2 — incremental Job
# MAGIC One serverless session; no pip install, restart or SQL warehouse.
# MAGIC Keep the repository modules beside this notebook. See docs/DATA_PLATFORM.md.

# COMMAND ----------
import json

from pipeline_job import notebook_main

if "dbutils" in globals() and "spark" in globals():
    result = notebook_main(globals()["dbutils"], globals()["spark"])
    globals()["dbutils"].notebook.exit(json.dumps(result))
