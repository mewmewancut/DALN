from unittest.mock import Mock

import pytest

import pipeline_job


def test_standalone_silver_does_not_repeat_bronze(monkeypatch, tmp_path):
    ingest = Mock()
    monkeypatch.setattr(pipeline_job, "CDCIngest", Mock(return_value=ingest))
    silver = Mock(return_value={"fact_orders": 3})
    monkeypatch.setattr(pipeline_job, "run_silver", silver)
    result = pipeline_job.run_pipeline(Mock(), "cdc", str(tmp_path), stage="silver")
    assert result["silver"] == {"fact_orders": 3}
    assert "bronze" not in result
    ingest.run.assert_not_called()
    silver.assert_called_once()


def test_invalid_exclusion_stops_before_spark(monkeypatch, tmp_path):
    sql = Mock()
    with pytest.raises(ValueError):
        pipeline_job.run_pipeline(
            sql, "cdc", str(tmp_path), excluded_shop_ids=(-1,), stage="silver"
        )
    sql.sql.assert_not_called()
