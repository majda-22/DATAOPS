import pytest

from dataops.evaluation.runner import (
    ExperimentScenario,
    run_experiment,
)
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


def fake_detector(data):
    """Produce a quality report from synthetic input data."""

    invalid = data["order_status"] == "INVALID_STATUS"

    return {
        "status": "FAIL" if invalid else "PASS",
        "results": [
            {
                "rule_id": "order_status_allowed",
                "status": "FAIL" if invalid else "PASS",
            }
        ],
    }


def test_experiment_runs_clean_and_faulty_scenarios():
    scenarios = [
        ExperimentScenario(
            name="clean",
            data={"order_status": "shipped"},
        ),
        ExperimentScenario(
            name="invalid_status",
            data={"order_status": "INVALID_STATUS"},
            ground_truth=make_truth(),
        ),
    ]

    result = run_experiment(scenarios, fake_detector)

    assert len(result.scenarios) == 2
    assert result.scenarios[0].evaluation.detected is False
    assert result.scenarios[1].evaluation.detected is True
    assert result.scenarios[1].evaluation.expected_rule_hit is True
    assert all(scenario.duration_seconds >= 0 for scenario in result.scenarios)


def test_detector_does_not_receive_ground_truth():
    truth = make_truth()
    received = []

    def detector(data):
        received.append(data)
        return {
            "status": "PASS",
            "results": [
                {
                    "rule_id": "order_status_allowed",
                    "status": "PASS",
                }
            ],
        }

    run_experiment(
        [
            ExperimentScenario(
                name="fault",
                data={"order_status": "INVALID_STATUS"},
                ground_truth=truth,
            )
        ],
        detector,
    )

    assert received == [{"order_status": "INVALID_STATUS"}]


def test_empty_experiment_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        run_experiment([], fake_detector)


def test_duplicate_scenario_names_are_rejected():
    scenarios = [
        ExperimentScenario("duplicate", {"order_status": "shipped"}),
        ExperimentScenario("duplicate", {"order_status": "shipped"}),
    ]

    with pytest.raises(ValueError, match="unique"):
        run_experiment(scenarios, fake_detector)
