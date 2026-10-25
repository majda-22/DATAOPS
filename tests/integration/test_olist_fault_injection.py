from pathlib import Path

import pytest
import yaml
from pyspark.sql import SparkSession
from pyspark.sql.types import StringType, StructField, StructType

from dataops.contracts.models import DatasetContract
from dataops.faults.injector import inject_fault
from dataops.faults.models import FaultSpec
from dataops.pipelines.quality_gate import (
    QualityGateError,
    publish_if_quality_passed,
)
from dataops.quality.spark_engine import evaluate_spark

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "configs/datasets/olist_orders.yaml"

COLUMNS = [
    "order_id",
    "customer_id",
    "order_status",
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]

SCHEMA = StructType([StructField(name, StringType(), True) for name in COLUMNS])


@pytest.fixture(scope="module")
def spark():
    session = (
        SparkSession.builder.master("local[2]").appName("olist-fault-injection-tests").getOrCreate()
    )

    yield session
    session.stop()


@pytest.fixture(scope="module")
def contract():
    with CONTRACT_PATH.open(encoding="utf-8") as file:
        return DatasetContract.model_validate(yaml.safe_load(file))


def valid_orders():
    """Two synthetic orders satisfying the Olist contract."""
    return [
        {
            "order_id": "order_001",
            "customer_id": "customer_001",
            "order_status": "delivered",
            "order_purchase_timestamp": "2018-08-07 05:42:46",
            "order_approved_at": "2018-08-07 05:50:08",
            "order_delivered_carrier_date": "2018-08-13 09:24:00",
            "order_delivered_customer_date": "2018-08-27 15:28:22",
            "order_estimated_delivery_date": "2018-09-18 00:00:00",
        },
        {
            "order_id": "order_002",
            "customer_id": "customer_002",
            "order_status": "shipped",
            "order_purchase_timestamp": "2018-08-08 10:00:00",
            "order_approved_at": "2018-08-08 11:00:00",
            "order_delivered_carrier_date": None,
            "order_delivered_customer_date": None,
            "order_estimated_delivery_date": "2018-09-20 00:00:00",
        },
    ]


@pytest.mark.parametrize(
    "spec",
    [
        FaultSpec(
            fault_type="duplicate_key",
            column="order_id",
            row_indices=(1,),
            source_row_index=0,
            expected_rule="order_id_unique",
        ),
        FaultSpec(
            fault_type="invalid_value",
            column="order_status",
            row_indices=(1,),
            value="INVALID_STATUS",
            expected_rule="order_status_allowed",
        ),
        FaultSpec(
            fault_type="null_value",
            column="order_id",
            row_indices=(1,),
            expected_rule="order_id_not_null",
        ),
        FaultSpec(
            fault_type="foreign_key_violation",
            column="customer_id",
            row_indices=(1,),
            value="UNKNOWN_CUSTOMER",
            expected_rule="orders_customer_fk",
        ),
    ],
    ids=[
        "duplicate_order_id",
        "invalid_status",
        "null_order_id",
        "orphan_customer",
    ],
)
def test_fault_detection_blocks_publication(
    spark,
    contract,
    spec,
):
    # 1. Inject the fault and obtain separate ground truth.
    corrupted_orders, ground_truth = inject_fault(
        valid_orders(),
        spec,
    )

    # 2. Convert corrupted records to a Spark DataFrame.
    orders_df = spark.createDataFrame(
        corrupted_orders,
        schema=SCHEMA,
    )

    # 3. Prepare valid customer references.
    customers_df = spark.createDataFrame(
        [
            ("customer_001",),
            ("customer_002",),
        ],
        ["customer_id"],
    )

    # 4. Execute Spark quality validation.
    # Ground truth is NOT passed to the detector.
    report = evaluate_spark(
        orders_df,
        contract,
        source="synthetic_fault_injection",
        reference_data={"olist_customers": customers_df},
    )

    # 5. Verify Spark detected a quality failure.
    assert report["status"] == "FAIL"

    failed_rules = {result["rule_id"] for result in report["results"] if result["status"] == "FAIL"}

    # Compare detector output with held-out ground truth.
    assert ground_truth.expected_rule in failed_rules

    # 6. Verify the quality gate prevents publication.
    published = []

    def publish():
        published.append("silver_overwritten")

    with pytest.raises(QualityGateError):
        publish_if_quality_passed(report, publish)

    assert published == []
