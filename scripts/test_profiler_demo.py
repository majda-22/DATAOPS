import csv
import json
from pathlib import Path

from dataops.observability.profiler import profile_csv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_FILE = PROJECT_ROOT / "data" / "reports" / "profiler_demo.csv"


def main():
    DEMO_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Create a tiny synthetic dataset with two columns.
    with DEMO_FILE.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["device_id", "temperature"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {"device_id": "D001", "temperature": "22.5"},
                {"device_id": "D002", "temperature": ""},
                {"device_id": "D003", "temperature": "23.1"},
                {"device_id": "D003", "temperature": "23.1"},
            ]
        )

    # Call the reusable profiler directly, without the Olist runner.
    report = profile_csv(DEMO_FILE, dataset="synthetic_telemetry")

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
