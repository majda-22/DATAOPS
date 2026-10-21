import json
from pathlib import Path

from dataops.contracts.loader import load_contract
from dataops.quality.engine import evaluate_csv

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONTRACT_PATH = PROJECT_ROOT / "configs" / "datasets" / "olist_orders.yaml"

DATA_PATH = PROJECT_ROOT / "data" / "raw" / "olist" / "olist_orders_dataset.csv"

REPORT_PATH = PROJECT_ROOT / "data" / "reports" / "olist_orders_quality.json"


def main() -> None:
    contract = load_contract(CONTRACT_PATH)
    report = evaluate_csv(DATA_PATH, contract)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nReport saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
