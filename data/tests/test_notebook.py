import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bronze_ingest import IngestionError

spec = importlib.util.spec_from_file_location(
    "notebook", Path(__file__).resolve().parents[1] / "01_bronze_ingest.py"
)
notebook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notebook)


def test_web_widgets_pass_configuration_to_ingestion(monkeypatch):
    widgets = Mock()
    values = {
        "source_catalog": "lakebase",
        "source_schema": "public",
        "target_catalog": "fashion",
        "warehouse_id": "wh-1",
        "check_twice": "true",
    }
    widgets.get.side_effect = values.__getitem__
    run = Mock(return_value={"users": 2})
    monkeypatch.setattr(notebook, "run", run)
    assert notebook.notebook_main(SimpleNamespace(widgets=widgets)) == {"users": 2}
    run.assert_called_once_with("lakebase", "wh-1", "public", "fashion", True)


def test_empty_web_configuration_fails_before_authentication(monkeypatch):
    widgets = Mock()
    widgets.get.return_value = ""
    run = Mock()
    monkeypatch.setattr(notebook, "run", run)
    with pytest.raises(ValueError, match="source_catalog"):
        notebook.notebook_main(SimpleNamespace(widgets=widgets))
    run.assert_not_called()


def test_two_run_check_executes_twice_and_verifies_live_source_counts(monkeypatch):
    ingest = Mock()
    ingest.run.return_value = {"users": 2}
    monkeypatch.setattr(notebook, "BronzeIngest", Mock(return_value=ingest))
    monkeypatch.setattr("databricks.sdk.WorkspaceClient", Mock())
    assert notebook.run("lakebase", "wh-1", check_twice=True) == {"users": 2}
    assert ingest.run.call_count == 2
    ingest.verify_source_counts.assert_called_once_with({"users": 2})


def test_changed_counts_do_not_report_success(monkeypatch, capsys):
    ingest = Mock()
    ingest.run.side_effect = [{"users": 2}, {"users": 3}]
    monkeypatch.setattr(notebook, "BronzeIngest", Mock(return_value=ingest))
    monkeypatch.setattr("databricks.sdk.WorkspaceClient", Mock())
    with pytest.raises(IngestionError, match="Source changed"):
        notebook.run("lakebase", "wh-1", check_twice=True)
    assert "completed" not in capsys.readouterr().out


@pytest.mark.parametrize("extra", [["--statement-timeout", "0"], ["--source-catalog", "bad.name"]])
def test_invalid_cli_options_fail_before_authentication(monkeypatch, extra):
    client = Mock()
    monkeypatch.setattr("databricks.sdk.WorkspaceClient", client)
    with pytest.raises(SystemExit) as error:
        notebook.main(["--source-catalog", "lakebase", "--warehouse-id", "wh-1", *extra])
    assert error.value.code == 2
    client.assert_not_called()


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
def test_remote_exception_has_no_sensitive_payload_in_job_logs(monkeypatch, capsys, error_type):
    monkeypatch.setattr(notebook, "run", Mock(side_effect=error_type("private payload")))
    with pytest.raises(SystemExit) as error:
        notebook.main(["--source-catalog", "lakebase", "--warehouse-id", "wh-1"])
    assert error.value.code == 1
    assert "private payload" not in capsys.readouterr().err
