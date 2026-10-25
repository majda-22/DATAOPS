import pytest
from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession

from dataops.pipelines.quality_gate import (
    QualityGateError,
    publish_if_quality_passed,
)


@pytest.fixture(scope="module")
def spark():
    builder = (
        SparkSession.builder.master("local[2]")
        .appName("silver-quality-gate-integration")
        .config(
            "spark.sql.extensions",
            "io.delta.sql.DeltaSparkSessionExtension",
        )
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )

    session = configure_spark_with_delta_pip(builder).getOrCreate()

    yield session

    session.stop()


def test_failed_quality_gate_preserves_silver_delta(spark, tmp_path):
    # Temporary local Delta table, separate from real MinIO data.
    silver_path = str(tmp_path / "silver_orders")

    # Step 1: Publish initially valid Silver records.
    valid_df = spark.createDataFrame(
        [
            ("order_001", "delivered"),
            ("order_002", "shipped"),
        ],
        ["order_id", "order_status"],
    )

    valid_df.write.format("delta").mode("overwrite").save(silver_path)

    # Step 2: Prepare corrupted incoming data.
    corrupted_df = spark.createDataFrame(
        [
            ("order_001", "INVALID_STATUS"),
            ("order_001", "INVALID_STATUS"),
        ],
        ["order_id", "order_status"],
    )

    # Simulate an already-failed validation report.
    failed_report = {
        "status": "FAIL",
        "results": [
            {"rule_id": "order_id_unique", "status": "FAIL"},
            {"rule_id": "order_status_allowed", "status": "FAIL"},
        ],
    }

    def publish_corrupted_data():
        corrupted_df.write.format("delta").mode("overwrite").save(silver_path)

    # Step 3: The quality gate must reject publication.
    with pytest.raises(QualityGateError):
        publish_if_quality_passed(
            failed_report,
            publish_corrupted_data,
        )

    # Step 4: Check actual Silver contents after rejection.
    silver_after = spark.read.format("delta").load(silver_path)

    actual_rows = {(row.order_id, row.order_status) for row in silver_after.collect()}

    assert actual_rows == {
        ("order_001", "delivered"),
        ("order_002", "shipped"),
    }

    # No new Delta commit should have occurred.
    history = spark.sql(f"DESCRIBE HISTORY delta.`{silver_path}`").select("version").collect()
    assert len(history) == 1
    assert history[0]["version"] == 0
