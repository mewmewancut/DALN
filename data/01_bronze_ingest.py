# Databricks notebook source
# MAGIC %md
# MAGIC # E1 — Bronze only
# MAGIC Ingest CDC history into Bronze; run Silver separately to demonstrate each stage.
# MAGIC Use the same widgets and checkpoint_root as 00_pipeline.py. See docs/DATA_PLATFORM.md.

# COMMAND ----------
import json

from pipeline_job import notebook_main

if "dbutils" in globals() and "spark" in globals():
    result = notebook_main(globals()["dbutils"], globals()["spark"], stage="bronze")
    globals()["dbutils"].notebook.exit(json.dumps(result))
