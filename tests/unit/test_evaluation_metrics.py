import pytest

from dataops.evaluation.metrics import calculate_metrics
from dataops.evaluation.runner import ExperimentScenario, run_experiment
from dataops.faults.models import FaultGroundTruth


def make_truth():
    return FaultGroundTruth(
        fault_type="invalid_value",
        column="order_status",
        affected_rows=(0,),
        expected_rule="order_status_allowed",
        original_values=("shipped",),
        injected_values=("INVALID_STATUS",),
    )


def detector(data):
    detected = data["alert"]

    return {
        "status": "FAIL" if detected else "PASS",
        "results": [
            {
                "rule_id": data["rule"],
                "status": "FAIL" if detected else "PASS",
            }
        ],
    }


def test_aggregate_detection_metrics():
    scenarios = [
        ExperimentScenario(
            "correct_detection",
            {"alert": True, "rule": "order_status_allowed"},
            make_truth(),
        ),
        ExperimentScenario(
            "missed_detection",
            {"alert": False, "rule": "order_status_allowed"},
            make_truth(),
        ),
        ExperimentScenario(
            "clean_control",
            {"alert": False, "rule": "order_id_unique"},
        ),
        ExperimentScenario(
            "false_positive",
            {"alert": True, "rule": "order_id_unique"},
        ),
    ]

    experiment = run_experiment(scenarios, detector)
    metrics = calculate_metrics(experiment)

    assert metrics.total_scenarios == 4
    assert metrics.fault_scenarios == 2
    assert metrics.clean_scenarios == 2
    assert metrics.detected_faults == 1
    assert metrics.correct_rule_hits == 1
    assert metrics.false_positives == 1

    assert metrics.detection_rate == 0.5
    assert metrics.expected_rule_hit_rate == 0.5
    assert metrics.false_positive_rate == 0.5
    assert metrics.average_duration_seconds >= 0


def test_no_clean_controls_has_undefined_false_positive_rate():
    experiment = run_experiment(
        [
            ExperimentScenario(
                "fault",
                {"alert": True, "rule": "order_status_allowed"},
                make_truth(),
            )
        ],
        detector,
    )

    metrics = calculate_metrics(experiment)

    assert metrics.detection_rate == 1.0
    assert metrics.false_positive_rate is None


def test_no_faults_has_undefined_detection_rate():
    experiment = run_experiment(
        [
            ExperimentScenario(
                "clean",
                {"alert": False, "rule": "order_status_allowed"},
            )
        ],
        detector,
    )

    metrics = calculate_metrics(experiment)

    assert metrics.detection_rate is None
    assert metrics.expected_rule_hit_rate is None
    assert metrics.false_positive_rate == 0.0


def test_empty_experiment_metrics_are_rejected():
    from uuid import uuid4

    from dataops.evaluation.runner import ExperimentResult

    with pytest.raises(ValueError, match="empty experiment"):
        calculate_metrics(ExperimentResult(uuid4(), ()))
