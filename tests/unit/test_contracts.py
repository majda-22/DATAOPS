
from pathlib import Path

import pytest
from pydantic import ValidationError

from dataops.contracts.loader import load_contract
from dataops.contracts.models import DatasetContract

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    PROJECT_ROOT / "configs" / "datasets" / "olist_orders.yaml"
)


def test_olist_contract_loads():
    contract = load_contract(CONTRACT_PATH)

    assert contract.dataset == "olist_orders"
    assert contract.layer == "bronze"
    assert contract.format == "csv"


def test_olist_contract_has_expected_columns():
    contract = load_contract(CONTRACT_PATH)

    column_names = [column.name for column in contract.columns]

    assert "order_id" in column_names
    assert "customer_id" in column_names
    assert "order_status" in column_names
    assert "order_purchase_timestamp" in column_names


def test_contract_rejects_unknown_primary_key_column():
    contract = load_contract(CONTRACT_PATH)
    raw_contract = contract.model_dump()
    raw_contract["primary_key"] = ["column_that_does_not_exist"]

    with pytest.raises(ValidationError):
        DatasetContract.model_validate(raw_contract)


def test_contract_rejects_not_null_rule_without_column():
    contract = load_contract(CONTRACT_PATH)
    raw_contract = contract.model_dump()

    not_null_rule = next(
        rule
        for rule in raw_contract["quality_rules"]
        if rule["type"] == "not_null"
    )
    not_null_rule["column"] = None

    with pytest.raises(ValidationError):
        DatasetContract.model_validate(raw_contract)


def test_contract_rejects_duplicate_column_names():
    contract = load_contract(CONTRACT_PATH)
    raw_contract = contract.model_dump()
    raw_contract["columns"].append(raw_contract["columns"][0].copy())

    with pytest.raises(ValidationError):
        DatasetContract.model_validate(raw_contract)
