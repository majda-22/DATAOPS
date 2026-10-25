import json
import os
from pathlib import Path

import yaml
from delta import configure_spark_with_delta_pip
from dotenv import load_dotenv
from pyspark.sql import SparkSession
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from dataops.contracts.models import DatasetContract
from dataops.observability.quality_store import persist_quality_report
from dataops.pipelines.olist_silver import transform_olist_orders
from dataops.pipelines.quality_gate import publish_if_quality_passed
from dataops.quality.spark_engine import evaluate_spark

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "configs/datasets/olist_orders.yaml"
SOURCE = "s3a://bronze/olist/orders"
SILVER_TARGET = "s3a://silver/olist/orders"
TIMESTAMP_COLUMNS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]

load_dotenv(ROOT / ".env")


def main():
    with CONTRACT_PATH.open(encoding="utf-8") as file:
        contract = DatasetContract.model_validate(yaml.safe_load(file))

    # This first integration test excludes foreign-key checks.
    # They require the referenced customers dataset.

    builder = (
        SparkSession.builder.master("local[2]")
        .appName("dataops-olist-bronze-quality")
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
        df = spark.read.format("delta").load(SOURCE)

        customers_path = ROOT / "data/raw/olist/olist_customers_dataset.csv"

        customers = (
            spark.read.option("header", "true")
            .option("mode", "FAILFAST")
            .option("inferSchema", "false")
            .csv(str(customers_path))
        )

        report = evaluate_spark(
            df,
            contract,
            source=SOURCE,
            reference_data={"olist_customers": customers},
        )
        print(json.dumps(report, indent=2))

        report_path = ROOT / "data/reports/olist_spark_quality.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )
        database_url = os.environ.get("DATABASE_URL")

        if not database_url:
            raise RuntimeError("DATABASE_URL is not configured")

        engine = create_engine(database_url)

        try:
            with Session(engine) as session:
                run_id = persist_quality_report(
                    session,
                    report,
                    pipeline_name="olist_bronze_quality",
                )

            print(f"Persisted pipeline run: {run_id}")

        finally:
            engine.dispose()

        # Stop Silver publication if Bronze quality validation failed.

        def publish_silver() -> None:
            """Transform and publish validated Olist orders to Silver."""

            print("\nQuality gate PASSED. Preparing Silver data.")

            spark.conf.set("spark.sql.session.timeZone", "UTC")

            # Transform Bronze string timestamps into Silver timestamps.
            silver_df = transform_olist_orders(df)

            source_count = report["row_count"]
            silver_count = silver_df.count()

            if silver_count != source_count:
                raise ValueError("Row count changed during Silver transformation")

            # Write the Silver Delta table into MinIO.
            (silver_df.write.format("delta").mode("overwrite").save(SILVER_TARGET))

            # Read the data back from MinIO to verify publication.
            published = spark.read.format("delta").load(SILVER_TARGET)

            published_count = published.count()

            if published_count != source_count:
                raise ValueError("Silver output row count does not match Bronze")

            published.printSchema()

            print(f"Silver rows: {published_count}")
            print(f"Silver location: {SILVER_TARGET}")
            print("BRONZE TO SILVER PIPELINE PASSED")

        # The gate decides whether publish_silver is executed.
        publish_if_quality_passed(report, publish_silver)
        print(f"\nReport saved to: {report_path}")
        print(f"Overall status: {report['status']}")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
