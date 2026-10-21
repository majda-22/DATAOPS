# Metadata Schema Design

Status: Implementation plan

## 1. PostgreSQL schemas

- `meta`: operational metadata.
- `eval`: evaluation data and held-out ground truth.

## 2. Operational tables (`meta`)

1. `dataset_contracts` — versioned dataset contracts.
2. `dataset_versions` — observed dataset versions and simulated event time.
3. `schema_snapshots` — historical schema definitions and fingerprints.
4. `pipeline_runs` — pipeline execution history.
5. `task_runs` — individual task execution history.
6. `quality_results` — quality rule outcomes.
7. `table_profiles` — historical table-level statistics.
8. `lineage_edges` — upstream/downstream dataset dependencies.
9. `incidents` — detected data incidents.
10. `incident_evidence` — evidence linked to incidents and runs.

## 3. Evaluation table (`eval`)

11. `incident_ground_truth` — expected incident labels and diagnoses, isolated from operational queries.

## 4. Design rules

- Preserve the existing initial migration.
- Use PostgreSQL-native UUIDs for new run and incident identifiers only after defining a safe migration strategy for existing integer IDs.
- Use `JSONB` for flexible PostgreSQL metadata.
- Store timestamps in UTC and distinguish event time from ingestion/recording time.
- Enforce valid statuses, nonnegative row counts, and appropriate foreign keys.
- Add indexes for run history, dataset history, incident lookup, and lineage traversal.
- Restrict evaluation ground truth through database permissions.
- Keep held-out evaluation data inaccessible to operational diagnosis queries.

## 5. Acceptance criteria

- All eleven tables exist in the intended schemas.
- Upgrade and downgrade work on a disposable PostgreSQL database.
- Tests verify constraints, foreign keys, and all five target queries.
- Existing migration history remains intact.
