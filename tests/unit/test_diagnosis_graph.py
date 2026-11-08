from uuid import uuid4

from dataops.diagnosis.graph import build_diagnosis_graph


def test_graph_diagnoses_failed_quality_rule():
    def fake_evidence_loader(experiment_id, scenario_name):
        return {
            "status": "FAIL",
            "failed_rules": ["order_id_unique"],
        }

    graph = build_diagnosis_graph(fake_evidence_loader)

    result = graph.invoke(
        {
            "experiment_id": str(uuid4()),
            "scenario_name": "duplicate_key",
        }
    )

    assert result["diagnosis"]["status"] == "failure_detected"
    assert result["diagnosis"]["suspected_rules"] == ["order_id_unique"]


def test_graph_handles_clean_data():
    def fake_evidence_loader(experiment_id, scenario_name):
        return {
            "status": "PASS",
            "failed_rules": [],
        }

    graph = build_diagnosis_graph(fake_evidence_loader)

    result = graph.invoke(
        {
            "experiment_id": str(uuid4()),
            "scenario_name": "clean_control",
        }
    )

    assert result["diagnosis"]["status"] == "no_failure_detected"
    assert result["diagnosis"]["suspected_rules"] == []


def test_graph_calculates_violation_rate():
    def fake_loader(experiment_id, scenario_name):
        return {
            "status": "FAIL",
            "failed_rules": ["order_id_unique"],
            "failed_checks": [
                {
                    "rule_id": "order_id_unique",
                    "rule_type": "unique",
                    "failed_rows": 2,
                    "checked_rows": 100,
                }
            ],
        }

    graph = build_diagnosis_graph(fake_loader)

    result = graph.invoke(
        {
            "experiment_id": str(uuid4()),
            "scenario_name": "duplicate_key",
        }
    )

    assert result["findings"] == [
        {
            "rule_id": "order_id_unique",
            "rule_type": "unique",
            "failed_rows": 2,
            "checked_rows": 100,
            "violation_rate": 0.02,
        }
    ]
