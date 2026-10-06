"""Planning E4 gate: two successful pipeline runs against a stable Lakebase source."""

from decimal import Decimal

from bronze_ingest import TABLES, IngestionError, identifier

STATUSES = "'PENDING','CONFIRMED','PREPARING','SHIPPING','DELIVERED','CANCELLED'"


def source_snapshot(sql, source):
    rows = sql.execute(
        " UNION ALL ".join(
            f"SELECT '{table}', COUNT(*), "
            "COALESCE(SUM(CAST(xxhash64(to_json(struct(*))) AS DECIMAL(38,0))), 0) "
            f"FROM {source}.{identifier(table)}"
            for table in TABLES
        )
    )
    result = {name: (int(count), Decimal(str(fingerprint))) for name, count, fingerprint in rows}
    if len(rows) != len(TABLES) or set(result) != set(TABLES):
        raise IngestionError("Source snapshot must contain all 13 E1 tables")
    return result


def capture(sql, source, target):
    expected_revenue, expected_orders = sql.execute(
        "SELECT COALESCE(SUM(CASE WHEN status='DELIVERED' THEN total_amount ELSE 0 END), 0), "
        f"COUNT(*) FROM {source}.orders"
    )[0]
    revenue, orders = sql.execute(
        f"SELECT (SELECT COALESCE(SUM(revenue), 0) FROM {target}.gold.revenue_daily), "
        f"(SELECT COALESCE(SUM(total_orders), 0) FROM {target}.gold.orders_summary_daily)"
    )[0]
    rows = sql.execute(
        " UNION ALL ".join(
            f"SELECT '{table}', COUNT(*) FROM {target}.bronze.{identifier(table)}"
            for table in TABLES
        )
    )
    counts = {name: int(count) for name, count in rows}
    if len(rows) != len(TABLES) or set(counts) != set(TABLES):
        raise IngestionError("Bronze snapshot must contain all 13 E1 tables")
    invalid_inventory, invalid_source, invalid_bronze, invalid_silver = map(
        int,
        sql.execute(
            f"SELECT (SELECT COUNT(*) FROM {target}.silver.fact_inventory "
            "WHERE quantity < 0 OR quantity IS NULL), "
            f"(SELECT COUNT(*) FROM {source}.orders "
            f"WHERE status IS NULL OR status NOT IN ({STATUSES})), "
            f"(SELECT COUNT(*) FROM {target}.bronze.orders "
            f"WHERE status IS NULL OR status NOT IN ({STATUSES})), "
            f"(SELECT COUNT(*) FROM {target}.silver.fact_orders "
            f"WHERE status IS NULL OR status NOT IN ({STATUSES}))"
        )[0],
    )
    return {
        "source_revenue": Decimal(str(expected_revenue)),
        "source_orders": int(expected_orders),
        "revenue": Decimal(str(revenue)),
        "orders": int(orders),
        "bronze_counts": counts,
        "invalid": (invalid_inventory, invalid_source, invalid_bronze, invalid_silver),
    }


def run_gate(sql, pipeline, source_catalog, target_catalog="fashion", *, report=print):
    source = f"{identifier(source_catalog)}.`public`"
    target = identifier(target_catalog)
    stable = source_snapshot(sql, source)
    snapshots = []
    for number in (1, 2):
        report(f"Running E1 -> E2 -> E3 ({number}/2)", flush=True)
        try:
            pipeline()
            before = source_snapshot(sql, source)
            snapshot = capture(sql, source, target)
            after = source_snapshot(sql, source)
            if stable != before or stable != after:
                raise IngestionError("Lakebase changed during E4; rerun with a stable source")
            snapshots.append(snapshot)
        except Exception:
            report(f"FAIL E4: pipeline/source verification failed on run {number}")
            raise

    checks = [
        ("1 revenue Gold = Lakebase", all(s["revenue"] == s["source_revenue"] for s in snapshots)),
        (
            "2 order count Gold = Lakebase",
            all(s["orders"] == s["source_orders"] for s in snapshots),
        ),
        (
            "3 all 13 Bronze counts = Lakebase",
            all(s["bronze_counts"] == {t: stable[t][0] for t in TABLES} for s in snapshots),
        ),
        (
            "4 revenue/order totals unchanged after two pipeline runs",
            all(snapshots[0][key] == snapshots[1][key] for key in ("revenue", "orders")),
        ),
        (
            "5 nonnegative inventory and valid order statuses",
            all(not any(s["invalid"]) for s in snapshots),
        ),
    ]
    for description, passed in checks:
        report(f"{'PASS' if passed else 'FAIL'} E4 {description}")
    if not all(passed for _, passed in checks):
        raise IngestionError("E4 gate failed; Dashboard/Genie must remain disabled")
    report("PASS E4 gate (5/5)")
    return snapshots[-1]
