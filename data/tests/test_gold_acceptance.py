from unittest.mock import Mock

import pytest

import gold_acceptance
from gold_acceptance import verify
from gold_queries import GOLD_TABLES


def test_acceptance_checks_six_projections_and_independent_source_totals_read_only():
    sql = Mock()
    sql.execute.side_effect = [[[2, 0, 0]]] * 6 + [
        [["1234567890123", 12, 5]],
        [["1234567890123", 12, 5, "1234567890123", 12]],
    ]
    assert verify(sql, "source") == dict.fromkeys(GOLD_TABLES, 2)
    statements = [call.args[0] for call in sql.execute.call_args_list]
    assert all(statement.startswith("SELECT") for statement in statements)
    assert "`source`.`public`.orders" in statements[-2]


@pytest.mark.parametrize("missing,extra", [(1, 0), (0, 1)])
def test_acceptance_rejects_missing_or_duplicate_or_changed_projection(missing, extra):
    sql = Mock()
    sql.execute.return_value = [[2, missing, extra]]
    with pytest.raises(ValueError, match="revenue_daily"):
        verify(sql, "source")


@pytest.mark.parametrize("wrong_index", range(5))
def test_acceptance_rejects_each_source_total_mismatch(wrong_index):
    sql = Mock()
    actual = [100, 12, 5, 100, 12]
    actual[wrong_index] += 1
    sql.execute.side_effect = [[[2, 0, 0]]] * 6 + [[[100, 12, 5]], [actual]]
    with pytest.raises(ValueError, match="totals differ"):
        verify(sql, "source")


@pytest.mark.parametrize("catalog_arg", ["source_catalog", "target_catalog"])
def test_acceptance_rejects_unsafe_identifiers_before_queries(catalog_arg):
    sql = Mock()
    args = {"source_catalog": "source", "target_catalog": "fashion"}
    args[catalog_arg] = "catalog; DROP TABLE orders"
    with pytest.raises(ValueError):
        verify(sql, **args)
    sql.execute.assert_not_called()


@pytest.mark.parametrize("fails", [False, True])
def test_cli_distinguishes_e3_acceptance_from_e4_and_fails_without_leaking_data(
    monkeypatch, capsys, fails
):
    monkeypatch.setattr(
        "sys.argv", ["gold_acceptance", "--source-catalog", "source", "--warehouse-id", "wh"]
    )
    client = Mock()
    monkeypatch.setattr("databricks.sdk.WorkspaceClient", Mock(return_value=client))
    verify_mock = Mock(return_value=dict.fromkeys(GOLD_TABLES, 0))
    if fails:
        verify_mock.side_effect = ValueError("private operational row must not be logged")
    monkeypatch.setattr(gold_acceptance, "verify", verify_mock)
    if fails:
        with pytest.raises(SystemExit) as error:
            gold_acceptance.main()
        assert error.value.code == 1
        output = capsys.readouterr()
        assert "PASS" not in output.out
        assert "E3 acceptance failed (ValueError)" in output.err
        assert "private operational row" not in output.err
    else:
        gold_acceptance.main()
        output = capsys.readouterr()
        assert all(f"PASS gold.{table}: 0 rows" in output.out for table in GOLD_TABLES)
        assert "E3 acceptance does not certify the E4 gate" in output.out
        assert "not yet implemented" not in output.out
        assert not output.err
    adapter, source, target = verify_mock.call_args.args
    assert adapter.api is client.statement_execution
    assert adapter.warehouse_id == "wh"
    assert (source, target) == ("source", "fashion")
