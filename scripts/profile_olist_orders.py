
import json
from pathlib import Path

from dataops.observability.profiler import profile_csv

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "olist"
    / "olist_orders_dataset.csv"
)

REPORT_DIR = PROJECT_ROOT / "data" / "reports"
REPORT_FILE = REPORT_DIR / "olist_orders_profile.json"

TIMESTAMP_COLUMNS = (
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
)


def profile_orders() -> dict:
    profile = profile_csv(
        DATA_FILE,
        dataset="olist_orders",
        timestamp_columns=TIMESTAMP_COLUMNS,
        status_column="order_status",
        unique_column="order_id",
        timestamp_range_column="order_purchase_timestamp",
    )

    # Preserve the original report fields while adding reusable metrics.
    uniqueness = profile["uniqueness"]
    timestamp_range = profile["timestamp_ranges"][
        "order_purchase_timestamp"
    ]

    return {
        "dataset": profile["dataset"],
        "profiled_at": profile["profiled_at"],
        "source_file": profile["source_file"],
        "row_count": profile["row_count"],
        "columns": profile["columns"],
        "missing_values": profile["missing_values"],
        "column_metrics": profile["column_metrics"],
        "order_id": {
            "non_empty_distinct_count": (
                uniqueness["non_empty_distinct_count"]
            ),
            "duplicate_rows_after_first_occurrence": (
                uniqueness["duplicate_rows_after_first_occurrence"]
            ),
            "distinct_ids_that_repeat": (
                uniqueness["distinct_values_that_repeat"]
            ),
        },
        "order_status_counts": profile["value_counts"]["order_status"],
        "timestamp_checks": profile["timestamp_checks"],
        "purchase_timestamp_range": timestamp_range,
    }


def main() -> None:
    report = profile_orders()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    REPORT_FILE.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nReport saved to: {REPORT_FILE}")


if __name__ == "__main__":
    main()
