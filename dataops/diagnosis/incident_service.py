from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from dataops.db.models import Incident, PipelineRun


def create_incident_from_quality_report(
    session: Session,
    pipeline_run_id: UUID,
    report: Mapping[str, Any],
) -> int | None:
    """Create an incident when a pipeline quality report fails."""

    if session.get(PipelineRun, pipeline_run_id) is None:
        raise ValueError("Pipeline run does not exist")

    status = report.get("status")

    if status == "PASS":
        return None

    if status != "FAIL":
        raise ValueError("Invalid quality report status")

    results = report.get("results")

    if not isinstance(results, list):
        raise ValueError("Invalid quality report results")

    failed_checks: list[dict[str, str | int]] = []

    for result in results:
        if not isinstance(result, dict):
            raise ValueError("Invalid quality check result")

        if result.get("status") != "FAIL":
            continue

        rule_id = result.get("rule_id")
        rule_type = result.get("rule_type")
        failed_rows = result.get("failed_rows")
        checked_rows = result.get("checked_rows")

        if (
            not isinstance(rule_id, str)
            or not rule_id
            or not isinstance(rule_type, str)
            or not rule_type
            or type(failed_rows) is not int
            or type(checked_rows) is not int
            or failed_rows < 0
            or checked_rows <= 0
            or failed_rows > checked_rows
        ):
            raise ValueError("Invalid failed quality check")

        failed_checks.append(
            {
                "rule_id": rule_id,
                "rule_type": rule_type,
                "failed_rows": failed_rows,
                "checked_rows": checked_rows,
            }
        )

    failed_rules: list[str] = [str(check["rule_id"]) for check in failed_checks]
    if not failed_rules:
        raise ValueError("Failed report contains no failed rules")

    incident = Incident(
        pipeline_run_id=pipeline_run_id,
        title="Data quality failure: " + ", ".join(failed_rules),
        severity="high",
        status="open",
        evidence={
            "status": "FAIL",
            "failed_rules": failed_rules,
            "failed_checks": failed_checks,
        },
    )

    session.add(incident)
    session.flush()

    return incident.id
