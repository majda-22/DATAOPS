from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from dataops.db.models import EvaluationScenario


def get_scenario_evidence(
    session: Session,
    experiment_id: UUID,
    scenario_name: str,
) -> dict | None:
    """Retrieve observable evidence without evaluation answers."""

    statement = select(EvaluationScenario.evidence).where(
        EvaluationScenario.experiment_id == experiment_id,
        EvaluationScenario.name == scenario_name,
    )

    evidence = session.scalar(statement)

    if evidence is None:
        return None

    # Allow only fields intended for diagnosis.
    return {
        "status": evidence["status"],
        "failed_rules": list(evidence["failed_rules"]),
        "failed_checks": [
            {
                "rule_id": check["rule_id"],
                "rule_type": check["rule_type"],
                "failed_rows": check["failed_rows"],
                "checked_rows": check["checked_rows"],
            }
            for check in evidence.get("failed_checks", [])
        ],
    }
