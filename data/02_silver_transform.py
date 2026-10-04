# Databricks notebook source
# MAGIC %md
# MAGIC # E2 — Silver only
# MAGIC Transform the current Bronze tables; run Bronze first when new CDC data is pending.
# MAGIC Use the same widgets and checkpoint_root as 00_pipeline.py. See docs/DATA_PLATFORM.md.

# COMMAND ----------
import json

from pipeline_job import notebook_main

if "dbutils" in globals() and "spark" in globals():
    result = notebook_main(globals()["dbutils"], globals()["spark"], stage="silver")
    globals()["dbutils"].notebook.exit(json.dumps(result))
