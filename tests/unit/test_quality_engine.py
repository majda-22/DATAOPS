
import csv

from dataops.contracts.models import DatasetContract
from dataops.quality.engine import evaluate_csv


def make_contract() -> DatasetContract:
    return DatasetContract.model_validate(
        {
            "dataset": "test_orders",
            "version": 1,
            "description": "Synthetic dataset for quality-engine tests",
            "layer": "bronze",
            "format": "csv",
            "columns": [
                {
                    "name": "order_id",
                    "logical_type": "string",
                    "nullable": False,
                },
                {
                    "name": "order_status",
                    "logical_type": "string",
                    "nullable": False,
                },
            ],
            "primary_key": ["order_id"],
            "quality_rules": [
                {
                    "id": "order_id_not_null",
                    "type": "not_null",
                    "column": "order_id",
                },
                {
                    "id": "order_id_unique",
                    "type": "unique",
                    "columns": ["order_id"],
                },
                {
                    "id": "order_status_allowed",
                    "type": "accepted_values",
                    "column": "order_status",
                    "values": ["delivered", "canceled"],
                },
            ],
        }
    )


def write_csv(tmp_path, rows):
    path = tmp_path / "test_orders.csv"

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["order_id", "order_status"],
        )
        writer.writeheader()
        writer.writerows(rows)

    return path


def test_clean_data_passes_all_rules(tmp_path):
    path = write_csv(
        tmp_path,
        [
            {"order_id": "A001", "order_status": "delivered"},
            {"order_id": "A002", "order_status": "canceled"},
        ],
    )

    report = evaluate_csv(path, make_contract())

    assert all(result["status"] == "PASS" for result in report["results"])


def test_missing_order_id_fails_not_null(tmp_path):
    path = write_csv(
        tmp_path,
        [
            {"order_id": "", "order_status": "delivered"},
        ],
    )

    report = evaluate_csv(path, make_contract())
    results = {result["rule_id"]: result for result in report["results"]}

    assert results["order_id_not_null"]["status"] == "FAIL"
    assert results["order_id_not_null"]["failed_rows"] == 1


def test_duplicate_order_id_fails_unique(tmp_path):
    path = write_csv(
        tmp_path,
        [
            {"order_id": "A001", "order_status": "delivered"},
            {"order_id": "A001", "order_status": "canceled"},
        ],
    )

    report = evaluate_csv(path, make_contract())
    results = {result["rule_id"]: result for result in report["results"]}

    assert results["order_id_unique"]["status"] == "FAIL"
    assert results["order_id_unique"]["failed_rows"] == 1


def test_unexpected_status_fails_accepted_values(tmp_path):
    path = write_csv(
        tmp_path,
        [
            {"order_id": "A001", "order_status": "in_transit"},
        ],
    )

    report = evaluate_csv(path, make_contract())
    results = {result["rule_id"]: result for result in report["results"]}

    assert results["order_status_allowed"]["status"] == "FAIL"
    assert results["order_status_allowed"]["failed_rows"] == 1


def test_missing_required_column_raises_error(tmp_path):
    path = tmp_path / "missing_column.csv"

    # The contract requires both order_id and order_status.
    # This CSV contains only order_id.
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["order_id"])
        writer.writeheader()
        writer.writerow({"order_id": "A001"})

    # The engine should reject the file before checking its rows.
    import pytest

    with pytest.raises(ValueError, match="CSV is missing contract columns"):
        evaluate_csv(path, make_contract())


def test_blank_order_status_fails_accepted_values(tmp_path):
    path = write_csv(
        tmp_path,
        [
            {"order_id": "A001", "order_status": ""},
        ],
    )

    report = evaluate_csv(path, make_contract())
    results = {result["rule_id"]: result for result in report["results"]}

    assert results["order_status_allowed"]["status"] == "FAIL"
    assert results["order_status_allowed"]["failed_rows"] == 1

