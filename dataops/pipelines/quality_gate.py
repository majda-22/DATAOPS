from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class QualityGateError(RuntimeError):
    """Raised when quality validation blocks publication."""


def publish_if_quality_passed(
    report: dict,
    publish: Callable[[], T],
) -> T:
    """Execute publication only when all quality checks pass."""

    results = report.get("results")

    if not isinstance(results, list) or not results:
        raise QualityGateError("Quality report has no checks")

    if report.get("status") != "PASS":
        raise QualityGateError("Quality gate failed. Publication blocked.")

    if any(check.get("status") != "PASS" for check in results):
        raise QualityGateError("A quality check failed. Publication blocked.")

    return publish()
