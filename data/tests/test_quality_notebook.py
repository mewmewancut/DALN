import json
import runpy
from pathlib import Path
from unittest.mock import Mock

import databricks.sdk
import pytest

import quality_check


@pytest.mark.parametrize("fails", [False, True])
def test_quality_notebook_exits_only_after_gate_passes(monkeypatch, fails):
    utils = Mock()
    values = {
        "source_catalog": "source",
        "target_catalog": "fashion",
        "warehouse_id": "warehouse",
        "pipeline_notebook": "/Workspace/pipeline",
        "cdc_catalog": "fashion_cdc",
        "checkpoint_root": "/Volumes/checkpoints",
    }
    utils.widgets.get.side_effect = values.__getitem__
    monkeypatch.setattr(databricks.sdk, "WorkspaceClient", Mock())

    def gate(sql, pipeline, source, target):
        assert (source, target) == ("source", "fashion")
        pipeline()
        if fails:
            raise RuntimeError("gate failed")
        return {"revenue": 100, "orders": 2}

    monkeypatch.setattr(quality_check, "run_gate", gate)

    def execute():
        runpy.run_path(
            str(Path(__file__).parents[1] / "04_data_quality_check.py"),
            init_globals={"dbutils": utils},
        )

    if fails:
        with pytest.raises(RuntimeError, match="gate failed"):
            execute()
        utils.notebook.exit.assert_not_called()
    else:
        execute()
        assert json.loads(utils.notebook.exit.call_args.args[0]) == {
            "passed": True,
            "checks": 5,
            "revenue": "100",
            "orders": 2,
        }
    utils.notebook.run.assert_called_once_with(
        "/Workspace/pipeline",
        1800,
        {
            "source_catalog": "fashion_cdc",
            "source_schema": "bronze",
            "target_catalog": "fashion",
            "checkpoint_root": "/Volumes/checkpoints",
            "excluded_shop_ids": "",
            "metadata_warehouse_id": "warehouse",
        },
    )
