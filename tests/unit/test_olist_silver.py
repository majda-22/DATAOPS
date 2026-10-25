import pytest
from pyspark.sql import SparkSession

from dataops.pipelines.olist_silver import transform_olist_orders


@pytest.fixture(scope="module")
def spark():
    session = SparkSession.builder.master("local[2]").appName("olist-silver-tests").getOrCreate()

    yield session
    session.stop()


def test_valid_timestamps_are_converted(spark):
    df = spark.createDataFrame(
        [
            (
                "2018-08-07 05:42:46",
                "2018-08-07 05:50:08",
                "2018-08-13 09:24:00",
                "2018-08-27 15:28:22",
                "2018-09-18 00:00:00",
            )
        ],
        [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )

    result = transform_olist_orders(df)

    assert all(result.schema[column].dataType.typeName() == "timestamp" for column in df.columns)


def test_invalid_timestamp_is_rejected(spark):
    df = spark.createDataFrame(
        [
            (
                "invalid",
                "2018-08-07 05:50:08",
                "2018-08-13 09:24:00",
                "2018-08-27 15:28:22",
                "2018-09-18 00:00:00",
            )
        ],
        [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )

    with pytest.raises(ValueError, match="Invalid timestamp"):
        transform_olist_orders(df)
