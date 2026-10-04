"""Read-only E1/E2 acceptance on a warehouse; never called by the scheduled pipeline."""

import argparse

from bronze_ingest import TABLES, IngestionError, identifier
from silver_queries import SILVER_TABLES, build_query
from silver_transform import validate_shop_ids
from warehouse_sql import WarehouseSQL


def verify(sql, source_catalog, target_catalog="fashion", excluded_shop_ids=()):
    source = f"{identifier(source_catalog)}.`public`"
    bronze = f"{identifier(target_catalog)}.`bronze`"
    silver = f"{identifier(target_catalog)}.`silver`"
    excluded = validate_shop_ids(excluded_shop_ids)
    queries = []
    for table in TABLES:
        queries.append(
            f"SELECT '{table}', (SELECT COUNT(*) FROM {source}.{identifier(table)}), "
            f"COUNT(*), COUNT(id), COUNT(DISTINCT id) FROM {bronze}.{identifier(table)}"
        )
    counts = {}
    for name, expected, actual, nonnull, unique in sql.execute(" UNION ALL ".join(queries)):
        if len({int(expected), int(actual), int(nonnull), int(unique)}) != 1:
            raise IngestionError(f"{name}: source/Bronze counts or keys differ")
        counts[name] = int(actual)
    if set(counts) != set(TABLES):
        raise IngestionError("Acceptance did not return all 13 Bronze tables")

    def columns(table):
        return [r[0] for r in sql.execute(f"SHOW COLUMNS IN {bronze}.{identifier(table)}")]

    silver_counts = {}
    for table in SILVER_TABLES:
        query, valid = build_query(table, bronze, silver, columns, excluded)
        projection = f"SELECT * FROM ({query}) projected" + (f" WHERE {valid}" if valid else "")
        target = f"{silver}.{identifier(table)}"
        actual, nonnull, unique = map(
            int, sql.execute(f"SELECT COUNT(*), COUNT(id), COUNT(DISTINCT id) FROM {target}")[0]
        )
        missing = int(
            sql.execute(
                f"SELECT COUNT(*) FROM (({projection}) EXCEPT ALL (SELECT * FROM {target}))"
            )[0][0]
        )
        extra = int(
            sql.execute(
                f"SELECT COUNT(*) FROM ((SELECT * FROM {target}) EXCEPT ALL ({projection}))"
            )[0][0]
        )
        if actual != nonnull or actual != unique or missing or extra:
            raise IngestionError(f"{table}: Silver differs from Planning E2 projection")
        silver_counts[table] = actual
    return {"bronze": counts, "silver": silver_counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-catalog", required=True)
    parser.add_argument("--target-catalog", default="fashion")
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--excluded-shop-ids", default="")
    args = parser.parse_args()
    from databricks.sdk import WorkspaceClient

    sql = WarehouseSQL(WorkspaceClient(profile=args.profile).statement_execution, args.warehouse_id)
    excluded = tuple(int(v) for v in args.excluded_shop_ids.split(",") if v.strip())
    try:
        counts = verify(sql, args.source_catalog, args.target_catalog, excluded)
    except Exception as error:
        parser.exit(1, f"E1/E2 acceptance failed ({type(error).__name__}); inspect diagnostics\n")
    for layer, tables in counts.items():
        for table, count in tables.items():
            print(f"PASS {layer}.{table}: {count} rows")
    print("E1/E2 acceptance passed")


if __name__ == "__main__":
    main()
