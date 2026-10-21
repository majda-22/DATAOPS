# Metadata Schema: Five Target Queries

These queries define the operational questions the metadata store must support.
They must be validated against the SQLAlchemy models and PostgreSQL schema.

## Q1 — Dataset history

Given a dataset name, retrieve all registered versions and their schema
fingerprints, ordered by version and capture time.

Required entities:
- dataset_versions
- schema_snapshots

Acceptance criteria:
- Multiple versions of one dataset can be retrieved.
- Schema changes can be identified using fingerprints.
- Results are ordered deterministically.

## Q2 — Pipeline and task execution

Given a pipeline run UUID, resolve its unique execution name and retrieve the pipeline status and every associated
task run, including task status, start time, finish time, and error information.

Required entities:
- pipeline_runs
- task_runs

Acceptance criteria:
- Tasks belong to the correct pipeline run.
- Failed tasks can be identified.
- Incomplete tasks remain distinguishable from completed tasks.

## Q3 — Data quality failures

Given a pipeline run ID, retrieve all quality results, their statuses,
failed-row counts, check details, and timestamps.

Required entities:
- pipeline_runs
- quality_results

Acceptance criteria:
- Failed checks can be filtered.
- Failed-row counts are available.
- Results can be traced to the relevant pipeline execution.

## Q4 — Incident investigation

Given an incident ID, retrieve its details, supporting evidence, and related
lineage edges so that the affected upstream and downstream datasets can
be investigated.

The shared query also accepts a pipeline-run UUID to investigate all incidents
for that actual execution, including the valid empty result for a clean run.

Required entities:
- incidents
- incident_evidence
- lineage_edges

Acceptance criteria:
- An incident can have multiple evidence records.
- Lineage can identify related datasets or tables.
- Missing evidence does not make the incident itself inaccessible.

## Q5 — Evaluation ground truth

Given an evaluation split, retrieve ground-truth labels and expected
diagnoses without requiring operational code to access evaluation labels.

Required entities:
- eval.incident_ground_truth
- meta.incidents

Acceptance criteria:
- Ground truth is stored in the eval schema.
- Records can be filtered by split.
- Operational tables do not have foreign keys to evaluation ground truth.
- Access restrictions are enforced separately through database permissions.

## Validation

For each query:
1. Write executable PostgreSQL SQL using the actual schema and column names.
2. Insert representative test records.
3. Execute the query against PostgreSQL.
4. Assert the returned records and important edge cases.
5. Add the query to the automated test suite.
