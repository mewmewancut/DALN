"""SQL ingestion shared by the warehouse runner and real Delta integration tests."""

import re
import sys
from uuid import uuid4

TABLES = (
    "users",
    "shops",
    "categories",
    "products",
    "product_variants",
    "inventory",
    "suppliers",
    "purchase_orders",
    "purchase_order_items",
    "orders",
    "order_items",
    "order_status_history",
    "reviews",
)


class IngestionError(RuntimeError):
    """A run failed validation or could not safely finish."""


def identifier(value):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", value):
        raise ValueError("Catalog/schema identifiers must contain only letters, digits, _ or -")
    return f"`{value}`"


class BronzeIngest:
    def __init__(self, sql, source_catalog, source_schema="public", target_catalog="fashion"):
        self.sql = sql
        self.source = f"{identifier(source_catalog)}.{identifier(source_schema)}"
        self.target = f"{identifier(target_catalog)}.`bronze`"
        if self.source.lower() == self.target.lower():
            raise ValueError("Source and target namespaces must differ")

    def count(self, table):
        return int(self.sql.execute(f"SELECT COUNT(*) FROM {table}")[0][0])

    def run(self):
        self.sql.execute(f"CREATE SCHEMA IF NOT EXISTS {self.target}")
        return {table: self.ingest_table(table) for table in TABLES}

    def ingest_table(self, table):
        if table not in TABLES:
            raise ValueError("Table is outside Planning E1")
        source = f"{self.source}.{identifier(table)}"
        target = f"{self.target}.{identifier(table)}"
        stage = f"{self.target}.`_ingest_{table}_{uuid4().hex}`"
        try:
            # Materialize once: key validation and MERGE read the same source snapshot.
            self.sql.execute(
                f"CREATE TABLE {stage} USING DELTA AS "
                f"SELECT s.*, current_timestamp() AS _ingested_at FROM {source} AS s"
            )
            rows, nonnull, unique = map(
                int,
                self.sql.execute(f"SELECT COUNT(*), COUNT(id), COUNT(DISTINCT id) FROM {stage}")[0],
            )
            if rows != nonnull or rows != unique:
                raise IngestionError(f"{table}: source id must be non-null and unique")
            self.sql.execute(
                f"CREATE TABLE IF NOT EXISTS {target} USING DELTA AS "
                f"SELECT * FROM {stage} WHERE FALSE"
            )
            stage_columns = {row[0] for row in self.sql.execute(f"SHOW COLUMNS IN {stage}")}
            target_columns = {row[0] for row in self.sql.execute(f"SHOW COLUMNS IN {target}")}
            if stage_columns != target_columns:
                raise IngestionError(f"{table}: source/Bronze schema differs; migrate explicitly")
            self.sql.execute(
                f"MERGE INTO {target} AS t USING {stage} AS s ON t.id = s.id "
                "WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *"
            )
            actual = self.count(target)
            if actual != rows:
                raise IngestionError(f"{table}: Bronze count {actual} differs from snapshot {rows}")
            return actual
        finally:
            original_error = sys.exception()
            try:
                self.sql.execute(f"DROP TABLE IF EXISTS {stage}")
            except Exception:
                if original_error is None:
                    raise
                original_error.add_note("Staging cleanup failed; remove leftover _ingest_ table")

    def verify_source_counts(self, expected):
        # Use with a quiescent source for the mandatory E1 two-run acceptance check.
        for table in TABLES:
            source = self.count(f"{self.source}.{identifier(table)}")
            bronze = self.count(f"{self.target}.{identifier(table)}")
            if source != bronze or bronze != expected[table]:
                raise IngestionError(f"{table}: live source/Bronze counts differ or source changed")
