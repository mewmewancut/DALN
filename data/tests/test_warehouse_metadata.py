import io
from threading import Barrier, Lock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bronze_ingest import IngestionError
from warehouse_metadata import WarehouseMetadata


def test_reads_live_delta_identity_and_version_without_business_data():
    reader = WarehouseMetadata(Mock(), "wh")
    name = "`catalog`.`bronze`.`users`"
    reader.execute = Mock(side_effect=[[["delta", "table-id"]], [[name, "12", "read-token"]]])
    assert reader.snapshot_many([name, name]) == {name: {"id": "table-id", "version": 12}}
    assert reader.execute.call_count == 2
    query = reader.execute.call_args.args[0]
    assert "uuid() AS read_token" in query
    assert f"DESCRIBE HISTORY {name} LIMIT 1" in query


@pytest.mark.parametrize("detail", [[], [["parquet", "id"]], [["delta", None]]])
def test_incomplete_metadata_is_not_a_valid_snapshot(detail):
    reader = WarehouseMetadata(Mock(), "wh")
    reader.execute = Mock(return_value=detail)
    with pytest.raises(IngestionError):
        reader.detail("table")


@pytest.mark.parametrize("rows", [[], [["a", "1", "x"], ["a", "1", "y"]], [["a", "-1", "x"]]])
def test_missing_duplicate_or_negative_versions_never_certify_skip(rows):
    reader = WarehouseMetadata(Mock(), "wh")
    reader.detail = Mock(return_value="table-id")
    reader.execute = Mock(return_value=rows)
    with pytest.raises(IngestionError):
        reader.snapshot_many(["a"])


def test_checkpoint_download_is_read_only_and_closes_stream():
    client = Mock()
    stream = io.BytesIO(b'{"processed_version": 4}')
    client.files.download.return_value = SimpleNamespace(contents=stream)
    reader = WarehouseMetadata(client, "wh")
    assert reader.marker("/Volumes/c/s/v/source.json") == {"processed_version": 4}
    assert stream.closed
    assert client.mock_calls == [("files.download", ("/Volumes/c/s/v/source.json",), {})]


def test_one_deadline_limits_all_reads_and_no_request_is_sent_after_expiry():
    client = Mock()
    reader = WarehouseMetadata(client, "wh", timeout=60, clock=Mock(side_effect=[0, 30, 61]))
    assert reader.remaining() == 30
    with pytest.raises(TimeoutError):
        reader.execute("DESCRIBE HISTORY table LIMIT 1")
    assert client.mock_calls == []


def test_parallel_metadata_reads_are_bounded_and_deduplicated():
    reader = WarehouseMetadata(Mock(), "wh")
    barrier, lock = Barrier(4, timeout=5), Lock()
    active = 0
    maximum = 0

    def read(name):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        barrier.wait()
        with lock:
            active -= 1
        return name

    names = [str(i) for i in range(8)]
    assert reader.read_many(read, names + names) == dict(zip(names, names, strict=True))
    assert maximum == 4
