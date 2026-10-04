from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.exc import ProgrammingError

from app.tests.conftest import test_engine


def test_runtime_grants_allow_existing_and_future_auto_increment_inserts():
    suffix = uuid4().hex
    owner = f"sequence_owner_{suffix}"
    runtime = f"sequence_runtime_{suffix}"
    schema = f"sequence_test_{suffix}"
    repair = Path(__file__).resolve().parents[2] / "docker" / "grant-runtime-sequences.sql"
    statements = (
        repair.read_text()
        .replace("fashion_e1", owner)
        .replace("daln_app", runtime)
        .replace("public", schema)
    )

    with test_engine.connect() as connection, connection.begin():
        connection.exec_driver_sql(f"CREATE ROLE {owner}")
        connection.exec_driver_sql(f"CREATE ROLE {runtime}")
        connection.exec_driver_sql(f"CREATE SCHEMA {schema} AUTHORIZATION {owner}")
        connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA {schema} TO {runtime}")
        connection.exec_driver_sql(f"SET LOCAL ROLE {owner}")
        connection.exec_driver_sql(f"CREATE TABLE {schema}.users (id BIGSERIAL PRIMARY KEY)")
        connection.exec_driver_sql(f"GRANT SELECT, INSERT ON {schema}.users TO {runtime}")
        connection.exec_driver_sql("RESET ROLE")
        connection.exec_driver_sql(f"SET LOCAL ROLE {runtime}")

        with connection.begin_nested() as savepoint:
            with pytest.raises(ProgrammingError) as failure:
                connection.exec_driver_sql(f"INSERT INTO {schema}.users DEFAULT VALUES")
            assert failure.value.orig.sqlstate == "42501"
            savepoint.rollback()

        connection.exec_driver_sql("RESET ROLE")
        connection.exec_driver_sql(f"SET LOCAL ROLE {owner}")
        connection.exec_driver_sql(statements)
        connection.exec_driver_sql(statements)  # Safe to apply more than once.
        connection.exec_driver_sql(f"CREATE TABLE {schema}.auth_tokens (id BIGSERIAL PRIMARY KEY)")
        connection.exec_driver_sql(f"GRANT SELECT, INSERT ON {schema}.auth_tokens TO {runtime}")
        connection.exec_driver_sql("RESET ROLE")
        connection.exec_driver_sql(f"SET LOCAL ROLE {runtime}")

        for table in ("users", "auth_tokens"):
            assert (
                connection.exec_driver_sql(
                    f"INSERT INTO {schema}.{table} DEFAULT VALUES RETURNING id"
                ).scalar_one()
                == 1
            )
        assert not connection.exec_driver_sql(
            f"SELECT has_schema_privilege(current_user, '{schema}', 'CREATE')"
        ).scalar_one()
        connection.exec_driver_sql("RESET ROLE")
        connection.rollback()  # Keep test roles and schema out of the local database.
