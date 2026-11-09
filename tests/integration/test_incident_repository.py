from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from dataops.db.models import Incident, PipelineRun
from dataops.diagnosis.incident_repository import get_incident


def test_get_incident_returns_pipeline_association(pg_engine):
    run_id = uuid4()

    with Session(pg_engine) as session:
        with session.begin():
            session.add(
                PipelineRun(
                    id=run_id,
                    pipeline_name="test_incident_pipeline",
                    status="failed",
                    started_at=datetime.now(UTC),
                )
            )
            session.flush()

            incident = Incident(
                pipeline_run_id=run_id,
                title="Order quality failure",
                severity="high",
                status="open",
            )
            session.add(incident)
            session.flush()
            incident_id = incident.id

        result = get_incident(session, incident_id)

        assert result is not None
        assert result["pipeline_run_id"] == str(run_id)
        assert result["title"] == "Order quality failure"
        assert result["severity"] == "high"
        assert "diagnosis" not in result
        assert "evidence" not in result


def test_get_incident_returns_none_when_missing(pg_engine):
    with Session(pg_engine) as session:
        assert get_incident(session, 2_147_483_647) is None
