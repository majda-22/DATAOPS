import os
from pathlib import Path
from uuid import uuid4

from delta import configure_spark_with_delta_pip
from dotenv import load_dotenv
from pyspark.sql import SparkSession

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

access_key = os.environ["MINIO_ROOT_USER"]
secret_key = os.environ["MINIO_ROOT_PASSWORD"]

# Spark runs directly on Ubuntu, outside Docker.
endpoint = f"http://localhost:{os.getenv('MINIO_API_PORT', '9000')}"

builder = (
    SparkSession.builder.master("local[2]")
    .appName("dataops-delta-minio-smoke")
    .config(
        "spark.sql.extensions",
        "io.delta.sql.DeltaSparkSessionExtension",
    )
    .config(
        "spark.sql.catalog.spark_catalog",
        "org.apache.spark.sql.delta.catalog.DeltaCatalog",
    )
    .config("spark.hadoop.fs.s3a.endpoint", endpoint)
    .config("spark.hadoop.fs.s3a.endpoint.region", "us-east-1")
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
    .config(
        "spark.hadoop.fs.s3a.aws.credentials.provider",
        "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
    )
    .config("spark.hadoop.fs.s3a.access.key", access_key)
    .config("spark.hadoop.fs.s3a.secret.key", secret_key)
)

spark = configure_spark_with_delta_pip(
    builder,
    extra_packages=["org.apache.hadoop:hadoop-aws:3.5.0"],
).getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

# Unique path prevents collisions with previous test runs.
table_path = f"s3a://bronze/smoke/orders-{uuid4().hex[:12]}"

try:
    print("Target:", table_path)

    initial = spark.createDataFrame(
        [(1, "created"), (2, "approved")],
        ["order_id", "status"],
    )

    initial.write.format("delta").mode("overwrite").save(table_path)

    print("\nVERSION 0:")
    spark.read.format("delta").load(table_path).show()

    updated = spark.createDataFrame(
        [(1, "delivered"), (2, "approved")],
        ["order_id", "status"],
    )

    updated.write.format("delta").mode("overwrite").save(table_path)

    print("\nVERSION 1:")
    spark.read.format("delta").load(table_path).show()

    print("\nTIME TRAVEL - VERSION 0:")
    (spark.read.format("delta").option("versionAsOf", 0).load(table_path).show())

    print("\nSPARK + DELTA + MINIO SMOKE TEST PASSED")

finally:
    spark.stop()
