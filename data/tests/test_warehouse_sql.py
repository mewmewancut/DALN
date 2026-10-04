from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from databricks.sdk.service.sql import StatementState

from bronze_ingest import IngestionError
from warehouse_sql import WarehouseSQL


def response(state, rows=None, truncated=False, statement_id="statement-1"):
    return SimpleNamespace(
        statement_id=statement_id,
        status=SimpleNamespace(state=StatementState(state)),
        manifest=SimpleNamespace(truncated=truncated),
        result=SimpleNamespace(data_array=rows),
    )


def test_polls_until_success_and_returns_count_data():
    api = Mock()
    api.execute_statement.return_value = response("PENDING")
    api.get_statement.side_effect = [response("RUNNING"), response("SUCCEEDED", [["13"]])]
    result = WarehouseSQL(api, "warehouse-1", sleep=Mock()).execute("SELECT COUNT(*) FROM table")
    assert result == [["13"]]
    assert api.get_statement.call_count == 2
    api.cancel_execution.assert_not_called()


def test_short_sql_returns_without_polling_or_sleeping():
    api = Mock()
    api.execute_statement.return_value = response("SUCCEEDED", [["13"]])
    sleep = Mock()
    assert WarehouseSQL(api, "warehouse-1", sleep=sleep).execute("SELECT COUNT(*)") == [["13"]]
    assert api.execute_statement.call_args.kwargs["wait_timeout"] == "10s"
    api.get_statement.assert_not_called()
    sleep.assert_not_called()


@pytest.mark.parametrize("timeout, wait_timeout", [(5, "5s"), (8, "8s"), (3, "0s")])
def test_submission_wait_does_not_exceed_statement_deadline(timeout, wait_timeout):
    api = Mock()
    api.execute_statement.return_value = response("SUCCEEDED")
    WarehouseSQL(api, "warehouse", timeout=timeout).execute("SELECT 1")
    assert api.execute_statement.call_args.kwargs["wait_timeout"] == wait_timeout


@pytest.mark.parametrize("state", ["FAILED", "CANCELED", "CLOSED"])
def test_terminal_failures_do_not_pass_or_log_server_error_payloads(state):
    api = Mock()
    failed = response(state)
    failed.status.error = SimpleNamespace(message="private operational data")
    api.execute_statement.return_value = failed
    with pytest.raises(IngestionError, match=state) as error:
        WarehouseSQL(api, "warehouse").execute("MERGE")
    assert "private" not in str(error.value)
    api.cancel_execution.assert_not_called()


def test_timeout_requests_cancel_and_preserves_timeout_when_cancel_fails():
    api = Mock()
    api.execute_statement.return_value = response("RUNNING")
    api.cancel_execution.side_effect = RuntimeError("cannot cancel")
    with pytest.raises(IngestionError, match="timeout"):
        WarehouseSQL(api, "warehouse", clock=Mock(side_effect=[0, 601])).execute("MERGE")
    api.cancel_execution.assert_called_once_with("statement-1")


def test_poll_failure_requests_cancel():
    api = Mock()
    api.execute_statement.return_value = response("RUNNING")
    api.get_statement.side_effect = ConnectionError("network failed")
    with pytest.raises(ConnectionError):
        WarehouseSQL(api, "warehouse", sleep=Mock()).execute("MERGE")
    api.cancel_execution.assert_called_once_with("statement-1")


def test_rejects_truncated_results_and_missing_statement_id():
    api = Mock()
    api.execute_statement.return_value = response("SUCCEEDED", [["1"]], truncated=True)
    with pytest.raises(IngestionError, match="truncated"):
        WarehouseSQL(api, "warehouse").execute("SELECT")
    api.execute_statement.return_value = response("RUNNING", statement_id=None)
    with pytest.raises(IngestionError, match="invalid"):
        WarehouseSQL(api, "warehouse").execute("SELECT")


def test_completed_ddl_without_result_and_nonpositive_timeout():
    api = Mock()
    finished = response("SUCCEEDED")
    finished.result = None
    api.execute_statement.return_value = finished
    assert WarehouseSQL(api, "warehouse").execute("CREATE SCHEMA") == []
    with pytest.raises(ValueError, match="positive"):
        WarehouseSQL(api, "warehouse", timeout=0)
