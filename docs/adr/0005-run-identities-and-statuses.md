# ADR 0005: Run identity, status vocabulary, and recording boundaries

- Status: Accepted
- Date: 2026-10-21

Pipeline/task IDs and all pipeline-run references use UUIDs. Preserve previous
integer IDs internally for reversible migration, as described in ADR 0001.
The bridge supplies its pipeline UUID to the quality engine, so a report and
its database execution cannot accidentally receive different run identifiers.

Keep the existing engine API's PASS/FAIL values. Translate exactly once through
`dataops.quality.status`: PASS -> passed, FAIL -> failed, WARNING -> warning,
ERROR -> error. Persist only these lowercase quality statuses. Pipeline and
task execution statuses remain pending/running/success/failed/cancelled (plus
skipped for tasks); passed/warning observations close successfully and failed/
error observations close as failed. Unsupported engine statuses are errors.

Commit the run and each running task before computation. Persist profile/schema
metadata before quality evaluation, and close the active task and run on an
exception. Record actual failed-check evidence as incidents; a clean observation
creates no synthetic incident. An observation's rows_out is its observed row
count, not an assertion that every row passed quality. A volume-rule failure
may legitimately have zero failed rows because missing rows cannot be sampled.

Contract definitions are immutable within (dataset, version). Registering a
changed definition requires a new version. Source hashes prevent a changed
input from being accepted as one consistent observation. The bridge is not an
orchestrator with crash recovery: an abruptly killed process may leave running
records, and a future reconciliation service must detect abandoned executions.
