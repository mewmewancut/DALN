"""Materialize and MERGE the seven Planning E2 tables using the shared SQL adapter."""

import sys
import time
from uuid import uuid4

from bronze_ingest import identifier
from silver_queries import SILVER_TABLES, STATUS_SQL, build_query


class TransformationError(RuntimeError):
    """Silver validation or refresh failed."""


def validate_shop_ids(values):
    values = tuple(values)
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
        raise ValueError("excluded_shop_ids must contain positive integer IDs")
    return tuple(sorted(set(values)))


class SilverTransform:
    def __init__(self, sql, target_catalog="fashion", excluded_shop_ids=(), *, report=print):
        self.sql = sql
        catalog = identifier(target_catalog)
        self.bronze = f"{catalog}.`bronze`"
        self.silver = f"{catalog}.`silver`"
        self.excluded_shop_ids = validate_shop_ids(excluded_shop_ids)
        self.report = report

    def columns(self, table):
        return [
            row[0] for row in self.sql.execute(f"SHOW COLUMNS IN {self.bronze}.{identifier(table)}")
        ]

    def run(self):
        self.sql.execute(f"CREATE SCHEMA IF NOT EXISTS {self.silver}")
        counts = {}
        started = time.monotonic()
        for table in SILVER_TABLES:
            table_started = time.monotonic()
            self.report(f"START {table}", flush=True)
            counts[table] = self.transform_table(table)
            self.report(
                f"DONE {table}: {counts[table]} rows; {time.monotonic() - table_started:.1f}s",
                flush=True,
            )
        self.report(
            f"Silver completed: {len(counts)} tables; {time.monotonic() - started:.1f}s", flush=True
        )
        return counts

    def transform_table(self, table):
        query, valid = build_query(
            table, self.bronze, self.silver, self.columns, self.excluded_shop_ids
        )
        target = f"{self.silver}.{identifier(table)}"
        stage = f"{self.silver}.`_silver_{table}_{uuid4().hex}`"
        try:
            # Counts, rejection logs and MERGE all use the same transformed snapshot.
            self.sql.execute(f"CREATE TABLE {stage} USING DELTA AS {query}")
            aggregates = "COUNT(*), COUNT(id), COUNT(DISTINCT id)"
            if valid:
                aggregates += f", COUNT(CASE WHEN {valid} THEN 1 END)"
            if table == "fact_orders":
                aggregates += (
                    f", COUNT(CASE WHEN status IS NULL OR status NOT IN ({STATUS_SQL}) THEN 1 END)"
                    ", COUNT(CASE WHEN total_amount IS NULL OR total_amount <= 0 THEN 1 END)"
                )
            stats = list(map(int, self.sql.execute(f"SELECT {aggregates} FROM {stage}")[0]))
            rows, nonnull, unique = stats[:3]
            if rows != nonnull or rows != unique:
                raise TransformationError(f"{table}: transformed id must be non-null and unique")
            accepted = stats[3] if valid else rows
            if table == "fact_orders":
                self.report(
                    f"REJECT fact_orders: invalid_status={stats[4]}; "
                    f"nonpositive_or_null_amount={stats[5]} (counts may overlap)",
                    flush=True,
                )
            source = f"SELECT * FROM {stage}" + (f" WHERE {valid}" if valid else "")
            if table == "fact_reviews":
                self.report(f"REJECT fact_reviews: invalid_rating={rows - accepted}", flush=True)
            self.sql.execute(
                f"CREATE TABLE IF NOT EXISTS {target} USING DELTA AS "
                f"SELECT * FROM ({source}) accepted WHERE FALSE"
            )
            stage_columns = {row[0] for row in self.sql.execute(f"SHOW COLUMNS IN {stage}")}
            target_columns = {row[0] for row in self.sql.execute(f"SHOW COLUMNS IN {target}")}
            if stage_columns != target_columns:
                raise TransformationError(
                    f"{table}: Bronze/Silver schema differs; migrate explicitly"
                )
            # A row that becomes invalid must also disappear on rerun (including its items).
            self.sql.execute(
                f"MERGE INTO {target} t USING ({source}) s ON t.id = s.id "
                "WHEN MATCHED AND ("
                + " OR ".join(
                    f"NOT (t.{identifier(c)} <=> s.{identifier(c)})" for c in sorted(stage_columns)
                )
                + ") THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT * "
                "WHEN NOT MATCHED BY SOURCE THEN DELETE"
            )
            actual = int(self.sql.execute(f"SELECT COUNT(*) FROM {target}")[0][0])
            if actual != accepted:
                raise TransformationError(
                    f"{table}: Silver count differs from transformed snapshot"
                )
            return actual
        finally:
            original_error = sys.exception()
            try:
                self.sql.execute(f"DROP TABLE IF EXISTS {stage}")
            except Exception:
                if original_error is None:
                    raise
                original_error.add_note(
                    "Silver staging cleanup failed; inspect leftover _silver_ table"
                )
