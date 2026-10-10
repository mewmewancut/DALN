from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_gold_transform import gold_sql as gold_sql
from test_gold_transform import seed, transform

import dashboard_deploy
from dashboard_acceptance import verify
from dashboard_definition import build_dashboard
from dashboard_queries import period_metrics, queries


def test_dashboard_reconciles_creation_and_delivery_periods_on_delta(gold_sql):
    sql = gold_sql
    seed(sql)
    transform(sql).run()
    daily = queries("spark_catalog")["daily"]
    metrics = sql.execute(period_metrics(daily, "DATE '2026-10-01'", "DATE '2026-10-01'"))[0]
    assert tuple(metrics[:4]) == (350, 5, 1, 3)
    assert metrics[4] == pytest.approx(1 / 5)
    assert abs(metrics[5] - Decimal(350) / 3) <= Decimal("0.000001")
    statuses = dict(
        sql.execute(
            "SELECT status, SUM(order_count) FROM ("
            + queries("spark_catalog")["statuses"]
            + ") WHERE date=DATE '2026-10-01' GROUP BY status"
        )
    )
    assert statuses == {
        "PENDING": 1,
        "CONFIRMED": 0,
        "PREPARING": 0,
        "SHIPPING": 0,
        "CANCELLED": 1,
        "DELIVERED": 3,
    }
    empty = sql.execute(period_metrics(daily, "DATE '2000-01-01'", "DATE '2000-01-01'"))[0]
    assert tuple(empty) == (0, 0, 0, 0, None, None)
    # Equal display names must remain separate categories in the top charts.
    shops = sql.execute(queries("spark_catalog")["shops"])
    products = sql.execute(queries("spark_catalog")["products"])
    assert all(f"(#{row[0]})" in row[2] for row in shops)
    assert all(f"(#{row[1]}, shop {row[0]})" in row[3] for row in products)


def test_dashboard_has_gold_only_sources_valid_bindings_and_date_scope():
    dashboard = build_dashboard()
    datasets = {d["name"]: "".join(d["queryLines"]) for d in dashboard["datasets"]}
    assert len(datasets) == 5
    assert all("`fashion`.`gold`" in sql for sql in datasets.values())
    assert all("silver" not in sql and "bronze" not in sql for sql in datasets.values())
    widgets = {x["widget"]["name"]: x["widget"] for x in dashboard["pages"][0]["layout"]}
    assert len(widgets) == 10
    bound = {q["query"]["datasetName"] for q in widgets["date_range"]["queries"]}
    assert bound == {"daily", "statuses"}
    for w in widgets.values():
        assert w["spec"]["frame"]["showTitle"]
        for q in w["queries"]:
            assert q["query"]["datasetName"] in datasets
    assert widgets["cancel_rate"]["queries"][0]["query"]["fields"][0]["expression"] == (
        "MEASURE(`Cancellation ratio`)"
    )
    measures = {c["displayName"]: c["expression"] for c in dashboard["datasets"][0]["columns"]}
    assert measures["Cancellation ratio"] == "SUM(`cancelled`)/NULLIF(SUM(`total_orders`),0)"
    assert measures["Delivered AOV"] == "SUM(`revenue`)/NULLIF(SUM(`delivered_orders`),0)"
    assert (
        widgets["aov"]["queries"][0]["query"]["fields"][0]["expression"]
        == "MEASURE(`Delivered AOV`)"
    )
    assert "Toàn thời gian" in widgets["top_shops"]["spec"]["frame"]["description"]
    assert "Snapshot" in widgets["low_stock"]["spec"]["frame"]["description"]
    money = widgets["revenue"]["spec"]["encodings"]["value"]["format"]
    assert money == {
        "type": "number-currency",
        "currencyCode": "VND",
        "abbreviation": "none",
        "decimalPlaces": {"type": "exact", "places": 0},
    }
    ratio = widgets["cancel_rate"]["spec"]["encodings"]["value"]["format"]
    assert ratio == {"type": "number-percent", "decimalPlaces": {"type": "exact", "places": 2}}
    assert widgets["aov"]["spec"]["encodings"]["value"]["format"] == money
    positions = [x["position"] for x in dashboard["pages"][0]["layout"]]
    for i, a in enumerate(positions):
        for b in positions[i + 1 :]:
            assert (
                a["x"] + a["width"] <= b["x"]
                or b["x"] + b["width"] <= a["x"]
                or a["y"] + a["height"] <= b["y"]
                or b["y"] + b["height"] <= a["y"]
            )


def acceptance_sql():
    sql = Mock()
    sql.execute.side_effect = [
        [[300, 3, 1, 2]],
        [[300, 3, 1, 2, 1 / 3, 150]],
        [["DELIVERED", 2], ["CANCELLED", 1]],
        [["DELIVERED", 2], ["CANCELLED", 1]],
        [],
        [],
        [],
    ]
    return sql


def test_acceptance_is_read_only_and_uses_vietnam_source_dates():
    sql = acceptance_sql()
    assert verify(sql, "source", "fashion", date(2026, 10, 1), date(2026, 10, 2))["orders"] == 3
    statements = [c.args[0] for c in sql.execute.call_args_list]
    assert all(s.lstrip().startswith("SELECT") for s in statements)
    assert "Asia/Ho_Chi_Minh" in statements[0]


@pytest.mark.parametrize(
    "row", [[301, 3, 1, 2, 1 / 3, 150], [300, 3, 1, 2, 0.5, 150], [300, 3, 1, 2, 1 / 3, 100]]
)
def test_acceptance_rejects_wrong_totals_or_unweighted_ratios(row):
    sql = acceptance_sql()
    sql.execute.side_effect = [[[300, 3, 1, 2]], [row]]
    with pytest.raises(ValueError):
        verify(sql, "source", "fashion", date(2026, 10, 1), date(2026, 10, 2))


def test_acceptance_rejects_statuses_counted_by_delivery_date():
    sql = acceptance_sql()
    sql.execute.side_effect = [
        [[300, 3, 1, 2]],
        [[300, 3, 1, 2, 1 / 3, 150]],
        [["DELIVERED", 2], ["CANCELLED", 1]],
        [["DELIVERED", 3], ["CANCELLED", 1]],
    ]
    with pytest.raises(ValueError, match="creation dates"):
        verify(sql, "source", "fashion", date(2026, 10, 1), date(2026, 10, 2))


@pytest.mark.parametrize(
    "start,end", [(date(2026, 10, 2), date(2026, 10, 1)), ("unsafe", date(2026, 10, 1))]
)
def test_acceptance_rejects_invalid_date_boundary_before_sql(start, end):
    sql = Mock()
    with pytest.raises(ValueError):
        verify(sql, "source", "fashion", start, end)
    sql.execute.assert_not_called()


def test_deploy_refuses_before_e4_or_after_failed_acceptance(monkeypatch):
    client, sql = Mock(), Mock()
    args = dict(
        source_catalog="source",
        start=date(2026, 10, 1),
        end=date(2026, 10, 2),
        parent_path="/Users/demo",
    )
    with pytest.raises(ValueError, match="E4"):
        dashboard_deploy.deploy(client, sql, **args)
    sql.execute.assert_not_called()
    monkeypatch.setattr(dashboard_deploy, "verify", Mock(side_effect=ValueError("mismatch")))
    with pytest.raises(ValueError, match="mismatch"):
        dashboard_deploy.deploy(client, sql, **args, e4_passed=True)
    client.lakeview.create.assert_not_called()
    client.lakeview.publish.assert_not_called()


@pytest.mark.parametrize("existing", [False, True])
def test_deploy_reuses_requested_dashboard_and_never_embeds_credentials(monkeypatch, existing):
    client, sql = Mock(), Mock()
    sql.warehouse_id = "warehouse"
    client.lakeview.create.return_value = SimpleNamespace(dashboard_id="dashboard")
    client.lakeview.get.return_value = SimpleNamespace(
        display_name="Fashion Platform Overview", etag="revision"
    )
    monkeypatch.setattr(dashboard_deploy, "verify", Mock(return_value={"orders": 3}))
    dashboard_id, result = dashboard_deploy.deploy(
        client,
        sql,
        source_catalog="source",
        catalog="fashion",
        start=date(2026, 10, 1),
        end=date(2026, 10, 2),
        parent_path="/Users/demo",
        dashboard_id="dashboard" if existing else None,
        e4_passed=True,
    )
    assert (dashboard_id, result) == ("dashboard", {"orders": 3})
    client.lakeview.publish.assert_called_once_with(
        "dashboard", embed_credentials=False, warehouse_id="warehouse"
    )
    if existing:
        client.lakeview.create.assert_not_called()
        assert client.lakeview.update.call_args.args[1].etag == "revision"
    else:
        assert client.lakeview.create.call_args.args[0].parent_path == "/Users/demo"
