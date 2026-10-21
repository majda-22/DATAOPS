"""Executable PostgreSQL integration tests for metadata queries Q1–Q5.

Configuration:
    TEST_DATABASE_URL=postgresql+psycopg://.../dedicated_test_db

Optional privilege test:
    EVAL_RESTRICTED_DATABASE_URL=postgresql+psycopg://.../dedicated_test_db

The test database must already have the Alembic migrations applied. These tests
never create/drop schemas or tables. Each query test inserts uniquely named
fixtures inside a transaction and rolls the transaction back afterward.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import DBAPIError


def _normalize_postgres_url(url: str) -> str:
    """Use psycopg 3 explicitly for common PostgreSQL URL formats."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def _create_test_engine(url: str, variable: str) -> Engine:
    """Reject example settings before connecting and bound connection waits."""
    parsed = make_url(_normalize_postgres_url(url))
    if parsed.get_backend_name() != "postgresql":
        raise ValueError(f"{variable} must point to PostgreSQL.")
    if (
        parsed.username == "USER"
        or parsed.password == "PASSWORD"
        or parsed.database == "YOUR_TEST_DB"
    ):
        raise ValueError(
            f"{variable} still contains example values. Replace USER, PASSWORD, "
            "and YOUR_TEST_DB with credentials for a running, dedicated test database."
        )
    return create_engine(parsed, pool_pre_ping=True, connect_args={"connect_timeout": 5})


@pytest.fixture(scope="session")
def pg_engine() -> Engine:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "PostgreSQL integration tests require TEST_DATABASE_URL pointing "
            "to a dedicated test database with Alembic migrations applied."
        )

    try:
        engine = _create_test_engine(url, "TEST_DATABASE_URL")
    except ValueError as error:
        pytest.fail(str(error), pytrace=False)
    try:
        try:
            connection = engine.connect()
        except DBAPIError:
            pytest.fail(
                "Cannot connect using TEST_DATABASE_URL. Check that PostgreSQL is "
                "running, the host/port are reachable, and the database and credentials "
                "are correct. See tests/integration/README.md.",
                pytrace=False,
            )
        with connection:
            version = connection.execute(text("SELECT version()")).scalar_one()
            assert "PostgreSQL" in version, "TEST_DATABASE_URL must point to PostgreSQL"
            schemas = (
                connection.execute(
                    text(
                        "SELECT schema_name FROM information_schema.schemata "
                        "WHERE schema_name IN ('meta', 'eval')"
                    )
                )
                .scalars()
                .all()
            )
            assert set(schemas) == {"meta", "eval"}, (
                "Database is missing meta/eval schemas; apply Alembic migrations first."
            )
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db(pg_engine: Engine) -> Connection:
    """Give each test a transaction that is always rolled back."""
    connection = pg_engine.connect()
    transaction = connection.begin()
    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


@pytest.fixture
def case_key() -> str:
    return f"it-{uuid4().hex}"


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


# Q1 — Dataset version history, including the schema snapshot captured for it.
Q1_DATASET_HISTORY = text(
    """
    SELECT
        dv.dataset_name,
        dv.version,
        dv.event_time,
        dv.row_count,
        ss.fingerprint,
        ss.schema_definition
    FROM meta.dataset_versions AS dv
    LEFT JOIN LATERAL (
        SELECT s.fingerprint, s.schema_definition
        FROM meta.schema_snapshots AS s
        WHERE s.dataset_name = dv.dataset_name
          AND s.captured_at <= dv.recorded_at
        ORDER BY s.captured_at DESC, s.id DESC
        LIMIT 1
    ) AS ss ON TRUE
    WHERE dv.dataset_name = :dataset_name
    ORDER BY dv.event_time, dv.version
    """
)

# Q2 — Pipeline execution and its individual tasks.
Q2_PIPELINE_TASKS = text(
    """
    SELECT
        p.pipeline_name,
        p.status AS pipeline_status,
        p.rows_in AS pipeline_rows_in,
        p.rows_out AS pipeline_rows_out,
        t.task_name,
        t.status AS task_status,
        t.rows_in AS task_rows_in,
        t.rows_out AS task_rows_out
    FROM meta.pipeline_runs AS p
    JOIN meta.task_runs AS t ON t.pipeline_run_id = p.id
    WHERE p.pipeline_name = :pipeline_name
    ORDER BY t.task_name
    """
)

# Q3 — Failed quality checks for a pipeline execution.
Q3_QUALITY_FAILURES = text(
    """
    SELECT
        p.pipeline_name,
        p.status AS pipeline_status,
        q.rule_id,
        q.status AS quality_status,
        q.failed_rows,
        q.details
    FROM meta.pipeline_runs AS p
    JOIN meta.quality_results AS q ON q.pipeline_run_id = p.id
    WHERE p.id = :pipeline_run_id
      AND q.status IN ('failed', 'error')
    ORDER BY q.rule_id
    """
)

# Q4 — Incident investigation: incident evidence plus upstream/downstream lineage
# associated with the same pipeline run.
Q4_INCIDENT_INVESTIGATION = text(
    """
    SELECT
        i.id AS incident_id,
        i.title,
        i.severity,
        i.status AS incident_status,
        i.diagnosis,
        e.evidence_type,
        e.evidence_payload,
        le.source_dataset,
        le.target_dataset,
        le.details AS lineage_details
    FROM meta.incidents AS i
    LEFT JOIN meta.incident_evidence AS e ON e.incident_id = i.id
    LEFT JOIN meta.lineage_edges AS le ON le.pipeline_run_id = i.pipeline_run_id
    WHERE i.id = :incident_id
    ORDER BY e.id, le.id
    """
)

# Q5 — Evaluation labels are queried only from eval, with an explicit split filter.
Q5_EVALUATION_CASES = text(
    """
    SELECT
        case_key,
        expected_incident,
        expected_category,
        expected_diagnosis,
        split,
        labels
    FROM eval.incident_ground_truth
    WHERE split = :split
      AND case_key LIKE :case_prefix
    ORDER BY case_key
    """
)


def test_q1_dataset_history_returns_versions_and_matching_schema(
    db: Connection, case_key: str, base_time: datetime
) -> None:
    dataset = f"it_dataset_{case_key}"
    db.execute(
        text(
            """
            INSERT INTO meta.dataset_versions
                (dataset_name, version, event_time, recorded_at, row_count, metadata_json)
            VALUES
                (:dataset, 'v1', :t1, :t1, 10, CAST(:metadata AS jsonb)),
                (:dataset, 'v2', :t2, :t2, 14, CAST(:metadata AS jsonb))
            """
        ),
        {
            "dataset": dataset,
            "t1": base_time,
            "t2": base_time + timedelta(hours=1),
            "metadata": '{"source":"integration-test"}',
        },
    )
    db.execute(
        text(
            """
            INSERT INTO meta.schema_snapshots
                (dataset_name, schema_definition, fingerprint, captured_at)
            VALUES
                (:dataset, CAST(:schema AS jsonb), 'fp-v1', :t1),
                (:dataset, CAST(:schema AS jsonb), 'fp-v2', :t2)
            """
        ),
        {
            "dataset": dataset,
            "schema": '{"columns":[{"name":"id","type":"integer"}]}',
            "t1": base_time,
            "t2": base_time + timedelta(hours=1),
        },
    )

    rows = db.execute(Q1_DATASET_HISTORY, {"dataset_name": dataset}).mappings().all()

    assert [(row["version"], row["row_count"]) for row in rows] == [
        ("v1", 10),
        ("v2", 14),
    ]
    assert [row["fingerprint"] for row in rows] == ["fp-v1", "fp-v2"]
    assert rows[0]["schema_definition"]["columns"][0]["name"] == "id"


def test_q2_pipeline_tasks_returns_joined_execution_details(
    db: Connection, case_key: str, base_time: datetime
) -> None:
    pipeline_name = f"it_pipeline_{case_key}"
    pipeline_id = db.execute(
        text(
            """
            INSERT INTO meta.pipeline_runs
                (pipeline_name, status, started_at, finished_at, rows_in, rows_out)
            VALUES (:name, 'success', :started, :finished, 100, 95)
            RETURNING id
            """
        ),
        {
            "name": pipeline_name,
            "started": base_time,
            "finished": base_time + timedelta(minutes=5),
        },
    ).scalar_one()

    db.execute(
        text(
            """
            INSERT INTO meta.task_runs
                (pipeline_run_id, task_name, status, started_at, finished_at,
                 rows_in, rows_out)
            VALUES
                (:id, 'extract', 'success', :started, :finished, 100, 100),
                (:id, 'transform', 'success', :started, :finished, 100, 95)
            """
        ),
        {
            "id": pipeline_id,
            "started": base_time,
            "finished": base_time + timedelta(minutes=2),
        },
    )

    rows = db.execute(Q2_PIPELINE_TASKS, {"pipeline_name": pipeline_name}).mappings().all()

    assert len(rows) == 2
    assert {row["pipeline_status"] for row in rows} == {"success"}
    assert {row["pipeline_rows_in"] for row in rows} == {100}
    assert {row["task_name"]: (row["task_status"], row["task_rows_out"]) for row in rows} == {
        "extract": ("success", 100),
        "transform": ("success", 95),
    }


def test_q3_quality_failures_filters_out_passed_checks(
    db: Connection, case_key: str, base_time: datetime
) -> None:
    pipeline_name = f"it_quality_{case_key}"
    pipeline_id = db.execute(
        text(
            """
            INSERT INTO meta.pipeline_runs (pipeline_name, status, started_at)
            VALUES (:name, 'failed', :started)
            RETURNING id
            """
        ),
        {"name": pipeline_name, "started": base_time},
    ).scalar_one()

    db.execute(
        text(
            """
            INSERT INTO meta.quality_results
                (pipeline_run_id, rule_id, status, failed_rows, details)
            VALUES
                (:id, 'not_null_customer_id', 'failed', 3,
                 CAST(:failed_details AS jsonb)),
                (:id, 'unique_order_id', 'passed', 0,
                 CAST(:passed_details AS jsonb)),
                (:id, 'valid_order_total', 'error', 1,
                 CAST(:error_details AS jsonb))
            """
        ),
        {
            "id": pipeline_id,
            "failed_details": '{"column":"customer_id"}',
            "passed_details": "{}",
            "error_details": '{"reason":"unexpected type"}',
        },
    )

    rows = db.execute(Q3_QUALITY_FAILURES, {"pipeline_run_id": pipeline_id}).mappings().all()

    assert [(row["rule_id"], row["quality_status"], row["failed_rows"]) for row in rows] == [
        ("not_null_customer_id", "failed", 3),
        ("valid_order_total", "error", 1),
    ]
    assert all(row["pipeline_status"] == "failed" for row in rows)
    assert rows[0]["details"]["column"] == "customer_id"


def test_q4_incident_investigation_joins_evidence_and_lineage(
    db: Connection, case_key: str, base_time: datetime
) -> None:
    pipeline_id = db.execute(
        text(
            """
            INSERT INTO meta.pipeline_runs (pipeline_name, status, started_at)
            VALUES (:name, 'failed', :started)
            RETURNING id
            """
        ),
        {"name": f"it_incident_{case_key}", "started": base_time},
    ).scalar_one()
    incident_id = db.execute(
        text(
            """
            INSERT INTO meta.incidents
                (pipeline_run_id, title, severity, status, diagnosis, evidence)
            VALUES (:pipeline_id, :title, 'high', 'investigating', :diagnosis,
                    CAST(:evidence AS jsonb))
            RETURNING id
            """
        ),
        {
            "pipeline_id": pipeline_id,
            "title": f"Integration incident {case_key}",
            "diagnosis": "Unexpected row-count drop",
            "evidence": '{"source":"integration-test"}',
        },
    ).scalar_one()

    db.execute(
        text(
            """
            INSERT INTO meta.incident_evidence
                (incident_id, evidence_type, evidence_payload)
            VALUES (:incident_id, 'row_count_delta',
                    CAST(:payload AS jsonb))
            """
        ),
        {
            "incident_id": incident_id,
            "payload": '{"expected":100,"actual":72}',
        },
    )
    db.execute(
        text(
            """
            INSERT INTO meta.lineage_edges
                (source_dataset, target_dataset, pipeline_run_id, details)
            VALUES (:source, :target, :pipeline_id, CAST(:details AS jsonb))
            """
        ),
        {
            "source": f"raw_{case_key}",
            "target": f"silver_{case_key}",
            "pipeline_id": pipeline_id,
            "details": '{"transform":"clean_orders"}',
        },
    )

    rows = db.execute(Q4_INCIDENT_INVESTIGATION, {"incident_id": incident_id}).mappings().all()

    assert len(rows) == 1
    row = rows[0]
    assert row["title"] == f"Integration incident {case_key}"
    assert row["severity"] == "high"
    assert row["evidence_type"] == "row_count_delta"
    assert row["evidence_payload"] == {"expected": 100, "actual": 72}
    assert row["source_dataset"] == f"raw_{case_key}"
    assert row["target_dataset"] == f"silver_{case_key}"
    assert row["lineage_details"]["transform"] == "clean_orders"


def test_q5_evaluation_query_filters_by_split_and_case_prefix(
    db: Connection, case_key: str
) -> None:
    prefix = f"it-{case_key}-"
    db.execute(
        text(
            """
            INSERT INTO eval.incident_ground_truth
                (case_key, expected_incident, expected_category,
                 expected_diagnosis, split, labels)
            VALUES
                (:train_key, TRUE, 'schema_drift', 'Column type changed',
                 'train', CAST(:labels AS jsonb)),
                (:heldout_key, FALSE, NULL, NULL,
                 'held_out', CAST(:labels AS jsonb))
            """
        ),
        {
            "train_key": prefix + "train",
            "heldout_key": prefix + "heldout",
            "labels": '{"source":"integration-test"}',
        },
    )

    rows = (
        db.execute(
            Q5_EVALUATION_CASES,
            {"split": "held_out", "case_prefix": prefix + "%"},
        )
        .mappings()
        .all()
    )

    assert len(rows) == 1
    assert rows[0]["case_key"] == prefix + "heldout"
    assert rows[0]["expected_incident"] is False
    assert rows[0]["split"] == "held_out"
    assert rows[0]["labels"] == {"source": "integration-test"}


def test_evaluation_role_cannot_read_ground_truth() -> None:
    """Verify database permissions using a separately configured restricted role."""
    url = os.getenv("EVAL_RESTRICTED_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set EVAL_RESTRICTED_DATABASE_URL to a connection URL for the "
            "evaluation-restricted role to verify ground-truth read denial."
        )

    try:
        engine = _create_test_engine(url, "EVAL_RESTRICTED_DATABASE_URL")
    except ValueError as error:
        pytest.fail(str(error), pytrace=False)
    try:
        with engine.connect() as connection:
            with pytest.raises(DBAPIError) as exc_info:
                connection.execute(text("SELECT case_key FROM eval.incident_ground_truth LIMIT 1"))
            original = exc_info.value.orig
            sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
            assert sqlstate == "42501", (
                "Expected PostgreSQL insufficient_privilege (SQLSTATE 42501), "
                f"got SQLSTATE {sqlstate!r}: {original}"
            )
    finally:
        engine.dispose()
