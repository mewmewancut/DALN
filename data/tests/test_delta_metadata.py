from threading import Barrier, Lock
from unittest.mock import Mock, patch

import pytest

from bronze_ingest import IngestionError
from delta_metadata import describe_many


def test_prefetch_deduplicates_tables_and_bounds_parallel_reads():
    lock = Lock()
    barrier = Barrier(2, timeout=5)
    state = {"active": 0, "maximum": 0, "calls": []}
    spark = Mock()

    def snapshot(session, name):
        assert session is spark
        with lock:
            state["active"] += 1
            state["maximum"] = max(state["maximum"], state["active"])
            state["calls"].append(name)
        barrier.wait()
        with lock:
            state["active"] -= 1
        return {"id": name, "version": 1}

    with patch("delta_metadata.table_snapshot", side_effect=snapshot):
        result = describe_many(spark, ["a", "b", "a", "c", "d", "b"])
    assert set(state["calls"]) == set(result) == {"a", "b", "c", "d"}
    assert len(state["calls"]) == 4
    assert state["maximum"] == 2
    assert result["a"] == {"id": "a", "version": 1}


def test_metadata_failure_does_not_return_partial_state_or_expose_payload():
    with patch("delta_metadata.table_snapshot", side_effect=RuntimeError("private payload")):
        with pytest.raises(
            IngestionError, match=r"Delta metadata failed \(RuntimeError\)"
        ) as error:
            describe_many(Mock(), ["a", "b"])
    assert "private payload" not in str(error.value)
