from pathlib import Path
from tempfile import TemporaryDirectory

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession

builder = (
    SparkSession.builder.master("local[2]")
    .appName("dataops-delta-smoke")
    .config(
        "spark.sql.extensions",
        "io.delta.sql.DeltaSparkSessionExtension",
    )
    .config(
        "spark.sql.catalog.spark_catalog",
        "org.apache.spark.sql.delta.catalog.DeltaCatalog",
    )
)

spark = configure_spark_with_delta_pip(builder).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

try:
    with TemporaryDirectory(prefix="dataops-delta-") as directory:
        path = str(Path(directory) / "orders")

        # Version 0: Initial data
        initial = spark.createDataFrame(
            [(1, "created"), (2, "approved")],
            ["order_id", "status"],
        )

        initial.write.format("delta").mode("overwrite").save(path)

        print("\nVERSION 0:")
        spark.read.format("delta").load(path).show()

        # Version 1: Updated data
        updated = spark.createDataFrame(
            [(1, "delivered"), (2, "approved")],
            ["order_id", "status"],
        )

        updated.write.format("delta").mode("overwrite").save(path)

        print("\nVERSION 1:")
        spark.read.format("delta").load(path).show()

        # Delta time travel
        print("\nTIME TRAVEL - VERSION 0:")
        (spark.read.format("delta").option("versionAsOf", 0).load(path).show())

        print("\nDELTA LAKE SMOKE TEST PASSED")

finally:
    spark.stop()
