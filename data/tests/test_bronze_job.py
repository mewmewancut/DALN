import importlib.util
from pathlib import Path
from threading import Barrier, Event, Lock, get_ident
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from conftest import SparkSQL

from bronze_ingest import TABLES, IngestionError

spec = importlib.util.spec_from_file_location(
    "bronze_job", Path(__file__).resolve().parents[1] / "01_bronze_job.py"
)
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)


class CountSQL:
    def execute(self, statement):
        if statement.startswith("SELECT COUNT(*),"):
            return [(1, 1, 1)]
        if statement.startswith("SELECT COUNT(*)"):
            return [(1,)]
        if statement.startswith("SHOW COLUMNS"):
            return [("id",), ("_ingested_at",)]
        return []


def test_parallel_job_bounds_work_and_isolates_clients_and_reports_progress():
    lock = Lock()
    first_wave = Barrier(2)
    active = peak = 0
    threads = {}
    statements = []

    class TimedSQL(CountSQL):
        def execute(self, statement):
            nonlocal active, peak
            thread = get_ident()
            with lock:
                threads.setdefault(thread, set()).add(id(self))
                statements.append(statement)
                if statement.startswith("CREATE TABLE `fashion`.`bronze`.`_ingest_"):
                    active += 1
                    peak = max(peak, active)
            if statement.startswith("CREATE TABLE `fashion`.`bronze`.`_ingest_"):
                if "_users_" in statement or "_shops_" in statement:
                    first_wave.wait(timeout=5)
            if statement.startswith("DROP TABLE"):
                with lock:
                    active -= 1
            return super().execute(statement)

    report = Mock()
    counts = job.run_job("source", "warehouse", sql_factory=TimedSQL, report=report)
    assert counts == dict.fromkeys(TABLES, 1)
    assert list(counts) == list(TABLES)
    assert peak == 2 and active == 0
    assert all(len(clients) == 1 for clients in threads.values())
    assert len(threads) == 3  # bootstrap plus two workers
    assert len([sql for sql in statements if sql.startswith("MERGE")]) == 13
    messages = [call.args[0] for call in report.call_args_list]
    assert len([m for m in messages if m.startswith("DONE")]) == 13
    assert messages[-1].startswith("Bronze job completed: 13 tables;")


def test_failure_stops_new_work_and_waits_for_inflight_cleanup(monkeypatch):
    first_wave = Barrier(2)
    failing_cleanup = Event()
    failure_observed = Event()
    cleaned = []
    started = []
    report = Mock()

    original_wait = job.wait

    def observe_failure(*args, **kwargs):
        finished, pending = original_wait(*args, **kwargs)
        if any(future.exception() is not None for future in finished):
            failure_observed.set()
        return finished, pending

    monkeypatch.setattr(job, "wait", observe_failure)

    class FailingSQL(CountSQL):
        def execute(self, statement):
            if statement.startswith("CREATE TABLE `fashion`.`bronze`.`_ingest_"):
                started.append(statement)
                first_wave.wait(timeout=5)
                if "_users_" in statement:
                    raise RuntimeError("private server payload")
                assert failing_cleanup.wait(timeout=5)
                # Keep this worker active until the coordinator has observed the failure.
                assert failure_observed.wait(timeout=5)
            if statement.startswith("DROP TABLE"):
                cleaned.append(statement)
                if "_users_" in statement:
                    failing_cleanup.set()
            return super().execute(statement)

    with pytest.raises(IngestionError, match="RuntimeError") as error:
        job.run_job("source", "warehouse", sql_factory=FailingSQL, report=report)
    assert "private" not in str(error.value)
    assert len(started) == len(cleaned) == 2
    assert not any("job completed" in call.args[0] for call in report.call_args_list)


@pytest.mark.parametrize("parallelism", [0, 5, 1.5, True])
def test_invalid_configuration_never_creates_clients(parallelism):
    factory = Mock()
    with pytest.raises(ValueError, match="parallelism"):
        job.run_job("source", "warehouse", parallelism=parallelism, sql_factory=factory)
    factory.assert_not_called()


@pytest.mark.parametrize(
    "source, warehouse, timeout",
    [("bad.name", "warehouse", 600), ("source", "", 600), ("source", "warehouse", 0)],
)
def test_bad_namespace_or_timeout_never_creates_clients(source, warehouse, timeout):
    factory = Mock()
    with pytest.raises(ValueError):
        job.run_job(source, warehouse, statement_timeout=timeout, sql_factory=factory)
    factory.assert_not_called()


def test_job_widgets_configure_single_refresh_without_acceptance_switch(monkeypatch):
    values = {
        "source_catalog": "source",
        "source_schema": "public",
        "warehouse_id": "warehouse",
        "target_catalog": "fashion",
        "parallelism": "2",
        "statement_timeout": "600",
    }
    widgets = Mock()
    widgets.get.side_effect = values.__getitem__
    run = Mock()
    monkeypatch.setattr(job, "run_job", run)
    job.notebook_main(SimpleNamespace(widgets=widgets))
    run.assert_called_once_with("source", "warehouse", "public", "fashion", 2, 600)
    assert "check_twice" not in [call.args[0] for call in widgets.get.call_args_list]


def test_parallel_job_merges_real_delta_twice_and_keeps_source_counts(sql):
    for table in TABLES:
        sql.execute(f"CREATE TABLE source.{table} (id BIGINT, name STRING) USING DELTA")
        if table != "reviews":
            sql.execute(f"INSERT INTO source.{table} VALUES (1, 'original')")

    def factory():
        return SparkSQL(sql.spark)

    args = ("spark_catalog", "warehouse", "source", "spark_catalog")
    first = job.run_job(*args, sql_factory=factory, report=Mock())
    sql.execute("UPDATE source.users SET name = 'updated' WHERE id = 1")
    sql.execute("INSERT INTO source.orders VALUES (2, 'new')")
    second = job.run_job(*args, sql_factory=factory, report=Mock())
    assert first == {table: 0 if table == "reviews" else 1 for table in TABLES}
    assert second == {**first, "orders": 2}
    for table in TABLES:
        assert sql.execute(f"SELECT COUNT(*) FROM bronze.{table}")[0][0] == second[table]
    assert sql.execute("SELECT name FROM bronze.users")[0][0] == "updated"
    assert not any(
        row.tableName.startswith("_ingest_") for row in sql.execute("SHOW TABLES IN bronze")
    )
