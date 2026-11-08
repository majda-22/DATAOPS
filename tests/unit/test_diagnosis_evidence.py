from dataclasses import asdict

import pytest

from dataops.diagnosis.evidence import build_quality_evidence


def test_failed_rule_becomes_evidence():
    report = {
        "status": "FAIL",
        "results": [
            {"rule_id": "order_id_unique", "status": "FAIL"},
            {"rule_id": "order_id_not_null", "status": "PASS"},
        ],
    }

    evidence = build_quality_evidence(report)

    assert evidence.status == "FAIL"
    assert evidence.failed_rules == ("order_id_unique",)


def test_ground_truth_fields_are_excluded():
    report = {
        "status": "FAIL",
        "expected_rule": "secret_answer",
        "fault_type": "duplicate_key",
        "results": [
            {
                "rule_id": "order_id_unique",
                "status": "FAIL",
                "expected_rule": "secret_answer",
            }
        ],
    }

    evidence = build_quality_evidence(report)
    serialized = asdict(evidence)

    assert "expected_rule" not in serialized
    assert "fault_type" not in serialized
    assert "secret_answer" not in str(serialized)


def test_clean_report_produces_empty_evidence():
    report = {
        "status": "PASS",
        "results": [
            {"rule_id": "order_id_unique", "status": "PASS"},
        ],
    }

    evidence = build_quality_evidence(report)

    assert evidence.failed_rules == ()


def test_invalid_report_is_rejected():
    report = {
        "status": "PASS",
        "results": [
            {"rule_id": "order_id_unique", "status": "FAIL"},
        ],
    }

    with pytest.raises(ValueError):
        build_quality_evidence(report)


def test_evidence_preserves_failed_check_details():
    report = {
        "status": "FAIL",
        "results": [
            {
                "rule_id": "order_id_unique",
                "rule_type": "unique",
                "status": "FAIL",
                "failed_rows": 2,
                "checked_rows": 100,
                "examples": [{"key": {"order_id": "A1"}}],
            }
        ],
    }

    evidence = build_quality_evidence(report)

    assert evidence.failed_rules == ("order_id_unique",)
    assert len(evidence.failed_checks) == 1

    check = evidence.failed_checks[0]

    assert check.rule_type == "unique"
    assert check.failed_rows == 2
    assert check.checked_rows == 100

    # Raw record examples are not exposed.
    assert "A1" not in str(asdict(evidence))
