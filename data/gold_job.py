"""Run the same Gold SQL on the notebook session or the configured SQL warehouse."""

from gold_transform import GoldTransform
from silver_job import SparkSQL
from warehouse_sql import WarehouseSQL


def run_gold(spark, target_catalog, *, report=print):
    return GoldTransform(SparkSQL(spark), target_catalog, report=report).run()


def run_gold_on_warehouse(warehouse_id, target_catalog, *, report=print):
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config

    client = WorkspaceClient(config=Config(http_timeout_seconds=15, retry_timeout_seconds=15))
    sql = WarehouseSQL(client.statement_execution, warehouse_id)
    return GoldTransform(sql, target_catalog, report=report).run()
