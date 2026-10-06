from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from genie_acceptance import denied


@pytest.mark.parametrize(
    "state,message",
    [("SUCCEEDED", ""), ("FAILED", "TABLE_OR_VIEW_NOT_FOUND"), ("FAILED", "warehouse unavailable")],
)
def test_isolation_check_does_not_treat_success_missing_table_or_infrastructure_error_as_denial(
    state, message
):
    api = Mock()
    api.execute_statement.return_value = SimpleNamespace(
        status=SimpleNamespace(
            state=SimpleNamespace(value=state), error=SimpleNamespace(message=message)
        )
    )
    with pytest.raises(ValueError, match="permission denial"):
        denied(api, "warehouse", "SELECT 1")


def test_isolation_check_accepts_only_explicit_unity_catalog_permission_failure():
    api = Mock()
    api.execute_statement.return_value = SimpleNamespace(
        status=SimpleNamespace(
            state=SimpleNamespace(value="FAILED"),
            error=SimpleNamespace(message="[INSUFFICIENT_PERMISSIONS]"),
        )
    )
    denied(api, "warehouse", "SELECT 1")
