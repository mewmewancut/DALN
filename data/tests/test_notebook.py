import json
import runpy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import pipeline_job
from bronze_ingest import IngestionError


def test_widgets_use_cdc_and_durable_volume(monkeypatch):
    values = {
        "source_catalog": "fashion_cdc",
        "source_schema": "bronze",
        "target_catalog": "fashion",
        "checkpoint_root": "/Volumes/fashion_cdc/bronze/checkpoints",
        "excluded_shop_ids": "2,3",
    }
    widgets = Mock()
    widgets.get.side_effect = values.__getitem__
    run = Mock(return_value={"bronze": {}, "silver": {}})
    monkeypatch.setattr(pipeline_job, "run_pipeline", run)
    spark = Mock()
    pipeline_job.notebook_main(SimpleNamespace(widgets=widgets), spark)
    run.assert_called_once_with(
        spark, "fashion_cdc", values["checkpoint_root"], "bronze", "fashion", (2, 3), stage="all"
    )


def test_pipeline_notebook_runs_both_stages_and_returns_result(monkeypatch):
    run = Mock(return_value={"bronze": {"users": "SKIP"}})
    monkeypatch.setattr(pipeline_job, "notebook_main", run)
    utils, spark = Mock(), Mock()
    runpy.run_path(
        str(Path(__file__).parents[1] / "00_pipeline.py"),
        init_globals={"dbutils": utils, "spark": spark},
    )
    run.assert_called_once_with(utils, spark)
    utils.notebook.exit.assert_called_once_with('{"bronze": {"users": "SKIP"}}')


def test_widgets_reject_ephemeral_checkpoint(monkeypatch):
    widgets = Mock()
    widgets.get.return_value = "/tmp/offsets"
    run = Mock()
    monkeypatch.setattr(pipeline_job, "run_pipeline", run)
    with pytest.raises(ValueError, match="persistent"):
        pipeline_job.notebook_main(SimpleNamespace(widgets=widgets), Mock())
    run.assert_not_called()


@pytest.mark.parametrize(
    "notebook,stage",
    [("01_bronze_ingest.py", "bronze"), ("02_silver_transform.py", "silver")],
)
@pytest.mark.parametrize("fails", [False, True])
def test_separate_notebook_runs_only_its_stage_and_reports_success_after_completion(
    monkeypatch, notebook, stage, fails
):
    values = {
        "source_catalog": "fashion_cdc",
        "source_schema": "bronze",
        "target_catalog": "fashion",
        "checkpoint_root": "/Volumes/fashion_cdc/bronze/pipeline_checkpoints",
        "excluded_shop_ids": "",
    }
    utils, spark = Mock(), Mock()
    utils.widgets.get.side_effect = values.__getitem__
    ingest = Mock()
    ingest.run.return_value = {"users": "CDC"}
    monkeypatch.setattr(pipeline_job, "CDCIngest", Mock(return_value=ingest))
    silver = Mock(return_value={"dim_shops": 3})
    monkeypatch.setattr(pipeline_job, "run_silver", silver)
    selected = ingest.run if stage == "bronze" else silver
    if fails:
        selected.side_effect = IngestionError("demo stage failed")

    def execute():
        runpy.run_path(
            str(Path(__file__).parents[1] / notebook),
            init_globals={"dbutils": utils, "spark": spark},
        )

    if fails:
        with pytest.raises(IngestionError, match="demo stage failed"):
            execute()
        utils.notebook.exit.assert_not_called()
    else:
        execute()
        utils.notebook.exit.assert_called_once()
        result = json.loads(utils.notebook.exit.call_args.args[0])
        assert set(result) == {stage, "timings_seconds"}
        assert result[stage] == ({"users": "CDC"} if stage == "bronze" else {"dim_shops": 3})
        assert set(result["timings_seconds"]) == {stage}

    selected.assert_called_once()
    if stage == "bronze":
        silver.assert_not_called()
    else:
        ingest.run.assert_not_called()
        silver.assert_called_once_with(
            spark, "fashion", values["checkpoint_root"], (), report=print, snapshots=None
        )
