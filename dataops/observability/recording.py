"""Record a CSV observation as durable contracts, runs, profiles, and quality results."""

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from dataops.contracts.loader import load_contract
from dataops.db import models
from dataops.db.queries import (
    Q1_DATASET_HISTORY,
    Q2_PIPELINE_TASKS,
    Q3_QUALITY_FAILURES,
    Q4_INCIDENT_INVESTIGATION,
    Q5_EVALUATION_CASES,
)
from dataops.observability.profiler import profile_csv
from dataops.quality.engine import evaluate_csv
from dataops.quality.status import pipeline_status, quality_status


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_csv_run(
    engine: Engine,
    csv_path: str | Path,
    contract_path: str | Path,
    *,
    reference_data: Mapping[str, str | Path] | None = None,
    event_time: datetime | None = None,
) -> dict[str, Any]:
    """Commit each stage and close failed runs even when an observation raises."""
    contract = load_contract(contract_path)
    path = Path(csv_path)
    run_id = uuid4()
    started = datetime.now(UTC)
    if event_time is not None and event_time.tzinfo is None:
        raise ValueError("event_time must include a timezone.")
    definition = contract.model_dump(mode="json")
    with Session(engine, expire_on_commit=False) as session:
        session.execute(
            insert(models.DatasetContract)
            .values(
                dataset_name=contract.dataset,
                version=contract.version,
                contract_definition=definition,
                is_active=True,
            )
            .on_conflict_do_nothing(index_elements=["dataset_name", "version"])
        )
        registered = session.scalars(
            select(models.DatasetContract).where(
                models.DatasetContract.dataset_name == contract.dataset,
                models.DatasetContract.version == contract.version,
            )
        ).one()
        if registered.contract_definition != definition:
            session.rollback()
            raise ValueError("A registered contract version is immutable; increment its version.")
        session.execute(
            update(models.DatasetContract)
            .where(
                models.DatasetContract.dataset_name == contract.dataset,
            )
            .values(is_active=False)
        )
        registered.is_active = True
        run = models.PipelineRun(
            id=run_id,
            dataset_contract_id=registered.id,
            pipeline_name=f"observe_{contract.dataset}_{run_id}",
            status="running",
            started_at=started,
            event_time=event_time,
        )
        session.add(run)
        task = models.TaskRun(
            pipeline_run_id=run_id, task_name="profile", status="running", started_at=started
        )
        session.add(task)
        session.commit()
        try:
            source_hash = file_digest(path)
            timestamp_columns = tuple(
                column.name for column in contract.columns if column.logical_type == "timestamp"
            )
            profile = profile_csv(
                path, dataset=contract.dataset, timestamp_columns=timestamp_columns
            )
            schema_definition = {
                "columns": definition["columns"],
                "observed_header": profile["columns"],
                "types_are_contract_declarations": True,
            }
            fingerprint = hashlib.sha256(
                json.dumps(schema_definition, sort_keys=True).encode()
            ).hexdigest()
            captured = datetime.now(UTC)
            session.add(
                models.SchemaSnapshot(
                    dataset_name=contract.dataset,
                    schema_definition=schema_definition,
                    fingerprint=fingerprint,
                    captured_at=captured,
                )
            )
            session.execute(
                insert(models.DatasetVersion)
                .values(
                    dataset_name=contract.dataset,
                    version=source_hash,
                    event_time=event_time or started,
                    recorded_at=captured,
                    row_count=profile["row_count"],
                    metadata_json={
                        "sha256": source_hash,
                        "source_file": path.name,
                        "pipeline_run_id": str(run_id),
                        "clock": "provided_event_time" if event_time else "observation_time",
                    },
                )
                .on_conflict_do_nothing(index_elements=["dataset_name", "version"])
            )
            session.add(
                models.TableProfile(
                    dataset_name=contract.dataset,
                    pipeline_run_id=run_id,
                    row_count=profile["row_count"],
                    column_profiles=profile,
                    profiled_at=captured,
                )
            )
            run.rows_in = profile["row_count"]
            task.status = "success"
            task.finished_at = captured
            task.rows_in = task.rows_out = profile["row_count"]
            task = models.TaskRun(
                pipeline_run_id=run_id, task_name="quality", status="running", started_at=captured
            )
            session.add(task)
            session.commit()

            quality = evaluate_csv(path, contract, reference_data=reference_data, run_id=run_id)
            # Guard the gap between profiling and evaluation against a changed input.
            if file_digest(path) != source_hash:
                raise ValueError("Source changed during observation; the run cannot be accepted.")
            for result in quality["results"]:
                session.add(
                    models.QualityResult(
                        pipeline_run_id=run_id,
                        rule_id=result["rule_id"],
                        status=quality_status(result["status"]),
                        failed_rows=result["failed_rows"],
                        details={**result, "run_id": str(run_id), "source_sha256": source_hash},
                    )
                )
            for key in contract.foreign_keys:
                session.execute(
                    insert(models.LineageEdge)
                    .values(
                        source_dataset=key.reference_dataset,
                        target_dataset=contract.dataset,
                        pipeline_run_id=run_id,
                        details={"relationship": "foreign_key", "rule_id": key.id},
                    )
                    .on_conflict_do_update(
                        index_elements=["source_dataset", "target_dataset"],
                        set_={
                            "pipeline_run_id": run_id,
                            "details": {"relationship": "foreign_key", "rule_id": key.id},
                        },
                    )
                )
            failures = [result for result in quality["results"] if result["status"] == "FAIL"]
            if failures:
                incident = models.Incident(
                    pipeline_run_id=run_id,
                    title=f"Quality failure: {contract.dataset}",
                    severity="high",
                    status="open",
                    evidence={
                        "source_sha256": source_hash,
                        "failed_rules": [r["rule_id"] for r in failures],
                    },
                )
                session.add(incident)
                session.flush()
                for failure in failures:
                    session.add(
                        models.IncidentEvidence(
                            incident_id=incident.id,
                            evidence_type="quality_failure",
                            evidence_payload=failure,
                        )
                    )
            finished = datetime.now(UTC)
            run.status = pipeline_status(quality["status"])
            run.finished_at = finished
            run.rows_out = profile["row_count"]  # Observation does not filter or transform rows.
            task.status = run.status
            task.finished_at = finished
            task.rows_in = task.rows_out = profile["row_count"]
            session.commit()
            return {
                "run_id": str(run_id),
                "dataset": contract.dataset,
                "contract_version": contract.version,
                "status": run.status,
                "row_count": profile["row_count"],
                "source_sha256": source_hash,
                "quality_results": quality["results"],
            }
        except Exception as error:
            session.rollback()
            run.status = task.status = "failed"
            run.finished_at = task.finished_at = datetime.now(UTC)
            run.error_message = task.error_message = str(error)
            incident = models.Incident(
                pipeline_run_id=run_id,
                title=f"Observation error: {contract.dataset}",
                severity="high",
                status="open",
                evidence={"error_type": type(error).__name__},
            )
            session.add(incident)
            session.flush()
            session.add(
                models.IncidentEvidence(
                    incident_id=incident.id,
                    evidence_type="execution_error",
                    evidence_payload={"error_type": type(error).__name__, "message": str(error)},
                )
            )
            session.commit()
            raise


def verify_recorded_run(
    engine: Engine, run_id: UUID | str, *, evaluator: Engine | None = None
) -> dict[str, Any]:
    """Execute shared Q1–Q5; evaluation is an explicit, separate connection."""
    with Session(engine) as session:
        run = session.get(models.PipelineRun, UUID(str(run_id)))
        if run is None:
            raise ValueError("Unknown run UUID")
        contract = session.get(models.DatasetContract, run.dataset_contract_id)
        assert contract is not None
        dataset = contract.dataset_name
        pipeline_name = run.pipeline_name
    with engine.connect() as connection:
        history = [
            dict(row)
            for row in connection.execute(Q1_DATASET_HISTORY, {"dataset_name": dataset}).mappings()
        ]
        tasks = [
            dict(row)
            for row in connection.execute(
                Q2_PIPELINE_TASKS, {"pipeline_name": pipeline_name}
            ).mappings()
        ]
        failures = [
            dict(row)
            for row in connection.execute(
                Q3_QUALITY_FAILURES, {"pipeline_run_id": UUID(str(run_id))}
            ).mappings()
        ]
        incidents = [
            dict(row)
            for row in connection.execute(
                Q4_INCIDENT_INVESTIGATION, {"pipeline_run_id": UUID(str(run_id))}
            ).mappings()
        ]
    evaluation: dict[str, Any] = {"status": "not_run", "reason": "No evaluator connection supplied"}
    if evaluator is not None:
        with evaluator.connect() as connection:
            cases = [
                dict(row)
                for row in connection.execute(
                    Q5_EVALUATION_CASES, {"split": "held_out", "case_prefix": f"{dataset}:%"}
                ).mappings()
            ]
        evaluation = {
            "status": "queried",
            "cases": cases,
            "note": "Labels are never inferred from engine output; empty means no curated cases.",
        }
    return {
        "run_id": str(run_id),
        "Q1_dataset_history": history,
        "Q2_tasks": tasks,
        "Q3_quality_failures": failures,
        "Q4_incidents": incidents,
        "Q5_evaluation": evaluation,
    }
