from pathlib import Path

import yaml

from dataops.contracts.models import DatasetContract


def load_contract(path: str | Path) -> DatasetContract:
    """Load a YAML dataset contract and validate its structure."""

    contract_path = Path(path)

    with contract_path.open("r", encoding="utf-8") as file:
        raw_contract = yaml.safe_load(file)

    if not isinstance(raw_contract, dict):
        raise TypeError(f"Expected a YAML mapping in contract file: {contract_path}")

    return DatasetContract.model_validate(raw_contract)
