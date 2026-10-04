import runpy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import pipeline_job


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


@pytest.mark.parametrize(
    "filename,stage",
    [
        ("00_pipeline.py", "all"),
        ("01_bronze_ingest.py", "bronze"),
        ("01_bronze_job.py", "bronze"),
        ("02_silver_transform.py", "silver"),
    ],
)
def test_notebook_entries_dispatch_expected_stage(monkeypatch, filename, stage):
    run = Mock(return_value={"bronze": {"users": "SKIP"}})
    monkeypatch.setattr(pipeline_job, "notebook_main", run)
    utils, spark = Mock(), Mock()
    runpy.run_path(
        str(Path(__file__).parents[1] / filename), init_globals={"dbutils": utils, "spark": spark}
    )
    if stage == "all":
        run.assert_called_once_with(utils, spark)
        utils.notebook.exit.assert_called_once_with('{"bronze": {"users": "SKIP"}}')
    else:
        run.assert_called_once_with(utils, spark, stage=stage)


def test_widgets_reject_ephemeral_checkpoint(monkeypatch):
    widgets = Mock()
    widgets.get.return_value = "/tmp/offsets"
    run = Mock()
    monkeypatch.setattr(pipeline_job, "run_pipeline", run)
    with pytest.raises(ValueError, match="persistent"):
        pipeline_job.notebook_main(SimpleNamespace(widgets=widgets), Mock())
    run.assert_not_called()
