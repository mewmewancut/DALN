"""Isolated reconciliation worker; no management credential is passed to the web API."""

import argparse
import json
import os
import time
from pathlib import Path

from bronze_ingest import identifier
from genie_provision import provision
from warehouse_sql import WarehouseSQL


def active_shops(sql, source_catalog):
    source = identifier(source_catalog)
    return tuple(
        sorted(
            int(r[0])
            for r in sql.execute(
                f"SELECT s.id FROM {source}.public.shops s JOIN {source}.public.users u "
                "ON u.id = s.owner_id WHERE s.is_active = TRUE AND u.is_active = TRUE "
                "AND u.role = 'SHOP_OWNER' ORDER BY s.id"
            )
        )
    )


def operational_shops(database_url):
    import psycopg

    url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url, connect_timeout=10, options="-c statement_timeout=10000") as conn:
        return tuple(
            int(r[0])
            for r in conn.execute(
                "SELECT s.id FROM shops s JOIN users u ON u.id = s.owner_id "
                "WHERE s.is_active = TRUE AND u.is_active = TRUE "
                "AND u.role = 'SHOP_OWNER' ORDER BY s.id"
            )
        )


def run_worker(
    client,
    sql,
    output,
    *,
    source_catalog="daln_source",
    catalog="fashion",
    interval=60,
    stop=None,
    sleep=time.sleep,
    report=print,
    reconcile=provision,
    read_shops=None,
):
    if interval < 5 or interval > 3600:
        raise ValueError("Interval must be 5..3600 seconds")
    previous = None
    failures = 0
    while stop is None or not stop():
        try:
            shops = read_shops() if read_shops else active_shops(sql, source_catalog)
            if previous != shops or not Path(output).exists():
                reconcile(
                    client, sql, catalog, output, shop_ids=shops, e4_passed=True, report=report
                )
                previous = shops
            failures = 0
        except Exception as error:
            failures += 1
            report(
                f"Genie reconciliation failed ({type(error).__name__}); retry scheduled", flush=True
            )
        sleep(min(300, interval * 2 ** min(failures, 3)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", required=True)
    parser.add_argument("--output", default="/runtime/.env.genie.json")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()
    from databricks.sdk import WorkspaceClient

    try:
        config = json.loads(Path(args.credentials).read_text(encoding="utf-8"))
        if config.get("e4_passed") is not True:
            raise ValueError("E4 gate is required")
        client = WorkspaceClient(
            host=config["host"],
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            auth_type="oauth-m2m",
        )
        sql = WarehouseSQL(client.statement_execution, config["warehouse_id"], timeout=120)
        database_url = os.environ.get("SOURCE_DATABASE_URL", "")
        run_worker(
            client,
            sql,
            args.output,
            interval=args.interval,
            read_shops=(lambda: operational_shops(database_url)) if database_url else None,
        )
    except Exception as error:
        parser.exit(1, f"Genie worker failed ({type(error).__name__})\n")


if __name__ == "__main__":
    main()
