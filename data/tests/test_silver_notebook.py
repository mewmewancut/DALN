import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from silver_transform import TransformationError

spec = importlib.util.spec_from_file_location(
    "silver_notebook", Path(__file__).resolve().parents[1] / "02_silver_transform.py"
)
notebook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notebook)


def test_job_widgets_pass_catalog_timeout_and_explicit_test_shop_ids(monkeypatch):
    widgets = Mock()
    values = {
        "target_catalog": "fashion",
        "warehouse_id": "wh-1",
        "excluded_shop_ids": "2, 5",
        "statement_timeout": "300",
    }
    widgets.get.side_effect = values.__getitem__
    run = Mock(return_value={"fact_orders": 2})
    monkeypatch.setattr(notebook, "run_job", run)
    assert notebook.notebook_main(SimpleNamespace(widgets=widgets)) == {"fact_orders": 2}
    run.assert_called_once_with("fashion", "wh-1", (2, 5), 300)


@pytest.mark.parametrize(
    "catalog, warehouse, excluded, timeout",
    [
        ("bad.name", "wh", (), 600),
        ("fashion", "", (), 600),
        ("fashion", "wh", (), 0),
        ("fashion", "wh", (True,), 600),
        ("fashion", "wh", (-1,), 600),
        ("fashion", "wh", (1.5,), 600),
        ("fashion", "wh", ("1 OR 1=1",), 600),
    ],
)
def test_invalid_configuration_never_authenticates_or_executes(
    monkeypatch, catalog, warehouse, excluded, timeout
):
    client = Mock()
    monkeypatch.setattr("databricks.sdk.WorkspaceClient", client)
    with pytest.raises(ValueError):
        notebook.run_job(catalog, warehouse, excluded, timeout)
    client.assert_not_called()


def test_remote_failure_is_sanitized_and_does_not_report_success(capsys):
    sql = Mock()
    sql.execute.side_effect = RuntimeError("private server payload")
    with pytest.raises(TransformationError, match="RuntimeError") as error:
        notebook.run_job("fashion", "wh", sql=sql)
    assert "private" not in str(error.value)
    assert "Silver completed" not in capsys.readouterr().out


def test_default_authentication_refreshes_once_with_warehouse_timeout(monkeypatch):
    client = Mock()
    transform = Mock()
    transform.run.return_value = {"dim_shops": 1}
    factory = Mock(return_value=transform)
    warehouse = Mock()
    monkeypatch.setattr(notebook, "SilverTransform", factory)
    monkeypatch.setattr(notebook, "WarehouseSQL", warehouse)
    monkeypatch.setattr("databricks.sdk.WorkspaceClient", client)
    assert notebook.run_job("fashion", "wh", statement_timeout=300) == {"dim_shops": 1}
    factory.assert_called_once_with(None, "fashion", ())
    warehouse.assert_called_once_with(client.return_value.statement_execution, "wh", 300)
    transform.run.assert_called_once_with()
