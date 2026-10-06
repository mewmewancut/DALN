from unittest.mock import Mock

import pytest

import gold_job
import pipeline_job
from gold_queries import GOLD_TABLES


def test_silver_failure_stops_gold(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline_job, "CDCIngest", Mock())
    monkeypatch.setattr(pipeline_job, "run_silver", Mock(side_effect=RuntimeError("Silver failed")))
    gold = Mock()
    monkeypatch.setattr(pipeline_job, "run_gold", gold)
    with pytest.raises(RuntimeError, match="Silver failed"):
        pipeline_job.run_pipeline(Mock(), "cdc", str(tmp_path))
    gold.assert_not_called()


@pytest.mark.parametrize("stage", ["all", "gold"])
def test_gold_warehouse_failure_fails_job_without_starting_spark(monkeypatch, tmp_path, stage):
    monkeypatch.setattr(pipeline_job, "preflight", Mock(return_value={"bronze": {}, "silver": {}}))
    monkeypatch.setattr(
        pipeline_job, "run_gold_on_warehouse", Mock(side_effect=RuntimeError("Gold failed"))
    )
    spark = Mock()
    with pytest.raises(RuntimeError, match="Gold failed"):
        pipeline_job.run_pipeline(
            spark, "cdc", str(tmp_path), stage=stage, metadata_warehouse_id="wh"
        )
    spark.sql.assert_not_called()


def test_gold_only_on_warehouse_does_not_read_cdc_or_silver_checkpoints(monkeypatch, tmp_path):
    preflight, bronze, silver = Mock(), Mock(), Mock()
    monkeypatch.setattr(pipeline_job, "preflight", preflight)
    monkeypatch.setattr(pipeline_job.CDCIngest, "run", bronze)
    monkeypatch.setattr(pipeline_job, "run_silver", silver)
    gold = Mock(return_value=dict.fromkeys(GOLD_TABLES, 0))
    monkeypatch.setattr(pipeline_job, "run_gold_on_warehouse", gold)
    spark = Mock()
    result = pipeline_job.run_pipeline(
        spark, "cdc", str(tmp_path), stage="gold", metadata_warehouse_id="wh"
    )
    assert set(result) == {"gold", "timings_seconds"}
    assert result["gold"] == dict.fromkeys(GOLD_TABLES, 0)
    assert result["timings_seconds"]["spark_startup"] == 0
    for unused in (preflight, bronze, silver, spark.sql):
        unused.assert_not_called()


def test_warehouse_gold_uses_real_sql_adapter_and_unified_auth(monkeypatch):
    monkeypatch.setattr("databricks.sdk.config.Config._resolve_host_metadata", lambda self: None)
    monkeypatch.setenv("DATABRICKS_HOST", "https://example.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "fake-token-for-test")
    client = Mock()
    monkeypatch.setattr("databricks.sdk.WorkspaceClient", Mock(return_value=client))
    transform = Mock(return_value=Mock(run=Mock(return_value={"revenue_daily": 3})))
    monkeypatch.setattr(gold_job, "GoldTransform", transform)
    assert gold_job.run_gold_on_warehouse("wh", "fashion") == {"revenue_daily": 3}
    adapter, catalog = transform.call_args.args
    assert adapter.api is client.statement_execution and adapter.warehouse_id == "wh"
    assert catalog == "fashion"
