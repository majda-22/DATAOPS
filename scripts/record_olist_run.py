"""Record and verify a real Olist orders observation in PostgreSQL."""

import json
import os
from pathlib import Path

from sqlalchemy import create_engine

from dataops.observability.recording import record_csv_run, verify_recorded_run

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("Set DATABASE_URL or run make record-olist.")
    engine = create_engine(os.environ["DATABASE_URL"])
    evaluator = (
        create_engine(os.environ["EVALUATION_DATABASE_URL"])
        if os.getenv("EVALUATION_DATABASE_URL")
        else None
    )
    try:
        report = record_csv_run(
            engine,
            ROOT / "data/raw/olist/olist_orders_dataset.csv",
            ROOT / "configs/datasets/olist_orders.yaml",
            reference_data={"olist_customers": ROOT / "data/raw/olist/olist_customers_dataset.csv"},
        )
        report["verification"] = verify_recorded_run(engine, report["run_id"], evaluator=evaluator)
        destination = ROOT / "data/reports" / f"recorded_olist_{report['run_id']}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(
            json.dumps(
                {
                    "run_id": report["run_id"],
                    "status": report["status"],
                    "rows": report["row_count"],
                    "checks": len(report["quality_results"]),
                    "report": str(destination),
                },
                indent=2,
            )
        )
        if report["status"] != "success":
            raise SystemExit(1)
    finally:
        engine.dispose()
        if evaluator is not None:
            evaluator.dispose()


if __name__ == "__main__":
    main()
