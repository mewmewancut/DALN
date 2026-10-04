"""Read Delta metadata/checkpoints without starting a notebook Spark session."""

import json
import time
from concurrent.futures import ThreadPoolExecutor

from bronze_ingest import IngestionError
from warehouse_sql import WarehouseSQL


class WarehouseMetadata:
    def __init__(self, client, warehouse_id, timeout=60, *, clock=time.monotonic):
        self.client = client
        self.warehouse_id = warehouse_id
        self.clock = clock
        self.deadline = clock() + timeout

    def remaining(self):
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise TimeoutError("Metadata preflight exceeded its deadline")
        return remaining

    def execute(self, statement):
        return WarehouseSQL(
            self.client.statement_execution,
            self.warehouse_id,
            timeout=self.remaining(),
            clock=self.clock,
        ).execute(statement)

    def detail(self, name):
        detail = self.execute(f"DESCRIBE DETAIL {name}")
        if not detail or detail[0][0] != "delta" or not detail[0][1]:
            raise IngestionError("Incomplete Delta metadata")
        return detail[0][1]

    def snapshot_many(self, names):
        names = tuple(dict.fromkeys(names))
        if not names:
            return {}
        identities = self.read_many(self.detail, names)
        # Databricks supports DESCRIBE HISTORY as a relation. One round trip for all
        # versions; never scan business rows or rely on a cached SQL result for SKIP.
        query = " UNION ALL ".join(
            f"SELECT '{name}' AS name, version FROM (DESCRIBE HISTORY {name} LIMIT 1)"
            for name in names
        )
        # A nondeterministic projected expression prevents SQL result-cache reuse.
        rows = self.execute(f"SELECT name, version, uuid() AS read_token FROM ({query})")
        snapshots = {
            name: {"id": identities[name], "version": int(version)} for name, version, _ in rows
        }
        if len(rows) != len(names) or set(snapshots) != set(names):
            raise IngestionError("Incomplete Delta versions")
        if any(value["version"] < 0 for value in snapshots.values()):
            raise IngestionError("Invalid Delta version")
        return snapshots

    def marker(self, path):
        self.remaining()
        with self.client.files.download(path).contents as contents:
            return json.load(contents)

    def read_many(self, read, names):
        names = tuple(dict.fromkeys(names))
        # Bound warehouse concurrency and share one deadline across every read.
        with ThreadPoolExecutor(max_workers=4) as pool:
            return dict(zip(names, pool.map(read, names), strict=True))
