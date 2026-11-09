import argparse
import json
import os
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from dataops.diagnosis.graph import build_diagnosis_graph
from dataops.diagnosis.loader import (
    make_evidence_loader,
    make_incident_evidence_loader,
    make_incident_loader,
    make_pipeline_run_loader,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose an experiment scenario using LangGraph.")
    parser.add_argument("--experiment-id", type=UUID)
    parser.add_argument("--scenario")
    parser.add_argument(
        "--pipeline-run-id",
        type=UUID,
        default=None,
        help="Explicitly associated pipeline execution UUID",
    )
    parser.add_argument(
        "--incident-id",
        type=int,
        default=None,
        help="Incident ID to load context from",
    )
    args = parser.parse_args()
    incident_mode = args.incident_id is not None
    experiment_mode = args.experiment_id is not None or args.scenario is not None
    if incident_mode == experiment_mode:
        parser.error("Must specify either --incident-id or both --experiment-id and --scenario")

    if not incident_mode and (args.experiment_id is None or args.scenario is None):
        parser.error(
            "Must specify both --experiment-id and --scenario when not using --incident-id"
        )

    if incident_mode and args.pipeline_run_id is not None:
        parser.error("Cannot specify --pipeline-run-id when using --incident-id")

    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    target = make_url(database_url)

    if target.database != "dataops_metadata":
        raise RuntimeError("Expected the dataops_metadata database")

    engine = create_engine(database_url)

    try:
        graph = build_diagnosis_graph(
            make_evidence_loader(engine),
            load_pipeline_run=make_pipeline_run_loader(engine),
            load_incident=make_incident_loader(engine),
            load_incident_evidence=make_incident_evidence_loader(engine),
        )

        state = (
            {"incident_id": args.incident_id}
            if incident_mode
            else {
                "experiment_id": str(args.experiment_id),
                "scenario_name": args.scenario,
                "pipeline_run_id": (
                    str(args.pipeline_run_id) if args.pipeline_run_id is not None else None
                ),
            }
        )

        result = graph.invoke(state)

        print(
            json.dumps(
                {
                    "diagnosis": result["diagnosis"],
                    "incident": result.get("incident"),
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
