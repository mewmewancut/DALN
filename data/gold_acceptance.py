"""Read-only E3 acceptance; the full Planning E4 gate is a separate task."""

import argparse
from decimal import Decimal

from bronze_ingest import identifier
from gold_queries import GOLD_TABLES, build_query
from warehouse_sql import WarehouseSQL


def verify(sql, source_catalog, target_catalog="fashion"):
    source = f"{identifier(source_catalog)}.`public`"
    silver = f"{identifier(target_catalog)}.`silver`"
    gold = f"{identifier(target_catalog)}.`gold`"
    counts = {}
    for table in GOLD_TABLES:
        target = f"{gold}.{identifier(table)}"
        query = build_query(table, silver, gold)
        actual, missing, extra = map(
            int,
            sql.execute(
                f"SELECT (SELECT COUNT(*) FROM {target}), "
                f"(SELECT COUNT(*) FROM (({query}) EXCEPT ALL (SELECT * FROM {target}))), "
                f"(SELECT COUNT(*) FROM ((SELECT * FROM {target}) EXCEPT ALL ({query})))"
            )[0],
        )
        if missing or extra:
            raise ValueError(f"{table}: Gold differs from the E3 projection")
        counts[table] = actual
    expected_revenue, expected_orders, expected_delivered = sql.execute(
        "SELECT COALESCE(SUM(CASE WHEN status = 'DELIVERED' THEN total_amount ELSE 0 END), 0), "
        "COUNT(*), COUNT(CASE WHEN status = 'DELIVERED' THEN 1 END) "
        f"FROM {source}.orders"
    )[0]
    actual_revenue, actual_orders, actual_delivered, performance_revenue, performance_orders = (
        sql.execute(
            f"SELECT (SELECT COALESCE(SUM(revenue), 0) FROM {gold}.revenue_daily), "
            f"(SELECT COALESCE(SUM(total_orders), 0) FROM {gold}.orders_summary_daily), "
            f"(SELECT COALESCE(SUM(delivered), 0) FROM {gold}.orders_summary_daily), "
            f"(SELECT COALESCE(SUM(revenue), 0) FROM {gold}.shop_performance), "
            f"(SELECT COALESCE(SUM(total_orders), 0) FROM {gold}.shop_performance)"
        )[0]
    )
    if (
        Decimal(str(expected_revenue)) != Decimal(str(actual_revenue))
        or Decimal(str(expected_revenue)) != Decimal(str(performance_revenue))
        or int(expected_orders) != int(actual_orders)
        or int(expected_orders) != int(performance_orders)
        or int(expected_delivered) != int(actual_delivered)
    ):
        raise ValueError("Gold revenue/order totals differ from Lakebase")
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-catalog", required=True)
    parser.add_argument("--target-catalog", default="fashion")
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--profile")
    args = parser.parse_args()
    from databricks.sdk import WorkspaceClient

    sql = WarehouseSQL(WorkspaceClient(profile=args.profile).statement_execution, args.warehouse_id)
    try:
        counts = verify(sql, args.source_catalog, args.target_catalog)
    except Exception as error:
        parser.exit(1, f"E3 acceptance failed ({type(error).__name__}); inspect diagnostics\n")
    for table, count in counts.items():
        print(f"PASS gold.{table}: {count} rows")
    print("PASS Gold totals vs Lakebase; E3 acceptance does not certify the E4 gate")


if __name__ == "__main__":
    main()
