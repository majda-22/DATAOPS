import csv

import pytest

from dataops.contracts.models import DatasetContract
from dataops.quality.engine import evaluate_csv
from dataops.quality.status import pipeline_status, quality_status
from tests.unit.test_quality_engine import make_contract, write_csv


def test_generated_rule_id_collision_preserves_both_checks(tmp_path):
    raw = make_contract().model_dump()
    raw["quality_rules"] = [
        {
            "id": "auto_not_null_order_id",
            "type": "accepted_values",
            "column": "order_status",
            "values": ["delivered"],
        }
    ]
    path = write_csv(tmp_path, [{"order_id": "", "order_status": "delivered"}])
    report = evaluate_csv(path, DatasetContract.model_validate(raw))
    results = {result["rule_id"]: result for result in report["results"]}
    assert results["auto_not_null_order_id"]["status"] == "PASS"
    assert results["auto_not_null_order_id__2"]["status"] == "FAIL"
    assert report["status"] == "FAIL"


def test_duplicate_csv_headers_are_rejected(tmp_path):
    path = tmp_path / "duplicate.csv"
    path.write_text("order_id,order_status,order_id\nA,delivered,B\n")
    with pytest.raises(ValueError, match="duplicate column"):
        evaluate_csv(path, make_contract())


@pytest.mark.parametrize("data_format", ["parquet", "delta"])
def test_csv_engine_does_not_pretend_to_support_other_backends(tmp_path, data_format):
    raw = make_contract().model_dump()
    raw["format"] = data_format
    path = write_csv(tmp_path, [{"order_id": "A", "order_status": "delivered"}])
    with pytest.raises(ValueError, match="requires a csv contract"):
        evaluate_csv(path, DatasetContract.model_validate(raw))


@pytest.mark.parametrize(
    "rows,minimum,status", [(0, 1, "FAIL"), (0, 0, "PASS"), (1, 2, "FAIL"), (1, 1, "PASS")]
)
def test_minimum_volume_includes_empty_datasets(tmp_path, rows, minimum, status):
    raw = make_contract().model_dump()
    raw["quality_rules"].append({"id": "volume", "type": "min_row_count", "min_rows": minimum})
    path = write_csv(tmp_path, [{"order_id": "A", "order_status": "delivered"}] * rows)
    report = evaluate_csv(path, DatasetContract.model_validate(raw))
    assert report["status"] == status
    result = next(r for r in report["results"] if r["rule_id"] == "volume")
    assert result["status"] == status
    assert result["failed_rows"] == 0  # A volume failure does not invent row-level failures.


def test_foreign_key_detects_orphans_and_requires_reference_data(tmp_path):
    raw = make_contract().model_dump()
    raw["foreign_keys"] = [
        {
            "id": "parent_fk",
            "columns": ["order_id"],
            "reference_dataset": "parent",
            "reference_columns": ["id"],
        }
    ]
    contract = DatasetContract.model_validate(raw)
    path = write_csv(tmp_path, [{"order_id": "missing", "order_status": "delivered"}])
    with pytest.raises(ValueError, match="requires reference data"):
        evaluate_csv(path, contract)
    parent = tmp_path / "parent.csv"
    parent.write_text("id\nexisting\n")
    report = evaluate_csv(path, contract, reference_data={"parent": parent})
    result = next(r for r in report["results"] if r["rule_id"] == "parent_fk")
    assert result["failed_rows"] == 1 and report["status"] == "FAIL"
    parent.write_text("id\nmissing\n")
    assert evaluate_csv(path, contract, reference_data={"parent": parent})["status"] == "PASS"
    parent.write_text("id\nmissing\nmissing\n")
    with pytest.raises(ValueError, match="not unique"):
        evaluate_csv(path, contract, reference_data={"parent": parent})


def test_composite_foreign_key_and_null_semantics(tmp_path):
    raw = make_contract().model_dump()
    raw["columns"][0]["nullable"] = True
    raw["primary_key"] = ["order_status"]
    raw["quality_rules"] = []
    raw["foreign_keys"] = [
        {
            "id": "pair_fk",
            "columns": ["order_id", "order_status"],
            "reference_dataset": "parent",
            "reference_columns": ["a", "b"],
        }
    ]
    contract = DatasetContract.model_validate(raw)
    path = write_csv(
        tmp_path,
        [
            {"order_id": "", "order_status": "pending"},
            {"order_id": "A", "order_status": "delivered"},
        ],
    )
    parent = tmp_path / "parent.csv"
    with parent.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerows([["a", "b"], ["A", "delivered"]])
    assert evaluate_csv(path, contract, reference_data={"parent": parent})["status"] == "PASS"


def test_status_translation_is_explicit_and_rejects_unknown_values():
    assert quality_status("PASS") == "passed"
    assert quality_status("FAIL") == "failed"
    assert pipeline_status("PASS") == "success"
    assert pipeline_status("FAIL") == "failed"
    with pytest.raises(KeyError):
        quality_status("unknown")
