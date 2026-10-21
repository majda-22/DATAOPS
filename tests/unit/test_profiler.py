import csv

import pytest

from dataops.observability.profiler import profile_csv


def write_csv(tmp_path, rows):
    path = tmp_path / "sample.csv"

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["order_id", "order_status"],
        )
        writer.writeheader()
        writer.writerows(rows)

    return path


def test_profile_counts_rows_and_columns(tmp_path):
    path = write_csv(
        tmp_path,
        [
            {"order_id": "A001", "order_status": "delivered"},
            {"order_id": "A002", "order_status": "canceled"},
        ],
    )

    profile = profile_csv(path)

    assert profile["row_count"] == 2
    assert profile["columns"] == ["order_id", "order_status"]


def test_profile_detects_missing_values(tmp_path):
    path = write_csv(
        tmp_path,
        [
            {"order_id": "A001", "order_status": "delivered"},
            {"order_id": "A002", "order_status": ""},
            {"order_id": "A003", "order_status": "delivered"},
        ],
    )

    profile = profile_csv(path)

    status_metrics = profile["column_metrics"]["order_status"]

    assert status_metrics["missing_count"] == 1
    assert status_metrics["missing_rate"] == pytest.approx(1 / 3)
    assert status_metrics["distinct_count"] == 1


def test_profile_counts_distinct_non_empty_values(tmp_path):
    path = write_csv(
        tmp_path,
        [
            {"order_id": "A001", "order_status": "delivered"},
            {"order_id": "A002", "order_status": "delivered"},
            {"order_id": "A003", "order_status": "canceled"},
        ],
    )

    profile = profile_csv(path)

    assert profile["column_metrics"]["order_status"]["distinct_count"] == 2


def test_profile_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        profile_csv(tmp_path / "does_not_exist.csv")


def test_profile_rejects_empty_file_without_header(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="CSV has no header"):
        profile_csv(path)


def test_profile_supports_configured_dataset_metrics(tmp_path):
    path = tmp_path / "orders.csv"

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "order_id",
                "order_status",
                "order_purchase_timestamp",
            ],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "order_id": "A001",
                    "order_status": "delivered",
                    "order_purchase_timestamp": "2024-01-01 10:00:00",
                },
                {
                    "order_id": "A001",
                    "order_status": "canceled",
                    "order_purchase_timestamp": "not-a-time",
                },
                {
                    "order_id": "A003",
                    "order_status": "delivered",
                    "order_purchase_timestamp": "",
                },
            ]
        )

    profile = profile_csv(
        path,
        dataset="test_orders",
        timestamp_columns=("order_purchase_timestamp",),
        status_column="order_status",
        unique_column="order_id",
        timestamp_range_column="order_purchase_timestamp",
    )

    assert profile["row_count"] == 3
    assert profile["uniqueness"]["duplicate_rows_after_first_occurrence"] == 1
    assert profile["value_counts"]["order_status"] == {
        "canceled": 1,
        "delivered": 2,
    }
    assert profile["timestamp_checks"]["order_purchase_timestamp"] == {
        "blank_count": 1,
        "invalid_nonblank_count": 1,
    }
    assert profile["timestamp_ranges"]["order_purchase_timestamp"]["min"] == ("2024-01-01 10:00:00")
