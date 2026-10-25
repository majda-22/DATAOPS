import pytest

from dataops.evaluation.detector import evaluate_detection
from dataops.faults.models import FaultGroundTruth


@pytest.fixture
def ground_truth():
    return FaultGroundTruth(
        fault_type="invalid_value",
        column="order_status",
        affected_rows=(1,),
        expected_rule="order_status_allowed",
        original_values=("shipped",),
        injected_values=("INVALID_STATUS",),
    )


def test_correct_fault_detection(ground_truth):
    report = {
        "status": "FAIL",
        "results": [
            {"rule_id": "order_id_unique", "status": "PASS"},
            {"rule_id": "order_status_allowed", "status": "FAIL"},
        ],
    }

    result = evaluate_detection(report, ground_truth)

    assert result.detected is True
    assert result.expected_rule_hit is True
    assert result.detected_rules == ("order_status_allowed",)
    assert result.unexpected_rules == ()
    assert result.false_positive is False


def test_missed_fault(ground_truth):
    report = {
        "status": "PASS",
        "results": [
            {"rule_id": "order_status_allowed", "status": "PASS"},
        ],
    }

    result = evaluate_detection(report, ground_truth)

    assert result.detected is False
    assert result.expected_rule_hit is False


def test_wrong_rule_detected(ground_truth):
    report = {
        "status": "FAIL",
        "results": [
            {"rule_id": "order_id_unique", "status": "FAIL"},
            {"rule_id": "order_status_allowed", "status": "PASS"},
        ],
    }

    result = evaluate_detection(report, ground_truth)

    assert result.detected is True
    assert result.expected_rule_hit is False
    assert result.unexpected_rules == ("order_id_unique",)


def test_clean_dataset_has_no_false_positive():
    report = {
        "status": "PASS",
        "results": [
            {"rule_id": "order_id_unique", "status": "PASS"},
            {"rule_id": "order_status_allowed", "status": "PASS"},
        ],
    }

    result = evaluate_detection(report, None)

    assert result.fault_present is False
    assert result.detected is False
    assert result.expected_rule_hit is None
    assert result.false_positive is False


def test_clean_dataset_with_alert_is_false_positive():
    report = {
        "status": "FAIL",
        "results": [
            {"rule_id": "order_id_unique", "status": "FAIL"},
        ],
    }

    result = evaluate_detection(report, None)

    assert result.false_positive is True
    assert result.unexpected_rules == ("order_id_unique",)


def test_empty_report_is_rejected():
    with pytest.raises(ValueError, match="must contain results"):
        evaluate_detection({"status": "PASS", "results": []}, None)


def test_inconsistent_report_is_rejected():
    report = {
        "status": "PASS",
        "results": [
            {"rule_id": "order_status_allowed", "status": "FAIL"},
        ],
    }

    with pytest.raises(ValueError, match="conflicts"):
        evaluate_detection(report, None)
