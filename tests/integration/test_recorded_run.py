from uuid import UUID, uuid4

import pytest
import yaml
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from dataops.db import models
from dataops.observability.recording import record_csv_run, verify_recorded_run
from tests.integration.test_metadata_queries import pg_engine as pg_engine


@pytest.fixture
def observation_case(pg_engine, tmp_path):
    dataset = "bridge_" + uuid4().hex
    contract = {
        "dataset": dataset,
        "version": 1,
        "description": "Bridge integration input",
        "layer": "bronze",
        "format": "csv",
        "columns": [{"name": "id", "logical_type": "string", "nullable": False}],
        "primary_key": ["id"],
        "quality_rules": [{"id": "volume", "type": "min_row_count", "min_rows": 2}],
    }
    path = tmp_path / "contract.yaml"
    path.write_text(yaml.safe_dump(contract))
    csv_path = tmp_path / "input.csv"
    csv_path.write_text("id\nA\nB\n")
    try:
        yield pg_engine, path, csv_path, contract
    finally:
        with Session(pg_engine) as session:
            contract_ids = select(models.DatasetContract.id).where(
                models.DatasetContract.dataset_name == dataset
            )
            run_ids = select(models.PipelineRun.id).where(
                models.PipelineRun.dataset_contract_id.in_(contract_ids)
            )
            session.execute(
                delete(models.Incident).where(models.Incident.pipeline_run_id.in_(run_ids))
            )
            session.execute(
                delete(models.LineageEdge).where(models.LineageEdge.pipeline_run_id.in_(run_ids))
            )
            for model in (models.TableProfile, models.DatasetVersion, models.SchemaSnapshot):
                session.execute(delete(model).where(model.dataset_name == dataset))
            session.execute(delete(models.PipelineRun).where(models.PipelineRun.id.in_(run_ids)))
            session.execute(
                delete(models.DatasetContract).where(models.DatasetContract.dataset_name == dataset)
            )
            session.commit()


def test_successful_observation_is_durable_idempotent_and_queryable(observation_case):
    engine, contract_path, csv_path, contract = observation_case
    first = record_csv_run(engine, csv_path, contract_path)
    second = record_csv_run(engine, csv_path, contract_path)
    assert UUID(first["run_id"]) != UUID(second["run_id"])
    assert first["status"] == second["status"] == "success"
    verification = verify_recorded_run(engine, first["run_id"], evaluator=engine)
    assert len(verification["Q1_dataset_history"]) == 1
    assert len(verification["Q2_tasks"]) == 2
    assert verification["Q3_quality_failures"] == verification["Q4_incidents"] == []
    assert verification["Q5_evaluation"]["status"] == "queried"
    with Session(engine) as session:
        run = session.get(models.PipelineRun, UUID(first["run_id"]))
        assert run.finished_at >= run.started_at
        results = session.scalars(
            select(models.QualityResult).where(models.QualityResult.pipeline_run_id == run.id)
        ).all()
        assert results and all(
            r.status == "passed" and r.details["run_id"] == first["run_id"] for r in results
        )
        profile = session.scalars(
            select(models.TableProfile).where(models.TableProfile.pipeline_run_id == run.id)
        ).one()
        assert profile.row_count == 2


def test_quality_failure_records_real_incident_and_evidence(observation_case):
    engine, contract_path, csv_path, _ = observation_case
    csv_path.write_text("id\nA\n")
    report = record_csv_run(engine, csv_path, contract_path)
    assert report["status"] == "failed"
    verification = verify_recorded_run(engine, report["run_id"])
    assert verification["Q3_quality_failures"][0]["rule_id"] == "volume"
    incident = verification["Q4_incidents"][0]
    assert incident["evidence_payload"]["examples"][0]["observed_rows"] == 1


def test_source_error_closes_run_and_task_instead_of_leaving_running(observation_case):
    engine, contract_path, csv_path, contract = observation_case
    with pytest.raises(FileNotFoundError):
        record_csv_run(engine, csv_path.parent / "missing.csv", contract_path)
    with Session(engine) as session:
        run = session.scalars(
            select(models.PipelineRun)
            .join(models.DatasetContract)
            .where(models.DatasetContract.dataset_name == contract["dataset"])
        ).one()
        assert run.status == "failed" and run.finished_at is not None
        task = session.scalars(
            select(models.TaskRun).where(models.TaskRun.pipeline_run_id == run.id)
        ).one()
        assert task.status == "failed" and task.error_message


def test_reusing_a_contract_version_with_changed_definition_is_rejected(observation_case):
    engine, contract_path, csv_path, contract = observation_case
    record_csv_run(engine, csv_path, contract_path)
    contract["description"] = "Changed without incrementing version"
    contract_path.write_text(yaml.safe_dump(contract))
    with pytest.raises(ValueError, match="immutable"):
        record_csv_run(engine, csv_path, contract_path)
