"""Provision private Genie identities and fixed shop Gold views after the E4 gate."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from bronze_ingest import identifier
from genie_space import build_space, view_name
from gold_queries import GOLD_TABLES
from warehouse_sql import WarehouseSQL


def provision(client, sql, catalog, output, *, e4_passed=False, report=print):
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
    shops = [
        int(row[0])
        for row in sql.execute(f"SELECT shop_id FROM {namespace}.shop_performance ORDER BY shop_id")
    ]
    state_path = output.with_name(output.name + ".provision")
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    host = client.config.host.rstrip("/")
    if state and state.get("host") != host:
        raise ValueError("Provision state belongs to a different workspace")
    state.setdefault("host", host)
    state.setdefault("identities", {})

    def save():
        temporary = state_path.with_name(state_path.name + ".tmp")
        temporary.write_text(json.dumps(state), encoding="utf-8")
        temporary.replace(state_path)

    for shop_id in [None, *shops]:
        scope = "admin" if shop_id is None else str(shop_id)
        name = f"daln-genie-{'admin' if shop_id is None else f'shop-{shop_id}'}"
        entry = state["identities"].get(scope)
        if entry is None:
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
        principal_sql = f"`{UUID(entry['client_id'])}`"
        sql.execute(f"GRANT USE CATALOG ON CATALOG {identifier(catalog)} TO {principal_sql}")
        sql.execute(f"GRANT USE SCHEMA ON SCHEMA {namespace} TO {principal_sql}")
        for table in GOLD_TABLES:
            target = f"{namespace}.{identifier(view_name(table, shop_id))}"
            if shop_id is not None:
                sql.execute(
                    f"CREATE OR REPLACE VIEW {target} AS SELECT * "
                    f"FROM {namespace}.{identifier(table)} WHERE shop_id = {shop_id}"
                )
            sql.execute(f"GRANT SELECT ON TABLE {target} TO {principal_sql}")
        if "space_id" not in entry:
            space = client.genie.create_space(
                sql.warehouse_id,
                build_space(catalog, columns, shop_id),
                title="Fashion Platform Assistant"
                + ("" if shop_id is None else f" — Shop {shop_id}"),
                description="Business analytics from Gold; Vietnam dates and VND.",
            )
            entry["space_id"] = space.space_id
            save()
        else:
            client.genie.update_space(
                entry["space_id"], serialized_space=build_space(catalog, columns, shop_id)
            )
        client.permissions.update(
            "genie",
            entry["space_id"],
            access_control_list=[
                AccessControlRequest(
                    service_principal_name=entry["client_id"],
                    permission_level=PermissionLevel.CAN_RUN,
                )
            ],
        )
        client.permissions.update(
            "sql/warehouses",
            sql.warehouse_id,
            access_control_list=[
                AccessControlRequest(
                    service_principal_name=entry["client_id"],
                    permission_level=PermissionLevel.CAN_USE,
                )
            ],
        )
        report(f"Configured private Genie scope {scope}", flush=True)
    config = {
        "host": host,
        "e4_passed": True,
        "admin": {
            k: state["identities"]["admin"][k] for k in ("space_id", "client_id", "client_secret")
        },
        "shops": {
            str(s): {
                k: state["identities"][str(s)][k]
                for k in ("space_id", "client_id", "client_secret")
            }
            for s in shops
        },
    }
    # Write the runtime config only after every scope has been provisioned.
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(json.dumps(config), encoding="utf-8")
    temporary.replace(output)
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile")
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--catalog", default="fashion")
    parser.add_argument("--output", default="backend/.env.genie.json")
    parser.add_argument(
        "--e4-passed",
        action="store_true",
        help="Attest that the full E4 gate has passed in this workspace",
    )
    args = parser.parse_args()
    from databricks.sdk import WorkspaceClient

    client = WorkspaceClient(profile=args.profile)
    sql = WarehouseSQL(client.statement_execution, args.warehouse_id)
    try:
        provision(client, sql, args.catalog, args.output, e4_passed=args.e4_passed)
    except Exception as error:
        parser.exit(
            1, f"Genie setup failed ({type(error).__name__}); runtime config was not enabled\n"
        )
    print("Private Genie scopes provisioned; verify data isolation before enabling the web chatbot")


if __name__ == "__main__":
    main()
