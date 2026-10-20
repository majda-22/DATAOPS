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

Record dataset versions, scenario IDs, random seeds, configuration,
predictions, and evaluation results.

## Consequences

- Results can be compared reproducibly across system versions.
- Access boundaries must be tested, not just documented.
- Hidden fault types can still be inadvertently leaked through
  configuration, logs, or shared artifacts.
- Synthetic faults measure performance on designed scenarios,
  not every possible real-world failure.