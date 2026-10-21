from pathlib import Path

from dataops.contracts.loader import load_contract
from dataops.contracts.models import DatasetContract


def load_catalog(directory: str | Path) -> dict[str, DatasetContract]:
    contracts = [load_contract(path) for path in sorted(Path(directory).glob("*.yaml"))]
    catalog = {contract.dataset: contract for contract in contracts}
    if len(catalog) != len(contracts):
        raise ValueError("Dataset names in a contract catalog must be unique.")
    for contract in contracts:
        for key in contract.foreign_keys:
            if key.reference_dataset not in catalog:
                raise ValueError(f"Unknown reference dataset: {key.reference_dataset}")
            target = catalog[key.reference_dataset]
            target_columns = {column.name for column in target.columns}
            if set(key.reference_columns) - target_columns:
                raise ValueError(f"Unknown reference columns in foreign key {key.id}")
            candidate_keys = [set(target.primary_key)] + [
                set(rule.columns or []) for rule in target.quality_rules if rule.type == "unique"
            ]
            if set(key.reference_columns) not in candidate_keys:
                raise ValueError(f"Foreign key {key.id} must reference a declared unique key.")
    return catalog
