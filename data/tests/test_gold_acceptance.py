from unittest.mock import Mock

import pytest

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
