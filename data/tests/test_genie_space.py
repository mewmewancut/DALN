import json
import re
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from genie_provision import provision
from genie_space import build_space, view_name
from gold_queries import GOLD_TABLES


def columns():
    return dict.fromkeys(GOLD_TABLES, ["shop_id", "revenue"])


@pytest.mark.parametrize("shop_id", [None, 7])
def test_space_has_only_six_gold_sources_descriptions_vn_metrics_and_sorted_valid_ids(shop_id):
    payload = json.loads(build_space("fashion", columns(), shop_id))
    tables = payload["data_sources"]["tables"]
    assert len(tables) == 6
    assert [t["identifier"] for t in tables] == sorted(t["identifier"] for t in tables)
    assert {t["identifier"] for t in tables} == {
        f"fashion.gold.{view_name(t, shop_id)}" for t in GOLD_TABLES
    }
    assert all(t["description"] and len(t["column_configs"]) == 2 for t in tables)
    for items in [
        payload["config"]["sample_questions"],
        payload["instructions"]["example_question_sqls"],
    ]:
        ids = [i["id"] for i in items]
        assert ids == sorted(ids)
        assert all(re.fullmatch("[a-f0-9]{32}", value) for value in ids)
    instruction = " ".join(payload["instructions"]["text_instructions"][0]["content"])
    assert "SHIPPING" in instruction and "does not" in instruction
    assert "Asia/Ho_Chi_Minh" in instruction
    if shop_id is not None:
        assert f"shop_id={shop_id}" in instruction
        assert "MUST refuse requests for another shop or platform-wide totals" in instruction
        assert "never to the platform" in instruction
    else:
        assert "admin scope covering all shops" in instruction
    assert len(payload["config"]["sample_questions"]) == 6
    assert len(payload["instructions"]["example_question_sqls"]) >= 20
    assert build_space("fashion", columns(), shop_id) == build_space("fashion", columns(), shop_id)


@pytest.mark.parametrize("shop_id", [0, -1, "1 OR TRUE", True])
def test_fixed_shop_view_rejects_unsafe_or_noncanonical_ids(shop_id):
    with pytest.raises(ValueError):
        view_name("revenue_daily", shop_id)


def test_space_rejects_raw_sources_unknown_columns_and_unsafe_catalog():
    with pytest.raises(ValueError):
        view_name("orders")
    with pytest.raises(ValueError):
        build_space("bad.catalog", columns())
    with pytest.raises(ValueError):
        build_space("fashion", {"orders": ["id"]})


@pytest.mark.parametrize("shared", [False, True])
def test_e5_status_columns_enable_shipping_without_raw_sources_or_default_month(shared):
    available = columns()
    available["orders_summary_daily"] = [
        "shop_id",
        "date",
        "total_orders",
        "delivered",
        "cancelled",
        "pending",
        "confirmed",
        "preparing",
        "shipping",
    ]
    payload = json.loads(build_space("fashion", available, shared=shared))
    instruction = " ".join(payload["instructions"]["text_instructions"][0]["content"])
    assert "SUM(shipping) across ALL dates" in instruction
    assert "not default to this month" in instruction
    assert "does not contain a SHIPPING" not in instruction
    example = next(
        e
        for e in payload["instructions"]["example_question_sqls"]
        if e["question"] == ["Có bao nhiêu đơn hàng đang giao?"]
    )
    assert "SUM(shipping)" in " ".join(example["sql"])
    assert "WHERE date" not in " ".join(example["sql"])
    assert ("chatbot_orders_summary_daily" if shared else "orders_summary_daily") in " ".join(
        example["sql"]
    )


def test_provision_refuses_pre_gate_or_unignored_secret_output_without_mutation(tmp_path):
    client, sql = Mock(), Mock()
    with pytest.raises(ValueError, match="E4"):
        provision(client, sql, "fashion", tmp_path / ".env.genie.json")
    with pytest.raises(ValueError, match="ignored"):
        provision(client, sql, "fashion", tmp_path / "secrets.json", e4_passed=True)
    sql.execute.assert_not_called()
    client.service_principals.create.assert_not_called()


def test_provision_gives_shop_only_fixed_views_and_reuses_credentials_and_spaces(tmp_path):
    client, sql = Mock(), Mock()
    client.config.host = "https://test.cloud.databricks.com"
    sql.warehouse_id = "warehouse"
    sql.execute.side_effect = lambda query: (
        [["shop_id"], ["revenue"]]
        if query.startswith("SHOW")
        else [[7], [8]]
        if query.startswith("SELECT shop_id")
        else []
    )
    client.service_principals.list.return_value = []
    client.service_principals.create.side_effect = [
        SimpleNamespace(application_id=f"00000000-0000-0000-0000-{scope:012d}", id=str(scope))
        for scope in (0, 7, 8)
    ]
    client.service_principal_secrets_proxy.create.return_value = SimpleNamespace(
        secret="fake-oauth-secret"
    )
    client.genie.create_space.side_effect = [
        SimpleNamespace(space_id=str(i) * 32) for i in (1, 2, 3)
    ]
    output = tmp_path / ".env.genie.json"
    result = provision(client, sql, "fashion", output, e4_passed=True, report=Mock(), verify=Mock())
    assert set(result["shops"]) == {"7", "8"}
    statements = [c.args[0] for c in sql.execute.call_args_list]
    for shop in (7, 8):
        grants = [q for q in statements if q.startswith("GRANT SELECT") and f"{shop:012d}" in q]
        assert len(grants) == 6 and all("chatbot_" in q for q in grants)
    views = [q for q in statements if q.startswith("CREATE OR REPLACE VIEW")]
    assert len(views) == 6
    assert all("session_user()" in q and "m.shop_id = g.shop_id" in q for q in views)
    assert result["shops"]["7"]["space_id"] == result["shops"]["8"]["space_id"]
    assert result["admin"]["space_id"] != result["shared_shop_space_id"]
    assert json.loads(output.read_text()) == result
    provision(client, sql, "fashion", output, e4_passed=True, report=Mock(), verify=Mock())
    assert client.service_principals.create.call_count == 3
    assert client.service_principal_secrets_proxy.create.call_count == 3
    assert client.genie.create_space.call_count == 2
    assert client.genie.update_space.call_count == 0
