# ADR 0001: Metadata Store

- Status: Accepted
- Date: 2026-10-20

## Context

DataOps Detective must persist pipeline runs, task executions,
dataset profiles, schema snapshots, quality results, lineage,
incidents, and evidence. These records need reliable relationships,
constraints, and queries.

## Decision

Use PostgreSQL as the authoritative metadata store.

Use stable identifiers and foreign keys to link records. Store
timestamps consistently in UTC. Use JSONB only for flexible
attributes that do not require a dedicated relational structure.

Pipeline and task run identifiers are PostgreSQL UUIDs, generated once per
execution and shared with engine reports. Revision `8d21c24a9b11` migrates the
integer IDs and every pipeline-run foreign key. Internal integer `legacy_id`
columns retain their sequences so a downgrade preserves records created before
or after conversion. They are compatibility fields, not public run identifiers.

The CSV observation bridge persists contracts, dataset versions, schema
snapshots, profiles, tasks, quality results, and real failure incidents. JSON
reports are supplementary artifacts. Operational data lives in `meta`; curated
ground truth lives in `eval` and is read through a separate evaluator connection.
See ADRs 0003–0005 for access, clock, identity, and status semantics.

## Consequences

- Relational constraints help preserve metadata integrity.
- SQL supports incident investigation and evaluation queries.
- Schema changes require versioned database migrations.
- PostgreSQL adds an infrastructure dependency.

## Alternatives considered

- SQLite: simpler local setup, but less representative of the
  intended multi-service architecture.
- Files alone: insufficient for relational queries and concurrent
  metadata writes.
