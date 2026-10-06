"""Reconcile private identities onto one shared shop Genie space after E4."""

import argparse
import hashlib
import json
from pathlib import Path
from uuid import UUID

from bronze_ingest import identifier
from genie_lock import provision_lock
from genie_security import setup_views, shared_view, sync_mapping
from genie_space import build_space
from gold_queries import GOLD_TABLES
from warehouse_sql import WarehouseSQL


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def provision(
    client, sql, catalog, output, *, e4_passed=False, report=print, shop_ids=None, verify=None
):
    if not Path(output).name.startswith(".env.") or not e4_passed:
        raise ValueError("E4 gate and ignored secret output are required")
    with provision_lock(output):
        return _provision(
            client,
            sql,
            catalog,
            output,
            e4_passed=e4_passed,
            report=report,
            shop_ids=shop_ids,
            verify=verify,
        )


def _provision(client, sql, catalog, output, *, e4_passed, report, shop_ids, verify):
    from databricks.sdk.service.iam import AccessControlRequest, PermissionLevel

    if not e4_passed:
        raise ValueError("Run E4 successfully before provisioning Genie")
    output = Path(output)
    if not output.name.startswith(".env."):
        raise ValueError("Use an ignored .env.* filename for OAuth secrets")
    namespace = f"{identifier(catalog)}.`gold`"
    columns = {
        t: [r[0] for r in sql.execute(f"SHOW COLUMNS IN {namespace}.{identifier(t)}")]
        for t in GOLD_TABLES
    }
    shops = sorted(
        set(
            shop_ids
            if shop_ids is not None
            else (
                int(r[0]) for r in sql.execute(f"SELECT shop_id FROM {namespace}.shop_performance")
            )
        )
    )
    if any(type(s) is not int or s <= 0 for s in shops):
        raise ValueError("Shop IDs must be positive integers")
    state_path = output.with_name(output.name + ".provision")
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    host = client.config.host.rstrip("/")
    if state and state.get("host") != host:
        raise ValueError("Provision state belongs to a different workspace")
    state.setdefault("host", host)
    state.setdefault("identities", {})

    def save():
        atomic_json(state_path, state)

    def identity(scope):
        entry = state["identities"].get(scope)
        if entry is None:
            name = f"daln-genie-{'admin' if scope == 'admin' else f'shop-{scope}'}"
            matches = list(client.service_principals.list(filter=f'displayName eq "{name}"'))
            principal = (
                matches[0]
                if matches
                else client.service_principals.create(display_name=name, active=True)
            )
            entry = {"client_id": principal.application_id, "principal_id": principal.id}
            state["identities"][scope] = entry
            save()
        if "client_secret" not in entry:
            secret = client.service_principal_secrets_proxy.create(
                entry["principal_id"], lifetime="31536000s"
            )
            entry["client_secret"] = secret.secret
            save()
        return entry

    admin = identity("admin")
    entries = {str(s): identity(str(s)) for s in shops}
    admin_payload = build_space(catalog, columns)
    shop_payload = build_space(catalog, columns, shared=True)
    digest = hashlib.sha256((admin_payload + shop_payload).encode()).hexdigest()
    if state.get("shared_version") != digest:
        setup_views(sql, catalog)
        if "space_id" not in admin:
            admin["space_id"] = client.genie.create_space(
                sql.warehouse_id, admin_payload, title="Fashion Platform Assistant"
            ).space_id
            save()
        else:
            client.genie.update_space(admin["space_id"], serialized_space=admin_payload)
        if "shared_space_id" not in state:
            state["shared_space_id"] = client.genie.create_space(
                sql.warehouse_id, shop_payload, title="Fashion Platform Assistant — Shops"
            ).space_id
            save()
        else:
            client.genie.update_space(state["shared_space_id"], serialized_space=shop_payload)
    shared_id = state["shared_space_id"]
    if shared_id == admin["space_id"]:
        raise ValueError("Admin space must remain separate")
    sync_mapping(sql, catalog, entries)
    for scope, entry in [("admin", admin), *entries.items()]:
        principal = f"`{UUID(entry['client_id'])}`"
        sql.execute(f"GRANT USE CATALOG ON CATALOG {identifier(catalog)} TO {principal}")
        sql.execute(f"GRANT USE SCHEMA ON SCHEMA {namespace} TO {principal}")
        for table in GOLD_TABLES:
            target = table if scope == "admin" else shared_view(table)
            sql.execute(f"GRANT SELECT ON TABLE {namespace}.{identifier(target)} TO {principal}")
        space_id = admin["space_id"] if scope == "admin" else shared_id
        for object_type, object_id, permission in [
            ("genie", space_id, PermissionLevel.CAN_RUN),
            ("sql/warehouses", sql.warehouse_id, PermissionLevel.CAN_USE),
        ]:
            client.permissions.update(
                object_type,
                object_id,
                access_control_list=[
                    AccessControlRequest(
                        service_principal_name=entry["client_id"], permission_level=permission
                    )
                ],
            )
    config = {
        "host": host,
        "e4_passed": True,
        "shared_shop_space_id": shared_id,
        "admin": {k: admin[k] for k in ("space_id", "client_id", "client_secret")},
        "shops": {
            s: {
                "space_id": shared_id,
                "client_id": e["client_id"],
                "client_secret": e["client_secret"],
            }
            for s, e in entries.items()
        },
    }
    if verify is None:
        from genie_acceptance import verify as verify_access

        def verify(cfg):
            return verify_access(cfg, sql.warehouse_id, report=report)

    verify(config)
    state["shared_version"] = digest
    save()
    atomic_json(output, config)
    report(f"Configured shared Genie with {len(entries)} private shop identities", flush=True)
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile")
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--catalog", default="fashion")
    parser.add_argument("--output", default="backend/.env.genie.json")
    parser.add_argument("--e4-passed", action="store_true")
    args = parser.parse_args()
    from databricks.sdk import WorkspaceClient

    client = WorkspaceClient(profile=args.profile)
    sql = WarehouseSQL(client.statement_execution, args.warehouse_id)
    try:
        provision(client, sql, args.catalog, args.output, e4_passed=args.e4_passed)
    except Exception as error:
        parser.exit(1, f"Genie setup failed ({type(error).__name__}); runtime config not updated\n")


if __name__ == "__main__":
    main()
