from sqlalchemy import select
from sqlalchemy.orm import Session

from dataops.db.models import Incident


def get_incident(
    session: Session,
    incident_id: int,
) -> dict | None:
    """Retrieve observable incident information."""

    if incident_id < 1:
        raise ValueError("Incident ID must be positive")

    statement = select(
        Incident.id,
        Incident.pipeline_run_id,
        Incident.title,
        Incident.severity,
        Incident.status,
        Incident.created_at,
    ).where(Incident.id == incident_id)

    row = session.execute(statement).one_or_none()

    if row is None:
        return None

    return {
        "incident_id": row.id,
        "pipeline_run_id": (str(row.pipeline_run_id) if row.pipeline_run_id is not None else None),
        "title": row.title,
        "severity": row.severity,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
    }


def get_incident_quality_evidence(
    session: Session,
    incident_id: int,
) -> dict | None:
    """Retrieve only approved incident quality evidence."""

    if incident_id < 1:
        raise ValueError("Incident ID must be positive")

    statement = select(Incident.evidence).where(Incident.id == incident_id)

    evidence = session.scalar(statement)

    if evidence is None:
        return None

    if not isinstance(evidence, dict):
        raise ValueError("Invalid incident evidence")

    status = evidence.get("status")
    failed_rules = evidence.get("failed_rules")

    if status not in {"PASS", "FAIL"}:
        raise ValueError("Invalid incident quality status")

    if not isinstance(failed_rules, list) or not all(
        isinstance(rule, str) and rule for rule in failed_rules
    ):
        raise ValueError("Invalid failed rules")

    raw_checks = evidence.get("failed_checks", [])

    if not isinstance(raw_checks, list):
        raise ValueError("Invalid incident failed checks")

    failed_checks = []

    for check in raw_checks:
        if not isinstance(check, dict):
            raise ValueError("Invalid incident failed check")

        rule_id = check.get("rule_id")
        rule_type = check.get("rule_type")
        failed_rows = check.get("failed_rows")
        checked_rows = check.get("checked_rows")

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
            raise ValueError("Invalid incident failed check")

        failed_checks.append(
            {
                "rule_id": rule_id,
                "rule_type": rule_type,
                "failed_rows": failed_rows,
                "checked_rows": checked_rows,
            }
        )

    return {
        "status": status,
        "failed_rules": failed_rules,
        "failed_checks": failed_checks,
    }
