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
