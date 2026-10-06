import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from genie_lock import provision_lock
from genie_provision import provision
from genie_security import setup_views, sync_mapping
from genie_space import build_space
from genie_worker import run_worker
from gold_queries import GOLD_TABLES


def test_shared_views_scope_by_session_identity_and_mapping_is_not_a_genie_source():
    sql = Mock()
    setup_views(sql, "fashion")
    views = [
        c.args[0]
        for c in sql.execute.call_args_list
        if c.args[0].startswith("CREATE OR REPLACE VIEW")
    ]
    assert len(views) == 6
    assert all(
        "session_user()" in v and "m.shop_id = g.shop_id" in v and "m.enabled = TRUE" in v
        for v in views
    )
    payload = json.loads(
        build_space("fashion", dict.fromkeys(GOLD_TABLES, ["shop_id"]), shared=True)
    )
    assert all(
        t["identifier"].startswith("fashion.gold.chatbot_")
        for t in payload["data_sources"]["tables"]
    )
    assert all(
        not c["enable_format_assistance"] and not c["enable_entity_matching"]
        for t in payload["data_sources"]["tables"]
        for c in t["column_configs"]
    )


def test_mapping_disables_missing_shops_and_rejects_shared_or_forged_principal():
    sql = Mock()
    sync_mapping(sql, "fashion", {"1": {"client_id": "00000000-0000-0000-0000-000000000001"}})
    assert (
        "WHEN NOT MATCHED BY SOURCE THEN UPDATE SET t.enabled = FALSE"
        in sql.execute.call_args.args[0]
    )
    with pytest.raises(ValueError):
        sync_mapping(sql, "fashion", {"1": {"client_id": "injected' OR TRUE"}})
    with pytest.raises(ValueError):
        sync_mapping(
            sql,
            "fashion",
            dict.fromkeys(["1", "2"], {"client_id": "00000000-0000-0000-0000-000000000001"}),
        )


def test_worker_reconciles_shop_changes_retries_and_skips_unchanged(
    tmp_path,
):
    client, sql, reconcile = Mock(), Mock(), Mock()
    sql.execute.side_effect = [[[1]], [[1]], [[1], [2]], [[1], [2]], [[2]]]
    reconcile.side_effect = [None, RuntimeError("FAKE-SECRET"), None, None]
    output = tmp_path / ".env.genie.json"
    output.write_text("{}")
    sleeps = []
    report = Mock()
    run_worker(
        client,
        sql,
        output,
        interval=5,
        stop=lambda: len(sleeps) == 5,
        sleep=sleeps.append,
        report=report,
        reconcile=reconcile,
    )
    assert [c.kwargs["shop_ids"] for c in reconcile.call_args_list] == [(1,), (1, 2), (1, 2), (2,)]
    assert sleeps == [5, 5, 10, 5, 5]
    assert "FAKE-SECRET" not in str(report.call_args_list)
    assert "u.is_active = TRUE" in sql.execute.call_args.args[0]


def test_provision_acceptance_failure_keeps_last_valid_runtime_and_retry_reuses_space(tmp_path):
    client, sql = Mock(), Mock()
    client.config.host = "https://fake.cloud.databricks.com"
    sql.warehouse_id = "warehouse"
    sql.execute.side_effect = lambda query: [["shop_id"]] if query.startswith("SHOW") else []
    client.service_principals.list.return_value = []
    client.service_principals.create.return_value = SimpleNamespace(
        application_id="00000000-0000-0000-0000-000000000001", id="1"
    )
    client.service_principal_secrets_proxy.create.return_value = SimpleNamespace(
        secret="FAKE-SECRET"
    )
    client.genie.create_space.side_effect = [
        SimpleNamespace(space_id="a" * 32),
        SimpleNamespace(space_id="b" * 32),
    ]
    output = tmp_path / ".env.genie.json"
    output.write_text('{"old":"valid"}')
    with pytest.raises(RuntimeError):
        provision(
            client,
            sql,
            "fashion",
            output,
            e4_passed=True,
            shop_ids=[],
            verify=Mock(side_effect=RuntimeError("denied")),
            report=Mock(),
        )
    assert json.loads(output.read_text()) == {"old": "valid"}
    provision(
        client, sql, "fashion", output, e4_passed=True, shop_ids=[], verify=Mock(), report=Mock()
    )
    assert client.genie.create_space.call_count == 2


def test_worker_checks_native_source_without_waking_warehouse_when_unchanged(tmp_path):
    sql, reader, reconcile = Mock(), Mock(return_value=(1,)), Mock()
    output = tmp_path / ".env.genie.json"
    output.write_text("{}")
    slept = []
    run_worker(
        Mock(),
        sql,
        output,
        read_shops=reader,
        reconcile=reconcile,
        stop=lambda: len(slept) == 2,
        sleep=slept.append,
    )
    assert reader.call_count == 2 and reconcile.call_count == 1
    sql.execute.assert_not_called()


def test_provision_lock_rejects_concurrent_writer_and_releases_on_failure(tmp_path):
    output = tmp_path / ".env.genie.json"
    with pytest.raises(RuntimeError):
        with provision_lock(output):
            with pytest.raises(OSError):
                with provision_lock(output):
                    pass
            raise RuntimeError("FAKE-FAILURE")
    with provision_lock(output):
        pass
