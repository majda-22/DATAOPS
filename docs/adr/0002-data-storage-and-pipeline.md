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

Use Parquet for analytical data, MinIO as the planned
S3-compatible object store, and PostgreSQL for operational
metadata.

Use Airflow to orchestrate repeatable pipeline runs.

Use the same quality-engine interface for all processing
workloads, with Spark-backed implementations for data profiling
and transformation.

## Consequences

- One primary processing framework across all datasets.
- Spark execution plans and distributed processing can be
  evaluated from the beginning.
- Even small datasets incur Spark startup and execution overhead.
- Local Spark development requires compatible Java and Python
  environments.
- Distributed execution introduces serialization, partitioning,
  shuffle, and memory-management concerns.
- NYC TLC remains the scale benchmark; using Spark alone does
  not prove that the pipeline scales efficiently.

## Alternatives considered

- pandas first, then PySpark: simpler initial development,
  but requires a later migration and duplicate implementations.
- PySpark throughout: selected for consistency and for the
  project's distributed-processing objectives.