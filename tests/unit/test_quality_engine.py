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


def make_automatic_contract() -> DatasetContract:
    return DatasetContract.model_validate(
        {
            "dataset": "test_composite",
            "version": 1,
            "description": "Test automatic integrity checks",
            "layer": "bronze",
            "format": "csv",
            "columns": [
                {"name": "order_id", "logical_type": "string", "nullable": False},
                {"name": "product_id", "logical_type": "string", "nullable": False},
                {"name": "quantity", "logical_type": "integer", "nullable": True},
            ],
            "primary_key": ["order_id", "product_id"],
            "quality_rules": [],
        }
    )


def write_composite_csv(tmp_path, rows):
    path = tmp_path / "composite.csv"
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["order_id", "product_id", "quantity"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_automatic_not_null_check_for_non_nullable_column(tmp_path):
    path = write_composite_csv(
        tmp_path,
        [{"order_id": "", "product_id": "P1", "quantity": "2"}],
    )

    report = evaluate_csv(path, make_automatic_contract())
    results = {result["rule_id"]: result for result in report["results"]}

    assert results["auto_not_null_order_id"]["status"] == "FAIL"
    assert results["auto_not_null_order_id"]["failed_rows"] == 1


def test_automatic_primary_key_detects_duplicate_composite_key(tmp_path):
    path = write_composite_csv(
        tmp_path,
        [
            {"order_id": "A1", "product_id": "P1", "quantity": "2"},
            {"order_id": "A1", "product_id": "P1", "quantity": "3"},
        ],
    )

    report = evaluate_csv(path, make_automatic_contract())
    results = {result["rule_id"]: result for result in report["results"]}

    assert results["auto_primary_key_unique"]["status"] == "FAIL"
    assert results["auto_primary_key_unique"]["failed_rows"] == 1


def test_automatic_checks_pass_for_valid_data(tmp_path):
    path = write_composite_csv(
        tmp_path,
        [
            {"order_id": "A1", "product_id": "P1", "quantity": "2"},
            {"order_id": "A1", "product_id": "P2", "quantity": "3"},
        ],
    )

    report = evaluate_csv(path, make_automatic_contract())

    assert report["status"] == "PASS"
    assert all(result["status"] == "PASS" for result in report["results"])


def test_explicit_primary_key_rules_are_not_duplicated():
    contract = make_contract()

    from dataops.quality.engine import _build_checks

    checks = _build_checks(contract)
    check_ids = [check["rule_id"] for check in checks]

    assert check_ids.count("order_id_not_null") == 1
    assert check_ids.count("order_id_unique") == 1
    assert "auto_not_null_order_id" not in check_ids
    assert "auto_primary_key_unique" not in check_ids
