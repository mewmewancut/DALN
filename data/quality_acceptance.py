"""Run the E4 gate locally with an existing Databricks Job and unified authentication."""

import argparse
from datetime import timedelta

from quality_check import run_gate
from warehouse_sql import WarehouseSQL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-catalog", required=True)
    parser.add_argument("--target-catalog", default="fashion")
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--job-id", required=True, type=int)
    parser.add_argument("--profile")
    args = parser.parse_args()
    from databricks.sdk import WorkspaceClient

    client = WorkspaceClient(profile=args.profile)
    job = client.jobs.get(args.job_id)
    tasks = job.settings.tasks if job.settings else None
    if not tasks or len(tasks) != 1 or not tasks[0].notebook_task:
        parser.error("Use the existing single-task E1/E2/E3 pipeline Job")
    params = tasks[0].notebook_task.base_parameters or {}
    if params.get("target_catalog") != args.target_catalog or params.get("excluded_shop_ids", ""):
        parser.error("E4 requires the matching target catalog and no excluded shops")
    if list(client.jobs.list_runs(job_id=args.job_id, active_only=True)):
        parser.error("Wait for active pipeline runs before E4")

    def pipeline():
        run = client.jobs.run_now(job_id=args.job_id).result(timeout=timedelta(minutes=35))
        state = run.state.result_state if run.state else None
        if getattr(state, "value", state) != "SUCCESS":
            raise RuntimeError("Pipeline Job did not succeed")
        print(f"SUCCESS pipeline run {run.run_id}", flush=True)

    sql = WarehouseSQL(client.statement_execution, args.warehouse_id)
    try:
        result = run_gate(sql, pipeline, args.source_catalog, args.target_catalog)
    except Exception as error:
        parser.exit(1, f"E4 failed ({type(error).__name__}); inspect diagnostics\n")
    print(f"Revenue: {result['revenue']} VND; orders: {result['orders']}")


if __name__ == "__main__":
    main()
