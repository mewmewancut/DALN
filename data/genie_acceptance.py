"""Read-only checks of real Genie service-principal isolation before enabling the web UI."""

import argparse
import json
import time
from pathlib import Path

from databricks.sdk import WorkspaceClient

from genie_space import view_name
from gold_queries import GOLD_TABLES
from warehouse_sql import WarehouseSQL


def denied(api, warehouse_id, statement):
    response = api.execute_statement(
        warehouse_id=warehouse_id, statement=statement, wait_timeout="10s"
    )
    deadline = time.monotonic() + 60
    while response.status.state.value in {"PENDING", "RUNNING"}:
        if time.monotonic() >= deadline:
            api.cancel_execution(response.statement_id)
            raise ValueError("Permission check timed out; not a denial")
        time.sleep(1)
        response = api.get_statement(response.statement_id)
    error = response.status.error
    if (
        response.status.state.value != "FAILED"
        or not error
        or "INSUFFICIENT_PERMISSIONS" not in (error.message or "")
    ):
        raise ValueError("Expected Unity Catalog permission denial; do not enable chatbot")


def verify(config, warehouse_id, *, factory=WorkspaceClient, report=print):
    def connect(identity):
        return factory(
            host=config["host"],
            client_id=identity["client_id"],
            client_secret=identity["client_secret"],
            auth_type="oauth-m2m",
        )

    admin = connect(config["admin"])
    admin_sql = WarehouseSQL(admin.statement_execution, warehouse_id)
    # Positive access is checked for all six Gold tables, not just revenue.
    admin_sql.execute(
        " UNION ALL ".join(f"SELECT '{t}', COUNT(*) FROM fashion.gold.{t}" for t in GOLD_TABLES)
    )
    denied(admin.statement_execution, warehouse_id, "SELECT * FROM fashion.bronze.orders LIMIT 1")
    report("PASS admin: six Gold tables readable; Bronze denied", flush=True)
    for shop_id, identity in config["shops"].items():
        shop_id = int(shop_id)
        shop = connect(identity)
        sql = WarehouseSQL(shop.statement_execution, warehouse_id)
        actual = sql.execute(
            " UNION ALL ".join(
                f"SELECT '{t}', COUNT(*), COUNT(CASE "
                f"WHEN shop_id <> {shop_id} OR shop_id IS NULL THEN 1 END) "
                f"FROM fashion.gold.{view_name(t, shop_id)}"
                for t in GOLD_TABLES
            )
        )
        expected = admin_sql.execute(
            " UNION ALL ".join(
                f"SELECT '{t}', COUNT(*) FROM fashion.gold.{t} WHERE shop_id = {shop_id}"
                for t in GOLD_TABLES
            )
        )
        if {r[0]: int(r[1]) for r in actual} != {r[0]: int(r[1]) for r in expected} or any(
            int(r[2]) for r in actual
        ):
            raise ValueError("Shop view scope/count differs from base Gold")
        for table in GOLD_TABLES:
            denied(
                shop.statement_execution,
                warehouse_id,
                f"SELECT * FROM fashion.gold.{table} LIMIT 1",
            )
        other = next((int(s) for s in config["shops"] if int(s) != shop_id), None)
        forbidden = [
            "fashion.bronze.orders",
            "fashion.silver.fact_orders",
            "daln_source.public.orders",
        ]
        if other is not None:
            forbidden.append(f"fashion.gold.{view_name('revenue_daily', other)}")
        for table in forbidden:
            denied(shop.statement_execution, warehouse_id, f"SELECT * FROM {table} LIMIT 1")
        report(
            f"PASS shop {shop_id}: six own views match; base Gold/other shop/raw data denied",
            flush=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="backend/.env.genie.json")
    parser.add_argument("--warehouse-id", required=True)
    args = parser.parse_args()
    try:
        verify(json.loads(Path(args.config).read_text(encoding="utf-8")), args.warehouse_id)
    except Exception as error:
        parser.exit(
            1, f"Genie isolation acceptance failed ({type(error).__name__}); keep web disabled\n"
        )


if __name__ == "__main__":
    main()
