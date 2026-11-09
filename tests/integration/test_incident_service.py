from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from dataops.db.models import Incident, PipelineRun
from dataops.diagnosis.incident_repository import get_incident_quality_evidence
from dataops.diagnosis.incident_service import (
    create_incident_from_quality_report,
)


def test_failed_quality_report_creates_incident(pg_engine):
    run_id = uuid4()

    report = {
        "status": "FAIL",
        "results": [
            {
                "rule_id": "order_id_unique",
                "rule_type": "unique",
                "status": "FAIL",
                "failed_rows": 5,
                "checked_rows": 100,
            },
        ],
    }

    with Session(pg_engine) as session:
        with session.begin():
            session.add(
                PipelineRun(
                    id=run_id,
                    pipeline_name="test_quality_pipeline",
                    status="failed",
                    started_at=datetime.now(UTC),
                )
            )

            session.flush()

            incident_id = create_incident_from_quality_report(
                session,
                run_id,
                report,
            )
            evidence = get_incident_quality_evidence(
                session,
                incident_id,
            )

            assert evidence == {
                "status": "FAIL",
                "failed_rules": ["order_id_unique"],
                "failed_checks": [
                    {
                        "rule_id": "order_id_unique",
                        "rule_type": "unique",
                        "failed_rows": 5,
                        "checked_rows": 100,
                    }
                ],
            }

            assert incident_id is not None

            incident = session.get(Incident, incident_id)

            assert incident is not None
            assert incident.pipeline_run_id == run_id
            assert incident.status == "open"
            assert incident.evidence["failed_rules"] == ["order_id_unique"]
