"""Bootstrap management OAuth only for the isolated provisioning container."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from genie_provision import atomic_json
from warehouse_sql import WarehouseSQL


def setup(client, sql, output, *, e4_passed=False):
    from databricks.sdk.service.iam import Patch, PatchOp, PatchSchema

    if not e4_passed or not Path(output).name.startswith(".env."):
        raise ValueError("E4 and ignored secret output are required")
    output = Path(output)
    if output.exists():
        config = json.loads(output.read_text(encoding="utf-8"))
        if config["host"] != client.config.host.rstrip("/"):
            raise ValueError("Worker belongs to another workspace")
    else:
        matches = list(
            client.service_principals.list(filter='displayName eq "daln-genie-provisioner"')
        )
        principal = (
            matches[0]
            if matches
            else client.service_principals.create(
                display_name="daln-genie-provisioner",
                active=True,
            )
        )
        config = {
            "host": client.config.host.rstrip("/"),
            "client_id": principal.application_id,
            "principal_id": principal.id,
            "warehouse_id": sql.warehouse_id,
            "e4_passed": True,
        }
        atomic_json(output, config)
    admins = list(client.groups.list(filter='displayName eq "admins"'))
    if len(admins) != 1:
        raise ValueError("Workspace admins group is required for identity provisioning")
    client.groups.patch(
        admins[0].id,
        schemas=[PatchSchema("urn:ietf:params:scim:api:messages:2.0:PatchOp")],
        operations=[
            Patch(op=PatchOp.ADD, path="members", value=[{"value": config["principal_id"]}])
        ],
    )
    if "client_secret" not in config:
        secret = client.service_principal_secrets_proxy.create(
            config["principal_id"], lifetime="31536000s"
        )
        config["client_secret"] = secret.secret
        atomic_json(output, config)
    identity = f"`{UUID(config['client_id'])}`"
    for statement in [
        f"GRANT USE CATALOG ON CATALOG fashion TO {identity}",
        f"GRANT MANAGE ON CATALOG fashion TO {identity}",
        f"GRANT CREATE SCHEMA ON CATALOG fashion TO {identity}",
        f"GRANT USE SCHEMA ON SCHEMA fashion.gold TO {identity}",
        f"GRANT SELECT ON SCHEMA fashion.gold TO {identity}",
        f"GRANT CREATE TABLE ON SCHEMA fashion.gold TO {identity}",
        f"GRANT USE CATALOG ON CATALOG daln_source TO {identity}",
        f"GRANT USE SCHEMA ON SCHEMA daln_source.public TO {identity}",
        f"GRANT SELECT ON TABLE daln_source.public.shops TO {identity}",
        f"GRANT SELECT ON TABLE daln_source.public.users TO {identity}",
    ]:
        sql.execute(statement)
    from databricks.sdk.service.iam import AccessControlRequest, PermissionLevel

    client.permissions.update(
        "sql/warehouses",
        sql.warehouse_id,
        access_control_list=[
            AccessControlRequest(
                service_principal_name=config["client_id"],
                permission_level=PermissionLevel.CAN_MANAGE,
            )
        ],
    )
    runtime = Path("backend/.env.genie.json")
    if runtime.exists():
        current = json.loads(runtime.read_text(encoding="utf-8"))
        for space_id in {current["admin"]["space_id"], current.get("shared_shop_space_id")} - {
            None
        }:
            client.permissions.update(
                "genie",
                space_id,
                access_control_list=[
                    AccessControlRequest(
                        service_principal_name=config["client_id"],
                        permission_level=PermissionLevel.CAN_MANAGE,
                    )
                ],
            )
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="daln-cdc")
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--output", default=".env.genie-worker.json")
    parser.add_argument("--e4-passed", action="store_true")
    args = parser.parse_args()
    from databricks.sdk import WorkspaceClient

    try:
        client = WorkspaceClient(profile=args.profile)
        setup(
            client,
            WarehouseSQL(client.statement_execution, args.warehouse_id),
            args.output,
            e4_passed=args.e4_passed,
        )
    except Exception as error:
        parser.exit(1, f"Worker setup failed ({type(error).__name__})\n")
    print("Isolated Genie worker credentials configured")


if __name__ == "__main__":
    main()
