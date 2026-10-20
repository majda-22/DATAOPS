
import csv
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def profile_csv(
    csv_path: str | Path,
    *,
    dataset: str | None = None,
    timestamp_columns: tuple[str, ...] = (),
    status_column: str | None = None,
    unique_column: str | None = None,
    timestamp_range_column: str | None = None,
) -> dict:
    """Profile a CSV and optionally calculate dataset-specific metrics."""

    csv_path = Path(csv_path)

    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    started_at = datetime.now(UTC)

    row_count = 0
    missing_counts = Counter()
    distinct_values = {}
    status_counts = Counter()
    timestamp_blank_counts = Counter()
    timestamp_invalid_counts = Counter()

    seen_unique_values = set()
    repeated_unique_values = set()
    duplicate_rows = 0

    timestamp_min = None
    timestamp_max = None

    with csv_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {csv_path}")

        columns = reader.fieldnames

        if len(columns) != len(set(columns)):
            raise ValueError(
                f"CSV contains duplicate column names: {csv_path}"
            )

        configured_columns = set(timestamp_columns)

        if status_column:
            configured_columns.add(status_column)

        if unique_column:
            configured_columns.add(unique_column)

        if timestamp_range_column:
            configured_columns.add(timestamp_range_column)

        missing_columns = configured_columns - set(columns)

        if missing_columns:
            raise ValueError(
                f"CSV is missing configured columns: "
                f"{sorted(missing_columns)}"
            )

        distinct_values = {column: set() for column in columns}

        for row in reader:
            row_count += 1

            for column in columns:
                value = row.get(column)

                if value is None or not value.strip():
                    missing_counts[column] += 1
                else:
                    distinct_values[column].add(value)

            if status_column:
                status = (row.get(status_column) or "").strip()
                if status:
                    status_counts[status] += 1

            if unique_column:
                value = (row.get(unique_column) or "").strip()

                if value:
                    if value in seen_unique_values:
                        duplicate_rows += 1
                        repeated_unique_values.add(value)
                    else:
                        seen_unique_values.add(value)

            for column in timestamp_columns:
                value = (row.get(column) or "").strip()

                if not value:
                    timestamp_blank_counts[column] += 1
                    continue

                try:
                    parsed = datetime.fromisoformat(value)
                except ValueError:
                    timestamp_invalid_counts[column] += 1
                    continue

                if column == timestamp_range_column:
                    if timestamp_min is None or parsed < timestamp_min:
                        timestamp_min = parsed

                    if timestamp_max is None or parsed > timestamp_max:
                        timestamp_max = parsed

    column_metrics = {}

    for column in columns:
        missing_count = missing_counts[column]

        column_metrics[column] = {
            "missing_count": missing_count,
            "missing_rate": round(
                missing_count / row_count if row_count else 0.0,
                6,
            ),
            "distinct_count": len(distinct_values[column]),
        }

    report = {
        "dataset": dataset or csv_path.stem,
        "profiled_at": started_at.isoformat(),
        "source_file": csv_path.name,
        "row_count": row_count,
        "columns": columns,
        "missing_values": {
            column: missing_counts[column] for column in columns
        },
        "column_metrics": column_metrics,
    }

    if unique_column:
        report["uniqueness"] = {
            "column": unique_column,
            "non_empty_distinct_count": len(seen_unique_values),
            "duplicate_rows_after_first_occurrence": duplicate_rows,
            "distinct_values_that_repeat": len(repeated_unique_values),
        }

    if status_column:
        report["value_counts"] = {
            status_column: dict(sorted(status_counts.items()))
        }

    if timestamp_columns:
        report["timestamp_checks"] = {
            column: {
                "blank_count": timestamp_blank_counts[column],
                "invalid_nonblank_count": timestamp_invalid_counts[column],
            }
            for column in timestamp_columns
        }

    if timestamp_range_column:
        report["timestamp_ranges"] = {
            timestamp_range_column: {
                "min": timestamp_min.isoformat(sep=" ")
                if timestamp_min else None,
                "max": timestamp_max.isoformat(sep=" ")
                if timestamp_max else None,
            }
        }

    return report
