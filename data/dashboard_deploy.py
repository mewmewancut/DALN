"""Create/update and publish a private E5 dashboard after E4 and SQL acceptance."""

import argparse
import json
from datetime import date

from dashboard_acceptance import verify
from dashboard_definition import build_dashboard
from warehouse_sql import WarehouseSQL


def deploy(
    client,
    sql,
    *,
    source_catalog,
    catalog="fashion",
    start,
    end,
    parent_path,
    dashboard_id=None,
    e4_passed=False,
):
    if not e4_passed:
        raise ValueError("Run E4 successfully before deploying Dashboard E5")
    result = verify(sql, source_catalog, catalog, start, end)
    from databricks.sdk.service.dashboards import Dashboard

    definition = json.dumps(build_dashboard(catalog), ensure_ascii=False)
    dashboard = Dashboard(
        display_name="Fashion Platform Overview",
        serialized_dashboard=definition,
        warehouse_id=sql.warehouse_id,
    )
    if dashboard_id:
        current = client.lakeview.get(dashboard_id)
        if current.display_name != dashboard.display_name:
            raise ValueError("Refuse to overwrite a different dashboard")
        dashboard.etag = current.etag
        client.lakeview.update(dashboard_id, dashboard)
    else:
        dashboard.parent_path = parent_path
        dashboard_id = client.lakeview.create(dashboard).dashboard_id
    # Viewers keep their own UC permissions; do not distribute author credentials.
    client.lakeview.publish(dashboard_id, embed_credentials=False, warehouse_id=sql.warehouse_id)
    return dashboard_id, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile")
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--source-catalog", required=True)
    parser.add_argument("--catalog", default="fashion")
    parser.add_argument("--from-date", type=date.fromisoformat, required=True)
    parser.add_argument("--to-date", type=date.fromisoformat, required=True)
    parser.add_argument("--parent-path", required=True)
    parser.add_argument("--dashboard-id")
    parser.add_argument("--e4-passed", action="store_true")
    args = parser.parse_args()
    from databricks.sdk import WorkspaceClient

    client = WorkspaceClient(profile=args.profile)
    sql = WarehouseSQL(client.statement_execution, args.warehouse_id)
    try:
        dashboard_id, result = deploy(
            client,
            sql,
            source_catalog=args.source_catalog,
            catalog=args.catalog,
            start=args.from_date,
            end=args.to_date,
            parent_path=args.parent_path,
            dashboard_id=args.dashboard_id,
            e4_passed=args.e4_passed,
        )
    except Exception as error:
        parser.exit(
            1, f"Dashboard deployment failed ({type(error).__name__}); inspect diagnostics\n"
        )
    print(f"PASS E5 SQL: revenue={result['revenue']} VND; orders={result['orders']}")
    print(f"Dashboard: {client.config.host.rstrip('/')}/sql/dashboardsv3/{dashboard_id}")


if __name__ == "__main__":
    main()
