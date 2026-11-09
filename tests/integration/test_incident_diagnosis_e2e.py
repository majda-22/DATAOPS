from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from dataops.db.models import Incident
from dataops.diagnosis.graph import build_diagnosis_graph
from dataops.diagnosis.loader import (
    make_incident_evidence_loader,
    make_incident_loader,
    make_pipeline_run_loader,
)
from dataops.observability.quality_store import persist_quality_report


def test_failed_quality_report_can_be_diagnosed(pg_engine):
    run_id = uuid4()
    started_at = datetime.now(UTC)

    # 1. Simulate a failed quality validation.
    report = {
        "run_id": str(run_id),
        "started_at": started_at.isoformat(),
        "finished_at": (started_at + timedelta(seconds=10)).isoformat(),
        "row_count": 100,
        "status": "FAIL",
        "dataset": "olist_orders",
        "contract_version": 1,
        "source_file": "test.csv",
        "results": [
            {
                "rule_id": "order_id_unique",
                "rule_type": "unique",
                "status": "FAIL",
                "failed_rows": 5,
                "checked_rows": 100,
                "examples": [],
            }
        ],
    }

    # 2. Persist the pipeline run and incident.
    with Session(pg_engine) as session:
        persist_quality_report(
            session,
            report,
            pipeline_name="olist_bronze_quality",
        )

    # 3. Retrieve the created incident.
    with Session(pg_engine) as session:
        incident = session.scalar(select(Incident).where(Incident.pipeline_run_id == run_id))

        assert incident is not None
        incident_id = incident.id

    # 4. Ensure experiment evidence is never accessed.
    def forbidden_experiment_loader(experiment_id, scenario_name):
        raise AssertionError("Incident diagnosis must not access experiment evidence")

    # 5. Build LangGraph using PostgreSQL loaders.
    graph = build_diagnosis_graph(
        forbidden_experiment_loader,
        load_pipeline_run=make_pipeline_run_loader(pg_engine),
        load_incident=make_incident_loader(pg_engine),
        load_incident_evidence=make_incident_evidence_loader(pg_engine),
    )

    # 6. Diagnose using only the incident ID.
    result = graph.invoke({"incident_id": incident_id})

    # 7. Verify the diagnosis.
    assert result["incident"]["incident_id"] == incident_id
    assert result["pipeline_run_id"] == str(run_id)
    assert result["pipeline_run"] is not None

    assert result["diagnosis"]["status"] == "failure_detected"

    assert result["diagnosis"]["suspected_rules"] == ["order_id_unique"]

    assert result["evidence"]["failed_rules"] == ["order_id_unique"]

    assert "ground_truth" not in result["evidence"]
