# ADR 0003: Evaluation and Ground Truth Isolation

- Status: Accepted
- Date: 2026-10-20

## Context

A detector cannot be evaluated objectively if it can access the
answers used to score its predictions. Repeatedly tuning against
the same fault scenarios also creates optimistic results.

## Decision

Maintain a ground-truth registry separately from the operational
metadata consumed by detectors and the diagnosis agent.

Freeze the development, held-out, and out-of-domain evaluation
splits before detector implementation.

Begin with eight development fault types and reserve four fault
types for held-out evaluation. Use UCI Online Retail as an
out-of-domain dataset.

The evaluator may read ground truth; detectors and the agent may not.

Persist labels only in `eval.incident_ground_truth`. The detector test role has
read-only access to operational `meta` tables and no SELECT privilege on ground
truth. `make test-db` provisions this role, sets
`EVAL_RESTRICTED_DATABASE_URL`, and requires PostgreSQL SQLSTATE 42501 for a label
read. Schema separation and the absence of a foreign key alone are not proof
of access isolation. The application must actually use this restricted role
when detectors/agents are implemented; a database owner is not restricted.

`configs/evaluation/splits.yaml` defines protocol version 1: eight development
fault families use train/validation/test scenarios; four other families are
reserved for `held_out`. UCI Online Retail is reserved for out-of-domain checks.
This specifies the split policy, not generated scenarios or measured accuracy.
Fault injection and detector implementation remain future work. Change the
protocol version before changing the family allocation and record it in results.

The observation bridge never derives ground-truth labels from quality output.
Q5 is executed only through an explicitly supplied evaluator connection. On
real Olist data with no curated labels it correctly returns no cases, which
is query verification and not a detector-performance result.

Record dataset versions, scenario IDs, random seeds, configuration,
predictions, and evaluation results.

## Consequences

- Results can be compared reproducibly across system versions.
- Access boundaries must be tested, not just documented.
- Hidden fault types can still be inadvertently leaked through
  configuration, logs, or shared artifacts.
- Synthetic faults measure performance on designed scenarios,
  not every possible real-world failure.
