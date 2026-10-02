import sys
from pathlib import Path

import pytest
from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="session")
def spark(tmp_path_factory):
    builder = (
        SparkSession.builder.master("local[2]")
        .appName("daln-bronze-tests")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.warehouse.dir", str(tmp_path_factory.mktemp("delta")))
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.databricks.delta.snapshotPartitions", "1")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog"
        )
    )
    session = configure_spark_with_delta_pip(builder).getOrCreate()
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


class SparkSQL:
    def __init__(self, spark):
        self.spark = spark

    def execute(self, statement):
        return self.spark.sql(statement).collect()


@pytest.fixture
def sql(spark):
    adapter = SparkSQL(spark)
    adapter.execute("CREATE DATABASE source")
    adapter.execute("CREATE DATABASE bronze")
    yield adapter
    adapter.execute("DROP DATABASE source CASCADE")
    adapter.execute("DROP DATABASE bronze CASCADE")
