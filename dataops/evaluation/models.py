from dataclasses import dataclass


@dataclass(frozen=True)
class DetectionEvaluation:
    """Result of comparing detector output with ground truth."""

    expected_rule: str | None
    detected_rules: tuple[str, ...]
    fault_present: bool
    detected: bool
    expected_rule_hit: bool | None
    false_positive: bool
    unexpected_rules: tuple[str, ...]
