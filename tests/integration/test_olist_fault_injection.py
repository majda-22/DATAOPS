from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pyspark.sql import SparkSession
from pyspark.sql.types import StringType, StructField, StructType

from dataops.contracts.models import DatasetContract
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
    ("fault", "expected_rule"),
    [
        ("duplicate_order_id", "order_id_unique"),
        ("invalid_status", "order_status_allowed"),
        ("null_order_id", "order_id_not_null"),
        ("orphan_customer", "orders_customer_fk"),
    ],
)
def test_fault_detection_blocks_publication(
    spark,
    contract,
    fault,
    expected_rule,
):
    orders = deepcopy(valid_orders())

    # Inject exactly one fault.
    if fault == "duplicate_order_id":
        orders[1]["order_id"] = orders[0]["order_id"]

    elif fault == "invalid_status":
        orders[1]["order_status"] = "INVALID_STATUS"

    elif fault == "null_order_id":
        orders[1]["order_id"] = None

    elif fault == "orphan_customer":
        orders[1]["customer_id"] = "UNKNOWN_CUSTOMER"

    orders_df = spark.createDataFrame(orders, schema=SCHEMA)

    # Valid customer-reference dataset.
    customers_df = spark.createDataFrame(
        [
            ("customer_001",),
            ("customer_002",),
        ],
        ["customer_id"],
    )

    # Execute the REAL Spark quality engine.
    report = evaluate_spark(
        orders_df,
        contract,
        source="synthetic_fault_injection",
        reference_data={"olist_customers": customers_df},
    )

    assert report["status"] == "FAIL"

    failed_rules = {result["rule_id"] for result in report["results"] if result["status"] == "FAIL"}

    assert expected_rule in failed_rules

    # Simulate a publication callback.
    published = []

    def publish():
        published.append("silver_overwritten")

    # Quality gate must reject Spark's failure report.
    with pytest.raises(QualityGateError):
        publish_if_quality_passed(report, publish)

    # No Silver publication occurred.
    assert published == []
