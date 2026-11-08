import argparse
import json
import os
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from dataops.diagnosis.graph import build_diagnosis_graph
from dataops.diagnosis.loader import make_evidence_loader, make_pipeline_run_loader


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose an experiment scenario using LangGraph.")
    parser.add_argument("--experiment-id", type=UUID, required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument(
        "--pipeline-run-id",
        type=UUID,
        default=None,
        help="Explicitly associated pipeline execution UUID",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    target = make_url(database_url)

    if target.database != "dataops_metadata":
        raise RuntimeError("Expected the dataops_metadata database")

    engine = create_engine(database_url)

    try:
        graph = build_diagnosis_graph(
            make_evidence_loader(engine), load_pipeline_run=make_pipeline_run_loader(engine)
        )

        result = graph.invoke(
            {
                "experiment_id": str(args.experiment_id),
                "scenario_name": args.scenario,
                "pipeline_run_id": str(args.pipeline_run_id)
                if args.pipeline_run_id is not None
                else None,
            }
        )

        print(
            json.dumps(
                {
                    "diagnosis": result["diagnosis"],
                    "findings": result.get("findings", []),
                    "pipeline_run": result.get("pipeline_run"),
                },
                indent=2,
            )
        )

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
