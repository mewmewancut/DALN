import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from genie_worker_setup import setup


def fixtures():
    client, sql = Mock(), Mock()
    client.config.host = "https://fake.cloud.databricks.com"
    sql.warehouse_id = "warehouse"
    client.service_principals.list.return_value = []
    client.service_principals.create.return_value = SimpleNamespace(
        application_id="00000000-0000-0000-0000-000000000001", id="42"
    )
    client.groups.list.return_value = [SimpleNamespace(id="admins-id")]
    client.service_principal_secrets_proxy.create.return_value = SimpleNamespace(
        secret="FAKE-WORKER-SECRET"
    )
    return client, sql


def test_bootstrap_grants_workspace_admin_only_to_isolated_worker_and_reuses_secret(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    client, sql = fixtures()
    runtime = tmp_path / "backend" / ".env.genie.json"
    runtime.parent.mkdir()
    original = {"admin": {"space_id": "a" * 32}, "shared_shop_space_id": "b" * 32}
    runtime.write_text(json.dumps(original))
    output = tmp_path / ".env.genie-worker.json"
    config = setup(client, sql, output, e4_passed=True)
    setup(client, sql, output, e4_passed=True)
    assert config["client_secret"] == "FAKE-WORKER-SECRET"
    assert json.loads(runtime.read_text()) == original
    assert client.service_principals.create.call_count == 1
    assert client.service_principal_secrets_proxy.create.call_count == 1
    membership = client.groups.patch.call_args
    assert membership.args == ("admins-id",)
    assert membership.kwargs["operations"][0].as_dict() == {
        "op": "add",
        "path": "members",
        "value": [{"value": "42"}],
    }
    grants = client.permissions.update.call_args_list
    assert {c.args[1] for c in grants} == {"warehouse", "a" * 32, "b" * 32}
    assert all(
        c.kwargs["access_control_list"][0].service_principal_name == config["client_id"]
        for c in grants
    )


@pytest.mark.parametrize("e4,filename", [(False, ".env.worker.json"), (True, "worker.json")])
def test_bootstrap_requires_e4_and_ignored_secret_file_before_remote_mutation(
    tmp_path, e4, filename
):
    client, sql = fixtures()
    with pytest.raises(ValueError):
        setup(client, sql, tmp_path / filename, e4_passed=e4)
    assert not client.mock_calls
    sql.execute.assert_not_called()


def test_bootstrap_rejects_saved_credentials_from_another_workspace(tmp_path):
    client, sql = fixtures()
    output = tmp_path / ".env.worker.json"
    output.write_text('{"host":"https://other.cloud.databricks.com"}')
    with pytest.raises(ValueError):
        setup(client, sql, output, e4_passed=True)
    client.groups.patch.assert_not_called()
    client.service_principal_secrets_proxy.create.assert_not_called()
    sql.execute.assert_not_called()
