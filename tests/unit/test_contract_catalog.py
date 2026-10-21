from pathlib import Path

import pytest
from pydantic import ValidationError

from dataops.contracts.catalog import load_catalog
from dataops.contracts.models import DatasetContract, ForeignKeyContract

ROOT = Path(__file__).resolve().parents[2]


def test_all_olist_and_uci_contracts_resolve_their_foreign_keys():
    catalog = load_catalog(ROOT / "configs/datasets")
    assert set(catalog) == {
        "olist_orders",
        "olist_customers",
        "olist_order_items",
        "olist_order_payments",
        "olist_order_reviews",
        "olist_products",
        "olist_sellers",
        "uci_online_retail",
    }
    assert catalog["olist_order_reviews"].primary_key == ["review_id", "order_id"]
    assert catalog["uci_online_retail"].primary_key == []
    assert catalog["uci_online_retail"].keyless_reason
    assert all(
        any(rule.type == "min_row_count" for rule in c.quality_rules) for c in catalog.values()
    )


def test_keyless_source_requires_an_explanation():
    contract = load_catalog(ROOT / "configs/datasets")["uci_online_retail"].model_dump()
    contract["keyless_reason"] = None
    with pytest.raises(ValidationError, match="keyless_reason"):
        DatasetContract.model_validate(contract)


def test_foreign_key_arity_is_validated():
    with pytest.raises(ValidationError, match="counts must match"):
        ForeignKeyContract(
            id="fk", columns=["a", "b"], reference_dataset="parent", reference_columns=["a"]
        )
