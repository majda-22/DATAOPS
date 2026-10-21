import os
import shutil
import sys
import time
from pathlib import Path

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLE_PATH = PROJECT_ROOT / "data" / "delta_smoke" / "orders"


def main() -> None:
    # Workers must use the same virtual environment as this process on Windows.
    os.environ["PYSPARK_PYTHON"] = sys.executable
    if os.name == "nt":
        hadoop_home = Path(os.environ.get("HADOOP_HOME", "C:/hadoop"))
        if not (hadoop_home / "bin" / "winutils.exe").is_file():
            hadoop_home = PROJECT_ROOT / ".tools" / "hadoop" / "hadoop-3.4.2"
        if not (hadoop_home / "bin" / "winutils.exe").is_file():
            raise RuntimeError(
                "Windows Hadoop binaries are missing. Set HADOOP_HOME to a directory "
                "containing bin/winutils.exe and bin/hadoop.dll."
            )
        os.environ["HADOOP_HOME"] = str(hadoop_home)
        os.environ["PATH"] = str(hadoop_home / "bin") + os.pathsep + os.environ["PATH"]
    # Start Spark with Delta Lake enabled.
    builder = (
        SparkSession.builder.appName("DataOpsDetective-Delta-Smoke-Test")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.databricks.delta.snapshotPartitions", "2")
        .config(
            "spark.jars.ivySettings",
            (PROJECT_ROOT / "configs" / "spark" / "ivysettings.xml").as_uri(),
        )
        .config(
            "spark.jars.ivy",
            str(PROJECT_ROOT / ".spark-ivy" / "maven-central"),
        )
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )

    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    try:
        print(f"Spark version: {spark.version}")
        print(f"Delta table path: {TABLE_PATH}")

        # Reset only this dedicated test table so reruns are reproducible.
        if TABLE_PATH.exists():
            if TABLE_PATH.resolve() != PROJECT_ROOT.resolve() / "data" / "delta_smoke" / "orders":
                raise ValueError(f"Refusing to remove unexpected table path: {TABLE_PATH}")
            shutil.rmtree(TABLE_PATH)

        # Create the initial dataset.
        initial_data = [
            (1, "books", 10.0),
            (2, "toys", 20.0),
            (3, "books", 15.0),
        ]
        columns = ["id", "category", "amount"]
        initial_df = spark.createDataFrame(initial_data, columns)

        # Write a partitioned Delta table.
        initial_df.write.format("delta").partitionBy("category").save(str(TABLE_PATH))
        print("\nInitial Delta table:")
        spark.read.format("delta").load(str(TABLE_PATH)).show()

        # Overwrite only the books partition.
        updated_data = [(1, "books", 99.0)]
        updated_df = spark.createDataFrame(updated_data, columns)

        updated_df.write.format("delta").mode("overwrite").option(
            "replaceWhere", "category = 'books'"
        ).save(str(TABLE_PATH))

        print("Current table after overwriting books:")
        spark.read.format("delta").load(str(TABLE_PATH)).show()

        # Read the original version (before the overwrite).
        old_df = spark.read.format("delta").option("versionAsOf", 0).load(str(TABLE_PATH))

        print("Original table, version 0:")
        old_df.show()

        # Verify the expected results.
        current_rows = {
            (row.id, row.category, row.amount)
            for row in spark.read.format("delta").load(str(TABLE_PATH)).collect()
        }
        original_rows = {(row.id, row.category, row.amount) for row in old_df.collect()}

        assert current_rows == {
            (1, "books", 99.0),
            (2, "toys", 20.0),
        }, f"Unexpected current rows: {current_rows}"

        assert original_rows == {
            (1, "books", 10.0),
            (2, "toys", 20.0),
            (3, "books", 15.0),
        }, f"Unexpected version 0 rows: {original_rows}"

        print("\nPASS: Delta write, read, partition overwrite, and time travel.")

        # A simple read-timing measurement.
        start = time.perf_counter()
        row_count = spark.read.format("delta").load(str(TABLE_PATH)).count()
        elapsed = time.perf_counter() - start

        print(f"Read/count rows: {row_count}")
        print(f"Read + count elapsed: {elapsed:.4f} seconds")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
