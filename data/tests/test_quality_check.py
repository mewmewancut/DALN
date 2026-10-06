from unittest.mock import Mock

import pytest

from bronze_ingest import TABLES, IngestionError
from quality_check import run_gate, source_snapshot


def source(count=2, fingerprint=100):
    return [(table, count, fingerprint) for table in TABLES]


def captured(revenue="123456789012345678", orders=2, bronze=2, invalid=(0, 0, 0, 0)):
    return [
        [["123456789012345678", 2]],
        [[revenue, orders]],
        [(table, bronze) for table in TABLES],
        [invalid],
    ]


def make_sql(first=None, second=None, changed=False):
    sql = Mock()
    sql.execute.side_effect = (
        [source(), source()]
        + (first or captured())
        + [source(), source(fingerprint=101) if changed else source()]
        + (second or captured())
        + [source()]
    )
    return sql


def test_gate_runs_pipeline_twice_and_prints_all_five_checks_using_exact_money():
    sql, pipeline, report = make_sql(), Mock(), Mock()
    result = run_gate(sql, pipeline, "lakebase", report=report)
    assert pipeline.call_count == 2
    assert result["orders"] == 2
    lines = [c.args[0] for c in report.call_args_list]
    assert len([line for line in lines if line.startswith("PASS E4 ")]) == 6
    assert all(c.args[0].startswith("SELECT") for c in sql.execute.call_args_list)
    assert "`lakebase`.`public`.orders" in sql.execute.call_args_list[2].args[0]


@pytest.mark.parametrize(
    "kwargs,failed",
    [({"revenue": 1}, "1 revenue"), ({"orders": 1}, "2 order"), ({"bronze": 1}, "3 all")],
)
def test_gate_fails_mismatches_in_either_run_and_still_reports_all_checks(kwargs, failed):
    report = Mock()
    with pytest.raises(IngestionError, match="gate failed"):
        run_gate(make_sql(second=captured(**kwargs)), Mock(), "lakebase", report=report)
    lines = [c.args[0] for c in report.call_args_list]
    assert any(line.startswith(f"FAIL E4 {failed}") for line in lines)
    assert any(line.startswith("PASS E4 5") for line in lines)
    assert "PASS E4 gate (5/5)" not in lines


@pytest.mark.parametrize("index", range(4))
def test_gate_rejects_negative_inventory_and_invalid_status_even_if_silver_drops_bad_rows(index):
    invalid = [0] * 4
    invalid[index] = 1
    with pytest.raises(IngestionError, match="gate failed"):
        run_gate(make_sql(first=captured(invalid=invalid)), Mock(), "lakebase", report=Mock())


def test_gate_rejects_changed_source_with_equal_row_counts():
    with pytest.raises(IngestionError, match="Lakebase changed"):
        run_gate(make_sql(changed=True), Mock(), "lakebase", report=Mock())


def test_pipeline_failure_does_not_run_second_pipeline_or_report_pass():
    pipeline, report = Mock(side_effect=RuntimeError("job failed")), Mock()
    with pytest.raises(RuntimeError, match="job failed"):
        run_gate(make_sql(), pipeline, "lakebase", report=report)
    assert pipeline.call_count == 1
    assert not any(c.args[0].startswith("PASS") for c in report.call_args_list)


@pytest.mark.parametrize("rows", [source()[:-1], source() + [source()[0]]])
def test_gate_rejects_missing_or_duplicate_source_tables(rows):
    sql, pipeline = Mock(), Mock()
    sql.execute.return_value = rows
    with pytest.raises(IngestionError, match="all 13"):
        run_gate(sql, pipeline, "lakebase", report=Mock())
    pipeline.assert_not_called()


def test_gate_rejects_catalog_injection_without_running_sql():
    sql = Mock()
    with pytest.raises(ValueError):
        run_gate(sql, Mock(), "bad.name", report=Mock())
    sql.execute.assert_not_called()


def test_source_fingerprint_detects_updates_without_count_change_on_spark(sql):
    for table in TABLES:
        sql.execute(f"CREATE TABLE source.{table} (id BIGINT, value STRING) USING DELTA")
        sql.execute(f"INSERT INTO source.{table} VALUES (1, 'before')")
    before = source_snapshot(sql, "source")
    sql.execute("UPDATE source.shops SET value='after' WHERE id=1")
    after = source_snapshot(sql, "source")
    assert before["shops"][0] == after["shops"][0] == 1
    assert before["shops"][1] != after["shops"][1]
    assert all(before[t] == after[t] for t in TABLES if t != "shops")
