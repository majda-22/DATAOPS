from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from dataops.contracts.models import DatasetContract
from dataops.quality.engine import _build_checks


def evaluate_spark(
    df: DataFrame,
    contract: DatasetContract,
    *,
    source: str = "spark_dataframe",
    reference_data: Mapping[str, DataFrame] | None = None,
    run_id: UUID | str | None = None,
) -> dict:
    """Evaluate a Spark DataFrame using existing dataset contracts."""

    checks = _build_checks(contract)

    # Foreign-key checks require reference DataFrames.
    # Reject them explicitly until Spark join support is added.
    supported = {
        "not_null",
        "unique",
        "accepted_values",
        "min_row_count",
        "foreign_key",
    }
    for check in checks:
        if check["rule_type"] not in supported:
            raise ValueError(f"Unsupported Spark quality rule: {check['rule_type']}")

    required = {column.name for column in contract.columns}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing contract columns: {sorted(missing)}")

    if len(df.columns) != len(set(df.columns)):
        raise ValueError("Spark DataFrame contains duplicate column names")

    run_id = str(UUID(str(run_id))) if run_id is not None else str(uuid4())
    started_at = datetime.now(UTC)
    row_count = df.count()

    results = []

    for check in checks:
        rule_type = check["rule_type"]
        rule_id = check["rule_id"]
        failed_rows = 0
        examples = []
        failed_check = False

        if rule_type == "not_null":
            column = check["column"]
            if column is None:
                raise ValueError(f"Missing column for rule {rule_id}")

            value = F.col(column).cast("string")

            invalid = df.filter(value.isNull() | (F.trim(value) == ""))

            failed_rows = invalid.count()
            examples = [{"value": row[column]} for row in invalid.select(column).limit(5).collect()]

        elif rule_type == "unique":
            columns = check["columns"]

            # Match CSV semantics: null/blank key components
            # are handled by separate not-null checks.
            valid = df
            for column in columns:
                value = F.col(column).cast("string")
                valid = valid.filter(value.isNotNull() & (F.trim(value) != ""))

            normalized = valid.select(
                *[F.trim(F.col(column).cast("string")).alias(column) for column in columns]
            )

            duplicates = normalized.groupBy(*columns).count().filter(F.col("count") > 1)

            duplicate_count = duplicates.agg(F.sum(F.col("count") - 1).alias("failed")).first()

            failed_rows = int(duplicate_count["failed"] or 0) if duplicate_count is not None else 0

            examples = [
                {"key": {column: row[column] for column in columns}}
                for row in duplicates.limit(5).collect()
            ]

        elif rule_type == "accepted_values":
            column = check["column"]
            if column is None:
                raise ValueError(f"Missing column for rule {rule_id}")

            value = F.trim(F.col(column).cast("string"))

            invalid = df.filter(value.isNull() | ~value.isin(check["values"]))

            failed_rows = invalid.count()
            examples = [{"value": row[column]} for row in invalid.select(column).limit(5).collect()]

        elif rule_type == "min_row_count":
            minimum = check["min_rows"]
            failed_check = row_count < minimum

            if failed_check:
                examples = [
                    {
                        "minimum_rows": minimum,
                        "observed_rows": row_count,
                    }
                ]

        elif rule_type == "foreign_key":
            dataset = check["reference_dataset"]
            source_columns = check["columns"]
            reference_columns = check["reference_columns"]

            if reference_data is None or dataset not in reference_data:
                raise ValueError(f"Foreign-key validation requires reference data for {dataset}.")

            reference_df = reference_data[dataset]

            missing = set(reference_columns) - set(reference_df.columns)
            if missing:
                raise ValueError(
                    f"Reference dataset {dataset} is missing columns: {sorted(missing)}"
                )

            # Normalize both sides consistently with the CSV engine.
            source_keys = df.select(
                *[
                    F.trim(F.col(column).cast("string")).alias(f"key_{i}")
                    for i, column in enumerate(source_columns)
                ]
            )

            reference_keys = reference_df.select(
                *[
                    F.trim(F.col(column).cast("string")).alias(f"key_{i}")
                    for i, column in enumerate(reference_columns)
                ]
            )

            key_columns = [f"key_{i}" for i in range(len(source_columns))]

            # SQL MATCH SIMPLE: ignore incomplete foreign keys.
            for column in key_columns:
                source_keys = source_keys.filter(F.col(column).isNotNull() & (F.col(column) != ""))
                reference_keys = reference_keys.filter(
                    F.col(column).isNotNull() & (F.col(column) != "")
                )

            # Match CSV behavior: reference keys must be unique.
            duplicate_reference = (
                reference_keys.groupBy(*key_columns)
                .count()
                .filter(F.col("count") > 1)
                .limit(1)
                .collect()
            )

            if duplicate_reference:
                raise ValueError(f"Reference key is not unique in {dataset}")

            # Keep source keys that have no matching reference.
            orphan_keys = source_keys.join(
                reference_keys,
                on=key_columns,
                how="left_anti",
            )

            failed_rows = orphan_keys.count()

            examples = [
                {"key": {column: row[f"key_{i}"] for i, column in enumerate(source_columns)}}
                for row in orphan_keys.limit(5).collect()
            ]

        if rule_type != "min_row_count":
            failed_check = failed_rows > 0

        results.append(
            {
                "rule_id": rule_id,
                "rule_type": rule_type,
                "status": "FAIL" if failed_check else "PASS",
                "checked_rows": row_count,
                "failed_rows": failed_rows,
                "examples": examples,
            }
        )

    finished_at = datetime.now(UTC)

    return {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "dataset": contract.dataset,
        "contract_version": contract.version,
        "source_file": source,
        "row_count": row_count,
        "status": ("FAIL" if any(result["status"] == "FAIL" for result in results) else "PASS"),
        "results": results,
    }
