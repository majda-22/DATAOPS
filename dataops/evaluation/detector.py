from collections.abc import Mapping
from typing import Any

from dataops.evaluation.models import DetectionEvaluation
from dataops.faults.models import FaultGroundTruth


def evaluate_detection(
    report: Mapping[str, Any],
    ground_truth: FaultGroundTruth | None,
) -> DetectionEvaluation:
    """Compare quality detections with held-out ground truth."""

    results = report.get("results")

    if not isinstance(results, list) or not results:
        raise ValueError("Quality report must contain results")

    detected_rules: set[str] = set()

    for result in results:
        if not isinstance(result, dict):
            raise ValueError("Each quality result must be a dictionary")

        rule_id = result.get("rule_id")
        status = result.get("status")

        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError("Each quality result needs a rule_id")

        if status not in {"PASS", "FAIL"}:
            raise ValueError(f"Unexpected quality status: {status}")

        if status == "FAIL":
            detected_rules.add(rule_id)

    overall_status = report.get("status")

    if overall_status not in {"PASS", "FAIL"}:
        raise ValueError("Unexpected overall quality status")

    if (overall_status == "FAIL") != bool(detected_rules):
        raise ValueError("Overall status conflicts with rule results")

    detected = bool(detected_rules)
    fault_present = ground_truth is not None

    if ground_truth is None:
        expected_rule = None
        expected_rule_hit = None
        unexpected_rules = tuple(sorted(detected_rules))
    else:
        expected_rule = ground_truth.expected_rule
        expected_rule_hit = expected_rule in detected_rules
        unexpected_rules = tuple(sorted(detected_rules - {expected_rule}))

    return DetectionEvaluation(
        expected_rule=expected_rule,
        detected_rules=tuple(sorted(detected_rules)),
        fault_present=fault_present,
        detected=detected,
        expected_rule_hit=expected_rule_hit,
        false_positive=not fault_present and detected,
        unexpected_rules=unexpected_rules,
    )
