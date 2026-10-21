# ADR 0004: Simulated-time replay and source identity

- Status: Accepted
- Date: 2026-10-21

## Decision

Replay uses an injected UTC event clock rather than wall-clock "now" to decide
freshness, late arrivals, or detector windows. Order records deterministically by
event timestamp, source snapshot SHA-256, and original row ordinal as a tie-break.
Define the source timezone explicitly when a dataset supplies naive timestamps;
never infer it from the execution machine. Keep cancellations and missing values
in Bronze; cleaning belongs to documented transformations.

Store event time separately from observation/recording time and execution
started/finished timestamps. Use the source SHA-256 as dataset-version identity,
record contract version and scenario seed, and retain the referenced Delta
versions under ADR 0002. Identical inputs may produce multiple UUID executions
while retaining one source dataset version. UUIDs are identifiers, not ordering.

## Implementation boundary

The metadata schema and recording API support timezone-aware `event_time`.
Without an injected event time the bridge explicitly records observation time
in dataset-version metadata; it does not pretend to replay historical Olist
events. Replay scheduling, injected detector clocks, and time-window evaluation
are planned and must be tested before freshness/detection claims are made.

## Costs and alternatives

An injected clock requires every time-dependent detector to accept a clock and
requires stable source manifests. Wall-clock sleeps would make evaluation slow,
machine-dependent, and irreproducible. Event ordering alone does not simulate
processing delays; arrival-time scenarios need a separate explicit schedule.
