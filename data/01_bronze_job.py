# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Job — compatibility entry
# MAGIC Uses the same incremental E1 runner. Prefer 00_pipeline.py for scheduled E1 → E2.

# COMMAND ----------
from pipeline_job import notebook_main

if "dbutils" in globals() and "spark" in globals():
    notebook_main(globals()["dbutils"], globals()["spark"], stage="bronze")
