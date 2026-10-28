import argparse
import json
import os
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from dataops.evaluation.history import (
    get_experiment_details,
    list_experiments,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect DataOps Detective evaluation experiments."
    )

    parser.add_argument(
        "--id",
        type=UUID,
        help="Show details for a specific experiment UUID.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of experiments to list.",
    )

    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    target = make_url(database_url)
    if target.database != "dataops_metadata":
        raise RuntimeError(f"Expected dataops_metadata; received {target.database}")

    engine = create_engine(database_url)

    try:
        with Session(engine) as session:
            if args.id is not None:
                result = get_experiment_details(session, args.id)
                if result is None:
                    raise SystemExit("Experiment not found")
            else:
                result = list_experiments(session, limit=args.limit)

        print(json.dumps(result, indent=2))

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
