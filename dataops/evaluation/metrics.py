from dataclasses import dataclass

from dataops.evaluation.runner import ExperimentResult


@dataclass(frozen=True)
class ExperimentMetrics:
    total_scenarios: int
    fault_scenarios: int
    clean_scenarios: int
    detected_faults: int
    correct_rule_hits: int
    false_positives: int
    detection_rate: float | None
    expected_rule_hit_rate: float | None
    false_positive_rate: float | None
    average_duration_seconds: float


def calculate_metrics(
    experiment: ExperimentResult,
) -> ExperimentMetrics:
    """Calculate scenario-level detector performance."""

    results = experiment.scenarios

    if not results:
        raise ValueError("Cannot calculate metrics for an empty experiment")

    faulty = [result for result in results if result.evaluation.fault_present]

    clean = [result for result in results if not result.evaluation.fault_present]

    detected_faults = sum(result.evaluation.detected for result in faulty)

    correct_rule_hits = sum(result.evaluation.expected_rule_hit is True for result in faulty)

    false_positives = sum(result.evaluation.false_positive for result in clean)

    fault_count = len(faulty)
    clean_count = len(clean)

    return ExperimentMetrics(
        total_scenarios=len(results),
        fault_scenarios=fault_count,
        clean_scenarios=clean_count,
        detected_faults=detected_faults,
        correct_rule_hits=correct_rule_hits,
        false_positives=false_positives,
        detection_rate=(detected_faults / fault_count if fault_count else None),
        expected_rule_hit_rate=(correct_rule_hits / fault_count if fault_count else None),
        false_positive_rate=(false_positives / clean_count if clean_count else None),
        average_duration_seconds=(
            sum(result.duration_seconds for result in results) / len(results)
        ),
    )
