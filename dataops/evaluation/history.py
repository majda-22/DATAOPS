from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from dataops.db.models import EvaluationExperiment, EvaluationScenario


def list_experiments(
    session: Session,
    limit: int = 20,
) -> list[dict]:
    """Return recent experiment summaries."""

    if limit < 1:
        raise ValueError("Limit must be positive")

    statement = (
        select(EvaluationExperiment)
        .order_by(
            EvaluationExperiment.created_at.desc(),
            EvaluationExperiment.id.desc(),
        )
        .limit(limit)
    )

    experiments = session.scalars(statement).all()

    return [
        {
            "experiment_id": str(experiment.id),
            "created_at": experiment.created_at.isoformat(),
            "metrics": experiment.metrics,
        }
        for experiment in experiments
    ]


def get_experiment_details(
    session: Session,
    experiment_id: UUID,
) -> dict | None:
    """Retrieve one experiment and its scenario outcomes."""

    experiment = session.get(EvaluationExperiment, experiment_id)

    if experiment is None:
        return None

    statement = (
        select(EvaluationScenario)
        .where(EvaluationScenario.experiment_id == experiment_id)
        .order_by(EvaluationScenario.id)
    )

    scenarios = session.scalars(statement).all()

    return {
        "experiment_id": str(experiment.id),
        "created_at": experiment.created_at.isoformat(),
        "metrics": experiment.metrics,
        "scenarios": [
            {
                "name": scenario.name,
                "duration_seconds": scenario.duration_seconds,
                "evaluation": scenario.evaluation,
            }
            for scenario in scenarios
        ],
    }
