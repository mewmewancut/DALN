"""Overwrite the six E3 Delta tables; no append, MERGE or Gold skip checkpoints."""

import time

from bronze_ingest import identifier
from gold_queries import GOLD_TABLES, build_query


class GoldTransform:
    def __init__(self, sql, target_catalog="fashion", *, report=print):
        self.sql = sql
        catalog = identifier(target_catalog)
        self.silver = f"{catalog}.`silver`"
        self.gold = f"{catalog}.`gold`"
        self.report = report

    def run(self):
        self.sql.execute(f"CREATE SCHEMA IF NOT EXISTS {self.gold}")
        # DELIVERED without a delivery date cannot be assigned to the C9 reporting period.
        # Fail before writing Gold instead of publishing revenue under a NULL date.
        invalid = int(
            self.sql.execute(
                f"SELECT COUNT(*) FROM {self.silver}.fact_orders "
                "WHERE shop_id IS NULL OR created_date_vn IS NULL "
                "OR (status = 'DELIVERED' AND delivered_date_vn IS NULL)"
            )[0][0]
        )
        if invalid:
            raise ValueError("Gold requires shop_id/created date and a date for delivered orders")
        counts = {}
        started = time.monotonic()
        for table in GOLD_TABLES:
            table_started = time.monotonic()
            self.report(f"START {table}", flush=True)
            target = f"{self.gold}.{identifier(table)}"
            query = build_query(table, self.silver, self.gold)
            self.sql.execute(
                f"CREATE TABLE IF NOT EXISTS {target} USING DELTA AS "
                f"SELECT * FROM ({query}) projected WHERE FALSE"
            )
            # Full data replacement is one Delta commit, including an empty result.
            # INSERT OVERWRITE works on both Databricks and the local Delta test runtime.
            self.sql.execute(f"INSERT OVERWRITE TABLE {target} {query}")
            counts[table] = int(self.sql.execute(f"SELECT COUNT(*) FROM {target}")[0][0])
            self.report(
                f"DONE {table}: {counts[table]} rows; {time.monotonic() - table_started:.1f}s",
                flush=True,
            )
        self.report(f"Gold completed: 6 tables; {time.monotonic() - started:.1f}s", flush=True)
        return counts
