"""Small SQL Statement Execution adapter using Databricks unified authentication."""

import time

from bronze_ingest import IngestionError


class WarehouseSQL:
    def __init__(self, api, warehouse_id, timeout=600, *, clock=time.monotonic, sleep=time.sleep):
        if timeout <= 0:
            raise ValueError("Statement timeout must be positive")
        self.api = api
        self.warehouse_id = warehouse_id
        self.timeout = timeout
        self.clock = clock
        self.sleep = sleep

    def execute(self, statement):
        deadline = self.clock() + self.timeout
        response = self.api.execute_statement(
            warehouse_id=self.warehouse_id,
            statement=statement,
            # Return short statements directly instead of paying a polling sleep for each SQL.
            wait_timeout=f"{min(10, int(self.timeout))}s" if self.timeout >= 5 else "0s",
        )
        statement_id = response.statement_id
        state = None
        try:
            while True:
                state = getattr(getattr(response, "status", None), "state", None)
                state = getattr(state, "value", state)
                if state == "SUCCEEDED":
                    if response.manifest and response.manifest.truncated:
                        raise IngestionError("SQL result was truncated")
                    if response.result is None:
                        return []
                    return response.result.data_array or []
                if state in {"FAILED", "CANCELED", "CLOSED"}:
                    # Do not log SQL error payloads, which can contain operational data.
                    raise IngestionError(f"SQL statement {statement_id} ended with {state}")
                if state not in {"PENDING", "RUNNING"} or not statement_id:
                    raise IngestionError("SQL returned an invalid statement status")
                remaining = deadline - self.clock()
                if remaining <= 0:
                    raise IngestionError(f"SQL statement {statement_id} exceeded timeout")
                self.sleep(min(2, remaining))
                response = self.api.get_statement(statement_id)
        except Exception:
            # Cancellation is best effort; preserve the original failure for the caller.
            if statement_id and state in {"PENDING", "RUNNING"}:
                try:
                    self.api.cancel_execution(statement_id)
                except Exception:
                    pass
            raise
