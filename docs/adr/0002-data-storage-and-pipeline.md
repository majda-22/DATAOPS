# ADR 0002: Data Storage and Pipeline Architecture

- Status: Accepted
- Date: 2026-10-20

## Context

DataOps Detective needs reproducible ingestion, traceable
transformations, data quality checks, and analytical storage
across datasets of different sizes.

Using pandas initially and migrating to Spark later would
introduce two processing implementations and additional
maintenance and testing costs.

## Decision

Use PySpark as the primary data processing engine from the
beginning, including for the Olist pipeline.

Adopt a Bronze / Silver / Gold architecture:

- Bronze preserves ingested source data and records its manifest.
- Silver applies documented transformations, validates data,
  and quarantines rejected records with reason codes.
- Gold produces business-oriented datasets and metrics.

Use Delta tables for mutable Silver/Gold analytical datasets: their data files
are Parquet, accompanied by `_delta_log` transaction history. Use plain Parquet
for immutable snapshots and interchange/export. Preserve the original Bronze
source snapshot and its SHA-256 manifest. MinIO is the selected S3-compatible
deployment target; PostgreSQL stores operational metadata, not analytical rows.

Delta is selected because atomic commits, selective partition replacement, and
versioned reads support replay and investigation. Pin the demonstrated local
pair, PySpark 4.2.0 / Delta Spark 4.4.1. Keep one orchestrated writer per table
until object-store concurrent-write behavior has an explicit tested protocol.
Delta history retention/VACUUM must retain every version required by a replay;
time travel does not replace a source-data backup.

Use Airflow to orchestrate repeatable pipeline runs.

Use the same quality-engine interface for all processing
workloads, with Spark-backed implementations for data profiling
and transformation.

Implementation boundary: local Delta write/read/partition-overwrite/time-travel
is demonstrated. MinIO, Airflow, and the Spark Bronze/Silver/Gold pipeline remain
planned. The CSV profiler/quality engine and recorded-run bridge are a bounded
bootstrap/reference adapter, not a pandas pipeline or a claim of distributed
execution. Production table processing uses Spark from its first implementation;
there is no later pandas-to-Spark migration planned. The contract model accepts
`delta`, but the CSV engine explicitly accepts only `csv`.

## Consequences

- One primary processing framework across all datasets.
- Spark execution plans and distributed processing can be
  evaluated from the beginning.
- Even small datasets incur Spark startup and execution overhead.
- Delta adds transaction-log operations, small-file management, retention policy,
  and object-store integration testing. MinIO deployment is not established by
  a successful local-filesystem smoke test.
- Local Spark development requires compatible Java and Python
  environments.
- Distributed execution introduces serialization, partitioning,
  shuffle, and memory-management concerns.
- NYC TLC remains the scale benchmark; using Spark alone does
  not prove that the pipeline scales efficiently.

## Alternatives considered

- Plain Parquet only: simpler file interchange, but no Delta transaction history
  or transactional partition replacement. Retained for immutable snapshots and
  exports; Delta is selected for mutable analytical tables.

- pandas first, then PySpark: simpler initial development,
  but requires a later migration and duplicate implementations.
- PySpark throughout: selected for consistency and for the
  project's distributed-processing objectives.
