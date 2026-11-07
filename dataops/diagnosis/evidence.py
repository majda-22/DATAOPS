from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QualityEvidence:
    """Observable quality information for diagnosis."""

    status: str
    failed_rules: tuple[str, ...]


def build_quality_evidence(
    report: Mapping[str, Any],
) -> QualityEvidence:
    """Extract observable evidence without evaluation answers."""

    status = report.get("status")
    results = report.get("results")

    if status not in {"PASS", "FAIL"}:
        raise ValueError("Invalid report status")

    if not isinstance(results, list) or not results:
        raise ValueError("Quality report must contain results")

    failed_rules = []

    for result in results:
        if not isinstance(result, dict):
            raise ValueError("Invalid quality result")

        rule_id = result.get("rule_id")
        rule_status = result.get("status")

        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError("Invalid rule identifier")

        if rule_status not in {"PASS", "FAIL"}:
            raise ValueError("Invalid rule status")

        if rule_status == "FAIL":
            failed_rules.append(rule_id)

    if (status == "FAIL") != bool(failed_rules):
        raise ValueError("Report status conflicts with failed rules")

    return QualityEvidence(
        status=status,
        failed_rules=tuple(sorted(set(failed_rules))),
    )
