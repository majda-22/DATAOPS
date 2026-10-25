from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from dataops.evaluation.detector import evaluate_detection
from dataops.evaluation.models import DetectionEvaluation
from dataops.faults.models import FaultGroundTruth


@dataclass(frozen=True)
class ExperimentScenario:
    """One clean or corrupted dataset to evaluate."""

    name: str
    data: Any
    ground_truth: FaultGroundTruth | None = None


@dataclass(frozen=True)
class ScenarioResult:
    """Evaluation result for one scenario."""

    name: str
    evaluation: DetectionEvaluation
    duration_seconds: float


@dataclass(frozen=True)
class ExperimentResult:
    """Results for an entire experiment."""

    experiment_id: UUID
    scenarios: tuple[ScenarioResult, ...]


def run_experiment(
    scenarios: Sequence[ExperimentScenario],
    detector: Callable[[Any], Mapping[str, Any]],
) -> ExperimentResult:
    """Run detection first, then evaluate against ground truth."""

    if not scenarios:
        raise ValueError("Experiment requires at least one scenario")

    names = [scenario.name for scenario in scenarios]

    if any(not name.strip() for name in names):
        raise ValueError("Scenario names cannot be empty")

    if len(set(names)) != len(names):
        raise ValueError("Scenario names must be unique")

    results = []

    for scenario in scenarios:
        # Only the dataset is passed to the detector.
        # Ground truth stays hidden during detection.
        start = perf_counter()

        report = detector(scenario.data)

        elapsed = perf_counter() - start

        # Ground truth is used only after detection finishes.
        evaluation = evaluate_detection(
            report,
            scenario.ground_truth,
        )

        results.append(
            ScenarioResult(
                name=scenario.name,
                evaluation=evaluation,
                duration_seconds=elapsed,
            )
        )

    return ExperimentResult(
        experiment_id=uuid4(),
        scenarios=tuple(results),
    )
