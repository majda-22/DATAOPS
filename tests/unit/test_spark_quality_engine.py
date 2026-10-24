import pytest
from pyspark.sql import SparkSession

from dataops.contracts.models import DatasetContract, ForeignKeyContract
from dataops.quality.spark_engine import evaluate_spark


@pytest.fixture(scope="module")
def spark():
    session = SparkSession.builder.master("local[2]").appName("spark-quality-tests").getOrCreate()
    yield session
    session.stop()


@pytest.fixture
def contract():
    return DatasetContract.model_validate(
        {
            "dataset": "test_orders",
            "version": 1,
            "description": "Test orders",
            "layer": "bronze",
            "format": "delta",
            "columns": [
                {"name": "order_id", "logical_type": "string", "nullable": False},
                {"name": "status", "logical_type": "string", "nullable": False},
            ],
            "primary_key": ["order_id"],
            "quality_rules": [
                {
                    "id": "status_allowed",
                    "type": "accepted_values",
                    "column": "status",
                    "values": ["created", "delivered"],
                },
                {
                    "id": "minimum_volume",
                    "type": "min_row_count",
                    "min_rows": 2,
                },
            ],
        }
    )


def test_clean_spark_data_passes(spark, contract):
    df = spark.createDataFrame(
        [("1", "created"), ("2", "delivered")],
        ["order_id", "status"],
    )

    result = evaluate_spark(df, contract)

    assert result["status"] == "PASS"
    assert result["row_count"] == 2
    assert all(check["status"] == "PASS" for check in result["results"])


def test_duplicate_key_and_invalid_status_fail(spark, contract):
    df = spark.createDataFrame(
        [("1", "created"), ("1", "invalid")],
        ["order_id", "status"],
    )

    result = evaluate_spark(df, contract)
    checks = {check["rule_id"]: check for check in result["results"]}

    assert result["status"] == "FAIL"
    assert checks["auto_primary_key_unique"]["failed_rows"] == 1
    assert checks["status_allowed"]["failed_rows"] == 1


def test_insufficient_volume_fails(spark, contract):
    df = spark.createDataFrame(
        [("1", "created")],
        ["order_id", "status"],
    )

    result = evaluate_spark(df, contract)
    checks = {check["rule_id"]: check for check in result["results"]}

    assert checks["minimum_volume"]["status"] == "FAIL"
    assert checks["minimum_volume"]["failed_rows"] == 0


def test_missing_column_raises_error(spark, contract):
    df = spark.createDataFrame(
        [("1",)],
        ["order_id"],
    )

    with pytest.raises(ValueError, match="Missing contract columns"):
        evaluate_spark(df, contract)


def test_spark_foreign_key_detects_orphans(spark, contract):
    fk_contract = contract.model_copy(
        update={
            "foreign_keys": [
                ForeignKeyContract(
                    id="orders_customer_fk",
                    columns=["order_id"],
                    reference_dataset="customers",
                    reference_columns=["customer_id"],
                )
            ]
        }
    )

    orders = spark.createDataFrame(
        [("1", "created"), ("2", "delivered")],
        ["order_id", "status"],
    )

    customers = spark.createDataFrame(
        [("1",)],
        ["customer_id"],
    )

    report = evaluate_spark(
        orders,
        fk_contract,
        reference_data={"customers": customers},
    )

    checks = {check["rule_id"]: check for check in report["results"]}

    assert checks["orders_customer_fk"]["status"] == "FAIL"
    assert checks["orders_customer_fk"]["failed_rows"] == 1


def test_spark_foreign_key_requires_reference_data(spark, contract):
    fk_contract = contract.model_copy(
        update={
            "foreign_keys": [
                ForeignKeyContract(
                    id="orders_customer_fk",
                    columns=["order_id"],
                    reference_dataset="customers",
                    reference_columns=["customer_id"],
                )
            ]
        }
    )

    orders = spark.createDataFrame(
        [("1", "created")],
        ["order_id", "status"],
    )

    with pytest.raises(ValueError, match="requires reference data"):
        evaluate_spark(orders, fk_contract)


def test_spark_foreign_key_rejects_duplicate_reference_keys(spark, contract):
    fk_contract = contract.model_copy(
        update={
            "foreign_keys": [
                ForeignKeyContract(
                    id="orders_customer_fk",
                    columns=["order_id"],
                    reference_dataset="customers",
                    reference_columns=["customer_id"],
                )
            ]
        }
    )

    orders = spark.createDataFrame([("1", "created")], ["order_id", "status"])
    customers = spark.createDataFrame([("1",), ("1",)], ["customer_id"])

    with pytest.raises(ValueError, match="Reference key is not unique"):
        evaluate_spark(
            orders,
            fk_contract,
            reference_data={"customers": customers},
        )


def test_spark_foreign_key_counts_multiple_orphans(spark, contract):
    fk_contract = contract.model_copy(
        update={
            "foreign_keys": [
                ForeignKeyContract(
                    id="orders_customer_fk",
                    columns=["order_id"],
                    reference_dataset="customers",
                    reference_columns=["customer_id"],
                )
            ]
        }
    )

    orders = spark.createDataFrame(
        [("1", "created"), ("2", "created"), ("3", "delivered")],
        ["order_id", "status"],
    )
    customers = spark.createDataFrame([("1",)], ["customer_id"])

    report = evaluate_spark(
        orders,
        fk_contract,
        reference_data={"customers": customers},
    )

    checks = {r["rule_id"]: r for r in report["results"]}
    assert checks["orders_customer_fk"]["failed_rows"] == 2


def test_spark_composite_foreign_key_ignores_blank_components(spark):
    contract = DatasetContract.model_validate(
        {
            "dataset": "items",
            "version": 1,
            "description": "Composite foreign-key test",
            "layer": "bronze",
            "format": "delta",
            "columns": [
                {"name": "order_id", "logical_type": "string", "nullable": True},
                {"name": "item_id", "logical_type": "string", "nullable": True},
            ],
            "primary_key": [],
            "keyless_reason": "Test fixture",
            "quality_rules": [],
            "foreign_keys": [
                {
                    "id": "items_fk",
                    "columns": ["order_id", "item_id"],
                    "reference_dataset": "reference_items",
                    "reference_columns": ["order_id", "item_id"],
                }
            ],
        }
    )

    items = spark.createDataFrame(
        [("A", "1"), ("A", "2"), ("B", ""), ("C", "3")],
        ["order_id", "item_id"],
    )
    reference = spark.createDataFrame(
        [("A", "1"), ("C", "3")],
        ["order_id", "item_id"],
    )

    report = evaluate_spark(
        items,
        contract,
        reference_data={"reference_items": reference},
    )

    checks = {r["rule_id"]: r for r in report["results"]}

    # A/2 is orphaned; B/blank is ignored.
    assert checks["items_fk"]["failed_rows"] == 1
