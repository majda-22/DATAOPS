from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FailedCheck:
    rule_id: str
    rule_type: str
    failed_rows: int
    checked_rows: int


@dataclass(frozen=True)
class QualityEvidence:
    """Observable quality information for diagnosis."""

    status: str
    failed_rules: tuple[str, ...]
    failed_checks: tuple[FailedCheck, ...] = ()


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
    failed_checks = []

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

            rule_type = result.get("rule_type")
            failed_rows = result.get("failed_rows")
            checked_rows = result.get("checked_rows")

            if (
                isinstance(rule_type, str)
                and type(failed_rows) is int
                and type(checked_rows) is int
                and 0 <= failed_rows <= checked_rows
            ):
                failed_checks.append(
                    FailedCheck(
                        rule_id=rule_id,
                        rule_type=rule_type,
                        failed_rows=failed_rows,
                        checked_rows=checked_rows,
                    )
                )

    if (status == "FAIL") != bool(failed_rules):
        raise ValueError("Report status conflicts with failed rules")

    return QualityEvidence(
        status=status,
        failed_rules=tuple(sorted(set(failed_rules))),
        failed_checks=tuple(
            sorted(
                failed_checks,
                key=lambda check: check.rule_id,
            )
        ),
    )
