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
    assert len(result["diagnosis"]["hypotheses"]) == 3
    assert result["findings"] == [
        {
            "rule_id": "order_id_unique",
            "rule_type": "unique",
            "failed_rows": 2,
            "checked_rows": 100,
            "violation_rate": 0.02,
        }
    ]


def test_graph_inspects_explicit_pipeline_run():
    run_id = uuid4()
    inspected_ids = []

    def fake_evidence_loader(experiment_id, scenario_name):
        return {
            "status": "FAIL",
            "failed_rules": ["order_id_unique"],
            "failed_checks": [],
        }

    def fake_pipeline_loader(requested_id):
        inspected_ids.append(requested_id)
        return {
            "run_id": str(requested_id),
            "pipeline_name": "olist_bronze_quality",
            "status": "success",
        }

    graph = build_diagnosis_graph(
        fake_evidence_loader,
        load_pipeline_run=fake_pipeline_loader,
    )

    result = graph.invoke(
        {
            "experiment_id": str(uuid4()),
            "scenario_name": "duplicate_key",
            "pipeline_run_id": str(run_id),
        }
    )

    assert inspected_ids == [run_id]
    assert result["pipeline_run"]["run_id"] == str(run_id)


def test_graph_does_not_guess_pipeline_run():
    def fake_evidence_loader(experiment_id, scenario_name):
        return {
            "status": "PASS",
            "failed_rules": [],
        }

    def forbidden_pipeline_loader(run_id):
        raise AssertionError("Pipeline lookup must not occur")

    graph = build_diagnosis_graph(
        fake_evidence_loader,
        load_pipeline_run=forbidden_pipeline_loader,
    )

    result = graph.invoke(
        {
            "experiment_id": str(uuid4()),
            "scenario_name": "clean_control",
        }
    )

    assert result["pipeline_run"] is None


def test_graph_uses_pipeline_run_from_incident():
    run_id = uuid4()
    incident_id = 42
    loaded_runs = []

    def fake_evidence_loader(experiment_id, scenario_name):
        return {
            "status": "FAIL",
            "failed_rules": ["order_id_unique"],
            "failed_checks": [],
        }

    def fake_incident_loader(requested_id):
        assert requested_id == incident_id
        return {
            "incident_id": requested_id,
            "pipeline_run_id": str(run_id),
            "title": "Order quality failure",
            "severity": "high",
            "status": "open",
        }

    def fake_incident_evidence_loader(incident_id):
        assert incident_id == 42
        return {
            "status": "FAIL",
            "failed_rules": ["order_id_unique"],
            "failed_checks": [],
        }

    def fake_pipeline_loader(requested_id):
        loaded_runs.append(requested_id)
        return {
            "run_id": str(requested_id),
            "status": "failed",
        }

    graph = build_diagnosis_graph(
        fake_evidence_loader,
        load_pipeline_run=fake_pipeline_loader,
        load_incident=fake_incident_loader,
        load_incident_evidence=fake_incident_evidence_loader,
    )

    result = graph.invoke(
        {
            "incident_id": incident_id,
            "experiment_id": str(uuid4()),
            "scenario_name": "duplicate_key",
        }
    )

    assert result["incident"]["incident_id"] == incident_id
    assert loaded_runs == [run_id]
    assert result["pipeline_run"]["run_id"] == str(run_id)


def test_graph_supports_incident_only_diagnosis():
    run_id = uuid4()

    def fake_experiment_loader(experiment_id, scenario_name):
        raise AssertionError("Experiment loader must not be called")

    def fake_incident_loader(incident_id):
        return {
            "incident_id": incident_id,
            "pipeline_run_id": str(run_id),
            "title": "Order quality failure",
            "severity": "high",
            "status": "open",
        }

    def fake_incident_evidence_loader(incident_id):
        return {
            "status": "FAIL",
            "failed_rules": ["order_id_unique"],
            "failed_checks": [],
        }

    def fake_pipeline_loader(requested_id):
        return {
            "run_id": str(requested_id),
            "pipeline_name": "olist_bronze_quality",
            "status": "failed",
        }

    graph = build_diagnosis_graph(
        fake_experiment_loader,
        load_pipeline_run=fake_pipeline_loader,
        load_incident=fake_incident_loader,
        load_incident_evidence=fake_incident_evidence_loader,
    )

    result = graph.invoke({"incident_id": 42})

    assert result["incident"]["incident_id"] == 42
    assert result["pipeline_run"]["run_id"] == str(run_id)
    assert result["diagnosis"]["status"] == "failure_detected"
    assert result["diagnosis"]["suspected_rules"] == ["order_id_unique"]
