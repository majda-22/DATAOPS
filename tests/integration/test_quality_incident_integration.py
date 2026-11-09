from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from dataops.db.models import Incident, PipelineRun, QualityResult
from dataops.observability.quality_store import persist_quality_report


@pytest.mark.parametrize(
    ("status", "expected_incidents"),
    [
        ("FAIL", 1),
        ("PASS", 0),
    ],
)
def test_quality_report_creates_incident_only_on_failure(
    pg_engine,
    status,
    expected_incidents,
):
    run_id = uuid4()
    started_at = datetime.now(UTC)

    report = {
        "run_id": str(run_id),
        "started_at": started_at.isoformat(),
        "finished_at": (started_at + timedelta(seconds=10)).isoformat(),
        "row_count": 100,
        "status": status,
        "dataset": "olist_orders",
        "contract_version": 1,
        "source_file": "test.csv",
        "results": [
            {
                "rule_id": "order_id_unique",
                "rule_type": "unique",
                "status": status,
                "failed_rows": 1 if status == "FAIL" else 0,
                "checked_rows": 100,
                "examples": [],
            }
        ],
    }

    # Execute twice to verify sequential retry behavior.
    with Session(pg_engine) as session:
        first_id = persist_quality_report(session, report)
        second_id = persist_quality_report(session, report)

        assert first_id == second_id == run_id

        runs = session.scalars(select(PipelineRun).where(PipelineRun.id == run_id)).all()

        checks = session.scalars(
            select(QualityResult).where(QualityResult.pipeline_run_id == run_id)
        ).all()

        incidents = session.scalars(
            select(Incident).where(Incident.pipeline_run_id == run_id)
        ).all()

        assert len(runs) == 1
        assert len(checks) == 1
        assert len(incidents) == expected_incidents

        if status == "FAIL":
            assert incidents[0].status == "open"
            assert incidents[0].evidence["failed_rules"] == ["order_id_unique"]
