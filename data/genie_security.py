"""Shared Gold views whose row scope is enforced by the caller's UC identity."""

from uuid import UUID

from bronze_ingest import identifier
from gold_queries import GOLD_TABLES


def shared_view(table):
    if table not in GOLD_TABLES:
        raise ValueError("Only E3 Gold sources are allowed")
    return f"chatbot_{table}"


def setup_views(sql, catalog):
    catalog = identifier(catalog)
    mapping = f"{catalog}.`genie_security`.`shop_identities`"
    sql.execute(f"CREATE SCHEMA IF NOT EXISTS {catalog}.`genie_security`")
    sql.execute(
        f"CREATE TABLE IF NOT EXISTS {mapping} "
        "(principal STRING NOT NULL, shop_id BIGINT NOT NULL, enabled BOOLEAN NOT NULL) "
        "USING DELTA"
    )
    for table in GOLD_TABLES:
        sql.execute(
            f"CREATE OR REPLACE VIEW {catalog}.`gold`.{identifier(shared_view(table))} AS "
            f"SELECT g.* FROM {catalog}.`gold`.{identifier(table)} g WHERE EXISTS "
            f"(SELECT 1 FROM {mapping} m WHERE m.principal = session_user() "
            "AND m.shop_id = g.shop_id AND m.enabled = TRUE)"
        )


def sync_mapping(sql, catalog, identities):
    rows = []
    seen = set()
    for shop_id, entry in identities.items():
        if not str(shop_id).isdigit() or int(shop_id) <= 0:
            raise ValueError("Shop IDs must be positive integers")
        principal = str(UUID(entry["client_id"]))
        if principal in seen:
            raise ValueError("A principal may belong to only one shop")
        seen.add(principal)
        rows.append(
            f"SELECT '{principal}' AS principal, {int(shop_id)} AS shop_id, TRUE AS enabled"
        )
    source = " UNION ALL ".join(rows) or (
        "SELECT CAST(NULL AS STRING) AS principal, CAST(NULL AS BIGINT) AS shop_id, "
        "FALSE AS enabled WHERE FALSE"
    )
    sql.execute(
        f"MERGE INTO {identifier(catalog)}.`genie_security`.`shop_identities` t "
        f"USING ({source}) s ON t.principal = s.principal "
        "WHEN MATCHED THEN UPDATE SET t.shop_id = s.shop_id, t.enabled = TRUE "
        "WHEN NOT MATCHED THEN INSERT * "
        "WHEN NOT MATCHED BY SOURCE THEN UPDATE SET t.enabled = FALSE"
    )
