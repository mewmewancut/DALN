"""Compare E5's period KPIs and all six creation-status counts with Lakebase."""

from datetime import date
from decimal import Decimal

from bronze_ingest import identifier
from dashboard_queries import period_metrics, queries

STATUSES = ("PENDING", "CONFIRMED", "PREPARING", "SHIPPING", "DELIVERED", "CANCELLED")


def verify(sql, source_catalog, target_catalog, start, end):
    if type(start) is not date or type(end) is not date or start > end:
        raise ValueError("Use an ordered pair of calendar dates")
    source = f"{identifier(source_catalog)}.`public`.orders"
    datasets = queries(target_catalog)
    lower, upper = f"DATE '{start.isoformat()}'", f"DATE '{end.isoformat()}'"
    created = (
        f"DATE(from_utc_timestamp(created_at, 'Asia/Ho_Chi_Minh')) BETWEEN {lower} AND {upper}"
    )
    delivered = (
        "status='DELIVERED' AND "
        f"DATE(from_utc_timestamp(delivered_at, 'Asia/Ho_Chi_Minh')) BETWEEN {lower} AND {upper}"
    )
    expected = sql.execute(
        f"SELECT COALESCE(SUM(CASE WHEN {delivered} THEN total_amount ELSE 0 END),0), "
        f"COUNT(CASE WHEN {created} THEN 1 END), "
        f"COUNT(CASE WHEN {created} AND status='CANCELLED' THEN 1 END), "
        f"COUNT(CASE WHEN {delivered} THEN 1 END) FROM {source}"
    )[0]
    actual = sql.execute(period_metrics(datasets["daily"], lower, upper))[0]
    if [Decimal(str(x)) for x in expected] != [Decimal(str(x)) for x in actual[:4]]:
        raise ValueError("Dashboard period KPIs differ from Lakebase")
    revenue, orders, cancelled, delivered_orders = map(lambda x: Decimal(str(x)), expected)
    for result, numerator, denominator in (
        (actual[4], cancelled, orders),
        (actual[5], revenue, delivered_orders),
    ):
        if denominator == 0:
            if result is not None:
                raise ValueError("Dashboard zero-denominator ratio must be NULL")
        elif result is None or abs(Decimal(str(result)) - numerator / denominator) > Decimal(
            "0.000001"
        ):
            raise ValueError("Dashboard ratio must be recalculated from totals")
    expected_statuses = {
        status: int(count)
        for status, count in sql.execute(
            f"SELECT status, COUNT(*) FROM {source} WHERE {created} GROUP BY status"
        )
    }
    actual_statuses = {
        status: int(count)
        for status, count in sql.execute(
            f"SELECT status, SUM(order_count) FROM ({datasets['statuses']}) "
            f"WHERE date BETWEEN {lower} AND {upper} GROUP BY status"
        )
    }
    if (
        set(expected_statuses) - set(STATUSES)
        or set(actual_statuses) - set(STATUSES)
        or any(actual_statuses.get(s, 0) != expected_statuses.get(s, 0) for s in STATUSES)
    ):
        raise ValueError("Dashboard status distribution differs from Lakebase creation dates")
    for name in ("shops", "products", "stock"):
        # Force each snapshot query to execute; missing columns/tables fail acceptance.
        sql.execute(datasets[name])
    return {"revenue": revenue, "orders": int(orders), "statuses": actual_statuses}
