from unittest.mock import Mock

import pytest

from acceptance import verify
from bronze_ingest import TABLES, IngestionError


def test_acceptance_rejects_mismatched_source_before_silver():
    sql = Mock()
    sql.execute.return_value = [("users", 2, 1, 1, 1)]
    with pytest.raises(IngestionError, match="source/Bronze"):
        verify(sql, "lakebase")
    assert sql.execute.call_count == 1


def test_acceptance_requires_all_tables_and_unique_keys():
    sql = Mock()
    sql.execute.return_value = [("users", 1, 1, 1, 1)]
    with pytest.raises(IngestionError, match="all 13"):
        verify(sql, "lakebase")
    sql.execute.return_value = [(table, 2, 2, 2, 1) for table in TABLES]
    with pytest.raises(IngestionError, match="keys differ"):
        verify(sql, "lakebase")


def test_unsafe_catalog_fails_without_sql():
    sql = Mock()
    with pytest.raises(ValueError):
        verify(sql, "bad.name")
    sql.execute.assert_not_called()


@pytest.mark.parametrize(
    "nonnull,unique,missing,extra", [(0, 1, 0, 0), (1, 0, 0, 0), (1, 1, 1, 0), (1, 1, 0, 1)]
)
def test_silver_acceptance_rejects_bad_keys_or_differing_values(nonnull, unique, missing, extra):
    sql = Mock()
    sql.execute.side_effect = [
        [(table, 1, 1, 1, 1) for table in TABLES],
        [(1, nonnull, unique)],
        [(missing,)],
        [(extra,)],
    ]
    with pytest.raises(IngestionError, match="dim_shops: Silver differs"):
        verify(sql, "lakebase")
