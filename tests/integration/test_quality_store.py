from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from dataops.db.models import PipelineRun, QualityResult
from dataops.observability.quality_store import persist_quality_report


@pytest.fixture
def store_connection(pg_engine):
    """Connect to the dedicated test database and roll back all test data."""
    if pg_engine.url.database != "dataops_metadata_test":
        pytest.fail("Refusing to write outside dataops_metadata_test")

    connection = pg_engine.connect()
    transaction = connection.begin()

    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


def make_report(*, failed=False):
    """Create an isolated quality report for an integration test."""
    started = datetime.now(UTC)

    return {
        "run_id": str(uuid4()),
        "started_at": started.isoformat(),
        "finished_at": (started + timedelta(seconds=1)).isoformat(),
        "dataset": "test_orders",
        "contract_version": 1,
        "source_file": "s3a://bronze/test/orders",
        "row_count": 10,
        "status": "FAIL" if failed else "PASS",
        "results": [
            {
                "rule_id": "order_id_not_null",
                "rule_type": "not_null",
                "status": "PASS",
                "checked_rows": 10,
                "failed_rows": 0,
                "examples": [],
            },
            {
                "rule_id": "order_status_allowed",
                "rule_type": "accepted_values",
                "status": "FAIL" if failed else "PASS",
                "checked_rows": 10,
                "failed_rows": 2 if failed else 0,
                "examples": ([{"value": "invalid"}] if failed else []),
            },
        ],
    }


def make_session(connection):
    return Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )


def test_persist_passing_report(store_connection):
    report = make_report()

    with make_session(store_connection) as session:
        run_id = persist_quality_report(session, report)

    with make_session(store_connection) as session:
        run = session.get(PipelineRun, run_id)
        assert run is not None
        assert run.status == "success"
        assert run.rows_in == 10
        assert run.rows_out is None

        results = session.scalars(
            select(QualityResult).where(QualityResult.pipeline_run_id == run_id)
        ).all()

        assert len(results) == 2
        assert all(result.status == "passed" for result in results)
        assert results[0].details["dataset"] == "test_orders"


def test_persist_same_run_is_idempotent(store_connection):
    report = make_report()

    with make_session(store_connection) as session:
        first_id = persist_quality_report(session, report)

    with make_session(store_connection) as session:
        second_id = persist_quality_report(session, report)

    assert first_id == second_id

    with make_session(store_connection) as session:
        count = session.scalar(
            select(func.count(QualityResult.id)).where(QualityResult.pipeline_run_id == first_id)
        )

        assert count == 2


def test_persist_failing_report(store_connection):
    report = make_report(failed=True)

    with make_session(store_connection) as session:
        run_id = persist_quality_report(session, report)

    with make_session(store_connection) as session:
        run = session.get(PipelineRun, run_id)
        assert run.status == "failed"
        assert run.rows_out is None

        results = session.scalars(
            select(QualityResult).where(QualityResult.pipeline_run_id == run_id)
        ).all()

        statuses = {result.rule_id: result.status for result in results}

        assert statuses["order_id_not_null"] == "passed"
        assert statuses["order_status_allowed"] == "failed"


def test_failed_insert_rolls_back_pipeline_run(store_connection):
    report = make_report()
    run_id = report["run_id"]

    with make_session(store_connection) as session:

        def reject_quality_insert(session, flush_context, instances):
            if any(isinstance(obj, QualityResult) for obj in session.new):
                raise RuntimeError("Simulated quality insert failure")

        event.listen(session, "before_flush", reject_quality_insert)

        with pytest.raises(RuntimeError, match="Simulated"):
            persist_quality_report(session, report)

    # The pipeline was flushed before the quality insert failed.
    # Transaction rollback must remove the pipeline record too.
    with make_session(store_connection) as session:
        run = session.get(PipelineRun, uuid4_type(run_id))
        assert run is None


def uuid4_type(value):
    from uuid import UUID

    return UUID(str(value))
