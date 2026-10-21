# Steps 3–6: migration, contracts, ADRs, and recorded Olist observation

Verified on 2026-10-21 against the dedicated Compose PostgreSQL metadata service.

## Migration acceptance

`python scripts/dev.py test-migrations` passed. It creates an empty disposable
database, upgrades through all three revisions to `8d21c24a9b11`, downgrades to
base, verifies operational/evaluation schemas are absent, and upgrades again.
An additional sequence seeds integer pipeline/task/quality relationships at
revision `14901026eeb4`, migrates to UUIDs, reverses the conversion, checks the
original integer relationship, and upgrades again. Only the generated temporary
database is dropped. Existing metadata rows in the main service are retained.

The restricted-role test is run with EVAL_RESTRICTED_DATABASE_URL configured.
It can SELECT operational metadata and is denied ground truth with SQLSTATE
42501. This verifies the configured detector role, not arbitrary owner/admin
connections. Future detector/agent services must actually use that role.

## Contracts and checks

53 unit cases pass, including catalog resolution, generated-ID collisions,
minimum-volume behavior for empty/nonempty files, duplicate headers, composite
foreign keys, null semantics, missing/duplicate parent inputs, and centralized
status conversion. Logical-type enforcement remains deferred.

The seven core Olist CSVs were evaluated with actual reference inputs:

| Dataset | Rows | Result |
| --- | ---: | --- |
| customers | 99,441 | PASS |
| orders | 99,441 | PASS |
| order_items | 112,650 | PASS |
| order_payments | 103,886 | PASS |
| order_reviews | 99,224 | PASS |
| products | 32,951 | PASS |
| sellers | 3,095 | PASS |

The UCI CSV contract is validated structurally, including its documented keyless
identity policy. UCI data was not supplied/evaluated in this milestone.

## Durable real-data run

Pipeline UUID: `9767ff1f-ac44-4783-ac85-289111ffe3be`.

- Dataset: `olist_orders`, contract version 3, 99,441 observed rows.
- Persisted status: `success`; start/finish ordering was checked.
- Two completed UUID task runs: profile and quality.
- One table profile; schema snapshot and SHA-256 dataset version registered.
- Nine persisted `passed` quality results, each linked to the same run UUID.
- Customer-reference dependency registered in lineage.
- Real source unchanged across profiling/evaluation, checked using SHA-256.
- JSON artifact: `data/reports/recorded_olist_<uuid>.json` (ignored by Git).

The SQL constants used by the integration tests are shared with production
verification in `dataops/db/queries.py`:

| Query | Real-data result |
| --- | --- |
| Q1 | One source version and its captured schema |
| Q2 | Two successful tasks linked to the recorded run |
| Q3 | Zero failed/error checks |
| Q4 | Zero incidents for that actual run UUID |
| Q5 | Executed through the explicit evaluator connection; zero curated held-out cases |

Q3/Q4 emptiness is correct for the clean observed snapshot. Q5 emptiness is not
an evaluation score: the bridge never manufactures ground-truth labels from
quality output. Failure-path integration tests separately verify real failed
checks create incidents/evidence and source errors close the active run/task.
Those tests use temporary synthetic inputs, while the UUID above records real
Olist data and remains in the local database.

Ten query/permission/recording integration cases and one migration round-trip
case pass. Ruff lint, formatting, and mypy pass. This milestone does not deploy
MinIO, implement replay scheduling, or implement detectors/diagnosis. ADRs
0001–0005 document those decisions and implementation boundaries.
