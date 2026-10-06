import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import quality_acceptance


@pytest.fixture
def cli(monkeypatch):
    import databricks.sdk

    client = Mock()
    task = SimpleNamespace(
        notebook_task=SimpleNamespace(base_parameters={"target_catalog": "fashion"})
    )
    client.jobs.get.return_value = SimpleNamespace(settings=SimpleNamespace(tasks=[task]))
    client.jobs.list_runs.return_value = []
    client.jobs.run_now.return_value.result.return_value = SimpleNamespace(
        run_id=42, state=SimpleNamespace(result_state=SimpleNamespace(value="SUCCESS"))
    )
    monkeypatch.setattr(databricks.sdk, "WorkspaceClient", lambda **kwargs: client)
    monkeypatch.setattr(quality_acceptance, "WarehouseSQL", lambda *args: Mock())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "quality_acceptance",
            "--source-catalog",
            "daln_source",
            "--warehouse-id",
            "fake-warehouse",
            "--job-id",
            "42",
        ],
    )

    # Exercise the real Job callback twice, as the separately tested E4 gate does.
    def gate(sql, pipeline, source, target):
        pipeline()
        pipeline()
        return {"revenue": 123, "orders": 4}

    monkeypatch.setattr(quality_acceptance, "run_gate", gate)
    return client, task


def test_cli_waits_for_two_successful_job_runs_before_reporting_totals(cli, capsys):
    client, _ = cli
    quality_acceptance.main()
    assert client.jobs.run_now.call_count == 2
    assert "Revenue: 123 VND; orders: 4" in capsys.readouterr().out


@pytest.mark.parametrize("invalid", ["target", "excluded", "tasks", "active"])
def test_cli_rejects_unsafe_job_configuration_before_any_pipeline_run(cli, invalid):
    client, task = cli
    if invalid == "target":
        task.notebook_task.base_parameters["target_catalog"] = "other"
    elif invalid == "excluded":
        task.notebook_task.base_parameters["excluded_shop_ids"] = "7"
    elif invalid == "tasks":
        client.jobs.get.return_value.settings.tasks.append(task)
    else:
        client.jobs.list_runs.return_value = [SimpleNamespace(run_id=1)]
    with pytest.raises(SystemExit) as caught:
        quality_acceptance.main()
    assert caught.value.code != 0
    client.jobs.run_now.assert_not_called()


@pytest.mark.parametrize("result", ["FAILED", "CANCELED", None])
def test_cli_failed_job_never_reports_success_or_starts_second_run(cli, capsys, result):
    client, _ = cli
    client.jobs.run_now.return_value.result.return_value.state.result_state = result
    with pytest.raises(SystemExit) as caught:
        quality_acceptance.main()
    assert caught.value.code != 0
    assert client.jobs.run_now.call_count == 1
    assert "Revenue:" not in capsys.readouterr().out
