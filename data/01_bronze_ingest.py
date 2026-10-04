# Databricks notebook source
# MAGIC %md
# MAGIC # E1 — Lakebase CDC → Bronze
# MAGIC Serverless compute; one initial snapshot followed by checkpointed CDC.
# MAGIC No installation, restart or SQL warehouse. See docs/DATA_PLATFORM.md.

# COMMAND ----------
from pipeline_job import notebook_main

if "dbutils" in globals() and "spark" in globals():
    notebook_main(globals()["dbutils"], globals()["spark"], stage="bronze")
