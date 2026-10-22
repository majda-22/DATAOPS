import os
from pathlib import Path

from delta import configure_spark_with_delta_pip
from dotenv import load_dotenv
from pyspark.sql import SparkSession
from pyspark.sql.types import StringType, StructField, StructType

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

SOURCE = ROOT / "data/raw/olist/olist_orders_dataset.csv"
TARGET = "s3a://bronze/olist/orders"
EXPECTED_ROWS = 99441

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

schema = StructType([StructField(name, StringType(), True) for name in COLUMNS])


def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)

    builder = (
        SparkSession.builder.master("local[2]")
        .appName("dataops-olist-bronze-ingestion")
        .config(
            "spark.sql.extensions",
            "io.delta.sql.DeltaSparkSessionExtension",
        )
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config(
            "spark.hadoop.fs.s3a.endpoint",
            f"http://localhost:{os.getenv('MINIO_API_PORT', '19000')}",
        )
        .config("spark.hadoop.fs.s3a.endpoint.region", "us-east-1")
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        .config(
            "spark.hadoop.fs.s3a.access.key",
            os.environ["MINIO_ROOT_USER"],
        )
        .config(
            "spark.hadoop.fs.s3a.secret.key",
            os.environ["MINIO_ROOT_PASSWORD"],
        )
    )

    spark = configure_spark_with_delta_pip(
        builder,
        extra_packages=["org.apache.hadoop:hadoop-aws:3.5.0"],
    ).getOrCreate()

    spark.sparkContext.setLogLevel("ERROR")

    try:
        df = (
            spark.read.option("header", "true")
            .option("mode", "FAILFAST")
            .schema(schema)
            .csv(str(SOURCE))
        )

        source_count = df.count()
        print(f"Source rows: {source_count}")

        if source_count != EXPECTED_ROWS:
            raise ValueError(f"Expected {EXPECTED_ROWS} rows, got {source_count}")

        (df.write.format("delta").mode("overwrite").save(TARGET))

        result = spark.read.format("delta").load(TARGET)

        target_count = result.count()
        print(f"Delta rows: {target_count}")

        if target_count != source_count:
            raise ValueError("Source and Delta row counts differ")

        if result.columns != COLUMNS:
            raise ValueError("Delta schema does not match source")

        result.show(5, truncate=False)

        print("OLIST BRONZE INGESTION PASSED")
        print(f"Location: {TARGET}")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
