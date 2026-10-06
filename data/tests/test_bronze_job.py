from unittest.mock import Mock

import pytest

import pipeline_job
from bronze_ingest import IngestionError


def test_silver_runs_only_after_successful_bronze(monkeypatch, tmp_path):
    ingest = Mock()
    ingest.run.side_effect = IngestionError("failed")
    monkeypatch.setattr(pipeline_job, "CDCIngest", Mock(return_value=ingest))
    silver = Mock()
    monkeypatch.setattr(pipeline_job, "run_silver", silver)
    gold = Mock()
    monkeypatch.setattr(pipeline_job, "run_gold", gold)
    with pytest.raises(IngestionError):
        pipeline_job.run_pipeline(Mock(), "cdc", str(tmp_path))
    silver.assert_not_called()
    gold.assert_not_called()


def test_all_stages_share_session_and_complete_in_order(monkeypatch, tmp_path):
    events = []
    spark = Mock()
    snapshots = {"`fashion`.`bronze`.`users`": {"id": "users-id", "version": 4}}
    ingest = Mock()
    ingest.target_snapshots = snapshots
    ingest.run.side_effect = lambda: events.append("bronze") or {"users": "CDC"}
    monkeypatch.setattr(pipeline_job, "CDCIngest", Mock(return_value=ingest))

    def silver(session, *args, **kwargs):
        assert session is spark
        assert kwargs["snapshots"] is snapshots
        events.append("silver")
        return {"dim_shops": 3}

    monkeypatch.setattr(pipeline_job, "run_silver", silver)

    def gold(session, catalog, **kwargs):
        assert session is spark and catalog == "fashion"
        events.append("gold")
        return {"revenue_daily": 2}

    monkeypatch.setattr(pipeline_job, "run_gold", gold)
    result = pipeline_job.run_pipeline(spark, "cdc", str(tmp_path))
    assert events == ["bronze", "silver", "gold"]
    assert result["bronze"] == {"users": "CDC"}
    assert result["silver"] == {"dim_shops": 3}
    assert result["gold"] == {"revenue_daily": 2}
    assert set(result["timings_seconds"]) == {"bronze", "silver", "gold", "spark_startup"}
    assert all(value >= 0 for value in result["timings_seconds"].values())


@pytest.mark.parametrize("stage,excluded", [("invalid", ()), ("all", (0,)), ("all", (True,))])
def test_invalid_configuration_fails_before_work(monkeypatch, tmp_path, stage, excluded):
    ingest = Mock()
    monkeypatch.setattr(pipeline_job, "CDCIngest", ingest)
    with pytest.raises(ValueError):
        pipeline_job.run_pipeline(
            Mock(), "cdc", str(tmp_path), excluded_shop_ids=excluded, stage=stage
        )
    ingest.assert_not_called()
