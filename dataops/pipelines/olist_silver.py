from pyspark.sql import DataFrame
from pyspark.sql import functions as F

TIMESTAMP_COLUMNS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


def transform_olist_orders(df: DataFrame) -> DataFrame:
    """Convert Bronze Olist orders into typed Silver records."""

    silver_df = df

    for column in TIMESTAMP_COLUMNS:
        raw = F.trim(F.col(column))

        normalized = F.when(
            raw.isNull() | (raw == ""),
            F.lit(None),
        ).otherwise(raw)

        parsed = F.try_to_timestamp(
            normalized,
            F.lit("yyyy-MM-dd HH:mm:ss"),
        )

        # Fail instead of silently converting invalid values to NULL.
        invalid_rows = df.filter(
            F.col(column).isNotNull()
            & (F.trim(F.col(column)) != "")
            & F.try_to_timestamp(
                F.col(column),
                F.lit("yyyy-MM-dd HH:mm:ss"),
            ).isNull()
        )

        if invalid_rows.limit(1).count() > 0:
            raise ValueError(f"Invalid timestamp values in {column}")

        silver_df = silver_df.withColumn(column, parsed)

    return silver_df
