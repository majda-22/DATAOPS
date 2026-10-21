"""Parameterized investigation queries shared by runners and integration tests."""

from sqlalchemy import text

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
    WHERE (CAST(:incident_id AS integer) IS NULL OR i.id = :incident_id)
      AND (CAST(:pipeline_run_id AS uuid) IS NULL OR i.pipeline_run_id = :pipeline_run_id)
    ORDER BY e.id, le.id
    """
).bindparams(incident_id=None, pipeline_run_id=None)

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
