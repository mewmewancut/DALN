# Databricks notebook source
# MAGIC %md
# MAGIC # E2 — Bronze → Silver
# MAGIC Run after successful E1. Unchanged dependencies are skipped.
# MAGIC No installation, restart or SQL warehouse. See docs/E2_SILVER.md.

# COMMAND ----------
from pipeline_job import notebook_main

if "dbutils" in globals() and "spark" in globals():
    notebook_main(globals()["dbutils"], globals()["spark"], stage="silver")
