import json
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from dataops.observability.quality_store import persist_quality_report

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

REPORT_PATH = ROOT / "data/reports/olist_spark_quality.json"


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    engine = create_engine(database_url)

    try:
        with Session(engine) as session:
            run_id = persist_quality_report(session, report)

        print("Quality report persisted successfully")
        print(f"Pipeline run ID: {run_id}")
        print(f"Dataset: {report['dataset']}")
        print(f"Quality checks: {len(report['results'])}")
        print(f"Status: {report['status']}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
