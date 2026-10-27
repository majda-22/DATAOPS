from dataclasses import asdict
from uuid import UUID

from sqlalchemy.orm import Session

from dataops.db.models import EvaluationExperiment, EvaluationScenario
from dataops.evaluation.metrics import ExperimentMetrics
from dataops.evaluation.runner import ExperimentResult


def persist_experiment(
    session: Session,
    experiment: ExperimentResult,
    metrics: ExperimentMetrics,
) -> UUID:
    """Persist an experiment and its scenario results atomically."""

    if metrics.total_scenarios != len(experiment.scenarios):
        raise ValueError("Experiment metrics do not match scenario count")

    with session.begin():
        existing = session.get(
            EvaluationExperiment,
            experiment.experiment_id,
        )

        if existing is not None:
            raise ValueError(f"Experiment already persisted: {experiment.experiment_id}")

        session.add(
            EvaluationExperiment(
                id=experiment.experiment_id,
                metrics=asdict(metrics),
            )
        )

        for result in experiment.scenarios:
            session.add(
                EvaluationScenario(
                    experiment_id=experiment.experiment_id,
                    name=result.name,
                    duration_seconds=result.duration_seconds,
                    evaluation=asdict(result.evaluation),
                    ground_truth=None,
                )
            )

    return experiment.experiment_id
