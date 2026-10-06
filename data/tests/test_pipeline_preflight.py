import copy
from unittest.mock import Mock

import pytest

import pipeline_job
import pipeline_preflight
import silver_job
from bronze_ingest import TABLES, IngestionError
from silver_job import DEPENDENCIES, silver_fingerprint
from silver_queries import SILVER_TABLES

ROOT = "/Volumes/cdc/bronze/checkpoints"
SOURCE = "`cdc`.`bronze`"
CATALOG = "`fashion`"


def qualified(dependency):
    return CATALOG + "." + ".".join(f"`{part}`" for part in dependency.split("."))


@pytest.fixture
def metadata():
    snapshots, markers = {}, {}
    for table in TABLES:
        source = f"{SOURCE}.`lb_{table}_history`"
        target = qualified("bronze." + table)
        snapshots[source] = {"id": "source-" + table, "version": 3}
        snapshots[target] = {"id": "bronze-" + table, "version": 5}
        markers[f"{ROOT}/fashion/e1/{table}/source.json"] = {
            "source": source,
            "target": target,
            "source_id": "source-" + table,
            "target_id": "bronze-" + table,
            "starting_version": 2,
            "processed_version": 3,
        }
    for table in SILVER_TABLES:
        snapshots[qualified("silver." + table)] = {"id": "silver-" + table, "version": 7}
    for table in SILVER_TABLES:
        inputs = {dep: copy.deepcopy(snapshots[qualified(dep)]) for dep in DEPENDENCIES[table]}
        markers[f"{ROOT}/fashion/e2/{table}.json"] = {
            "fingerprint": silver_fingerprint(table, inputs, ()),
            "target": copy.deepcopy(snapshots[qualified("silver." + table)]),
        }
    reader = Mock()
    reader.snapshot.side_effect = snapshots.__getitem__
    reader.marker.side_effect = markers.__getitem__
    reader.read_many.side_effect = lambda read, names: {
        name: read(name) for name in dict.fromkeys(names)
    }
    reader.snapshot_many.side_effect = lambda names: reader.read_many(reader.snapshot, names)
    reader.snapshots = snapshots
    reader.markers = markers
    return reader


def check(metadata, stage="all", excluded=()):
    return pipeline_preflight.unchanged_stages(metadata, SOURCE, "fashion", ROOT, excluded, stage)


@pytest.mark.parametrize("stage", ["all", "bronze", "silver"])
def test_unchanged_stage_is_certified_without_writes_or_unrelated_reads(metadata, stage):
    result = check(metadata, stage)
    assert set(result) == ({"bronze", "silver"} if stage == "all" else {stage})
    assert all(value == "SKIP" for tables in result.values() for value in tables.values())
    names = [call.args[0] for call in metadata.snapshot.call_args_list]
    assert len(names) == len(set(names))
    if stage == "silver":
        assert all("lb_" not in name for name in names)
    if stage == "bronze":
        assert all("`silver`" not in name for name in names)


@pytest.mark.parametrize(
    "table",
    [
        "`cdc`.`bronze`.`lb_users_history`",
        qualified("bronze.users"),
        qualified("silver.fact_orders"),
    ],
)
def test_source_or_dependency_or_silver_target_change_requires_processing(metadata, table):
    metadata.snapshots[table]["version"] += 1
    assert check(metadata) is None


@pytest.mark.parametrize("kind", ["source_id", "target_id", "version_backwards", "wrong_source"])
def test_identity_and_checkpoint_invariants_cannot_be_skipped(metadata, kind):
    source = metadata.snapshots[f"{SOURCE}.`lb_users_history`"]
    if kind == "source_id":
        source["id"] = "recreated"
    elif kind == "target_id":
        metadata.snapshots[qualified("bronze.users")]["id"] = "recreated"
    elif kind == "version_backwards":
        source["version"] = 0
    else:
        metadata.markers[f"{ROOT}/fashion/e1/users/source.json"]["source"] = "other-source"
    with pytest.raises(IngestionError, match="rebuild"):
        check(metadata)


def test_changed_silver_config_or_transform_requires_refresh(metadata, monkeypatch):
    assert check(metadata, excluded=(2,)) is None
    monkeypatch.setattr(silver_job, "TRANSFORM_VERSION", 2)
    assert check(metadata) is None


@pytest.mark.parametrize("missing", ["marker", "table"])
def test_missing_checkpoint_or_table_never_certifies_skip(metadata, missing):
    if missing == "marker":
        del metadata.markers[f"{ROOT}/fashion/e1/users/source.json"]
    else:
        del metadata.snapshots[qualified("silver.fact_orders")]
    with pytest.raises(KeyError):
        check(metadata)


def test_preflight_failure_falls_back_without_exposing_payload(monkeypatch):
    monkeypatch.setattr("databricks.sdk.config.Config._resolve_host_metadata", lambda self: None)
    monkeypatch.setenv("DATABRICKS_HOST", "https://example.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "fake-token-for-test")
    monkeypatch.setattr(
        "databricks.sdk.WorkspaceClient", Mock(side_effect=RuntimeError("private credential"))
    )
    report = Mock()
    assert (
        pipeline_preflight.preflight("wh", SOURCE, "fashion", ROOT, (), "all", report=report)
        is None
    )
    assert "RuntimeError" in report.call_args.args[0]
    assert "private" not in report.call_args.args[0]


def test_preflight_initializes_real_sdk_with_bounded_timeouts(metadata, monkeypatch):
    monkeypatch.setattr("databricks.sdk.config.Config._resolve_host_metadata", lambda self: None)
    monkeypatch.setenv("DATABRICKS_HOST", "https://example.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "fake-token-for-test")

    def reader(client, warehouse_id):
        assert client.config.http_timeout_seconds == 15
        assert client.config.retry_timeout_seconds == 15
        assert warehouse_id == "wh"
        return metadata

    monkeypatch.setattr(pipeline_preflight, "WarehouseMetadata", reader)
    result = pipeline_preflight.preflight("wh", SOURCE, "fashion", ROOT, (), "all", report=Mock())
    assert set(result) == {"bronze", "silver"}


def test_no_change_job_never_touches_spark_or_stage_writers(metadata, monkeypatch):
    monkeypatch.setattr(pipeline_job, "preflight", lambda *args, **kwargs: check(metadata))
    spark = Mock()
    bronze = Mock()
    silver = Mock()
    monkeypatch.setattr(pipeline_job.CDCIngest, "run", bronze)
    monkeypatch.setattr(pipeline_job, "run_silver", silver)
    gold = Mock(return_value={"revenue_daily": 2})
    monkeypatch.setattr(pipeline_job, "run_gold_on_warehouse", gold)
    result = pipeline_job.run_pipeline(spark, "cdc", ROOT, metadata_warehouse_id="wh")
    assert len(result["bronze"]) == 13
    assert len(result["silver"]) == 7
    assert result["gold"] == {"revenue_daily": 2}
    gold.assert_called_once_with("wh", "fashion", report=print)
    assert result["timings_seconds"]["spark_startup"] == 0
    assert result["timings_seconds"]["preflight"] >= 0
    assert spark.mock_calls == []
    bronze.assert_not_called()
    silver.assert_not_called()


def test_pending_data_uses_normal_pipeline_and_keeps_startup_out_of_stage_timings(monkeypatch):
    monkeypatch.setattr(pipeline_job, "preflight", Mock(return_value=None))
    monkeypatch.setattr(
        pipeline_job.time,
        "monotonic",
        Mock(side_effect=[0, 1, 2, 722, 723, 725, 726, 729, 730, 734]),
    )
    bronze = Mock(return_value={"users": "CDC"})
    monkeypatch.setattr(pipeline_job.CDCIngest, "run", bronze)
    silver = Mock(return_value={"dim_shops": 3})
    monkeypatch.setattr(pipeline_job, "run_silver", silver)
    gold = Mock(return_value={"revenue_daily": 2})
    monkeypatch.setattr(pipeline_job, "run_gold", gold)
    result = pipeline_job.run_pipeline(Mock(), "cdc", ROOT, metadata_warehouse_id="wh")
    assert result["bronze"] == {"users": "CDC"}
    assert result["silver"] == {"dim_shops": 3}
    assert result["timings_seconds"] == {
        "preflight": 1,
        "spark_startup": 720,
        "bronze": 2,
        "silver": 3,
        "gold": 4,
    }
    bronze.assert_called_once()
    silver.assert_called_once()
    gold.assert_called_once()


def test_startup_failure_never_reports_stage_success(monkeypatch):
    spark = Mock()
    spark.sql.side_effect = RuntimeError("Spark unavailable")
    bronze, silver = Mock(), Mock()
    monkeypatch.setattr(pipeline_job.CDCIngest, "run", bronze)
    monkeypatch.setattr(pipeline_job, "run_silver", silver)
    with pytest.raises(RuntimeError, match="Spark unavailable"):
        pipeline_job.run_pipeline(spark, "cdc", ROOT)
    bronze.assert_not_called()
    silver.assert_not_called()
