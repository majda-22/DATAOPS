# DataOps Detective

DataOps Detective is a data observability and root-cause diagnosis project.
Today it provides validated YAML contracts, CSV quality checks and profiling,
eleven PostgreSQL metadata tables, five tested metadata queries, a recorded Olist
observation bridge, and a local Delta Lake demonstration. Automated ingestion, Bronze/Silver/Gold processing,
anomaly detection, diagnosis, orchestration, and the API/dashboard remain planned.

## Requirements

- Python 3.11 or 3.12 (the verified Windows environment uses 3.11).
- Git and Docker with Docker Compose v2 for database integration tests.
- Java 21 on PATH for the pinned Spark 4.2.0 / Delta Spark 4.4.1 demonstration.
- Internet access for Python dependencies, the PostgreSQL image, and Delta JARs.
- GNU Make is optional; Python commands below work on Windows without it.

## Clone and install

```powershell
git clone https://github.com/majda-22/DATAOPS.git
cd DATAOPS
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[db,dev,spark]"
python -m pre_commit install
```

On Linux/macOS, use `python3.11 -m venv .venv` and `source .venv/bin/activate`.
The package supports optional `db`, `spark`, and `dev` extras; the commands above
install all three. Spark and Delta versions are pinned to the pair used by the
smoke test. PostgreSQL integration tests require the `db` extra.

## Development checks

```powershell
python scripts/dev.py lint
python scripts/dev.py test
python -m pre_commit run --all-files
```

`lint` runs Ruff lint, Ruff formatting verification, and mypy on the `dataops`
package. `test` runs unit tests without requiring Docker, Java, or source data.
Pre-commit runs the same lint/format checks and package type checks on commits.
The hooks use the activated environment; activate it before committing.

| Make target | Equivalent command |
| --- | --- |
| `make install` | `python -m pip install -e ".[db,dev,spark]"` followed by `python -m pre_commit install` |
| `make lint` | `python scripts/dev.py lint` |
| `make test` | `python scripts/dev.py test` |
| `make migrate` | `python scripts/dev.py migrate` |
| `make test-db` | `python scripts/dev.py test-db` |
| `make test-migrations` | `python scripts/dev.py test-migrations` |
| `make record-olist` | `python scripts/dev.py record-olist` |

Use `make PYTHON=...` if your Python executable has a different name.

## Start PostgreSQL and run every integration test

```powershell
python scripts/dev.py test-db
```

This starts the dedicated Compose PostgreSQL service, waits for readiness,
applies Alembic migrations, provisions a restricted role, and runs all six
integration tests, including ground-truth access denial. Test fixtures roll
back after each query test. The dedicated database remains running afterward.
The command does not use an inherited `DATABASE_URL` or modify another database.

Compose uses `127.0.0.1:55433` (container port 5432), database
`dataops_metadata_test`, user `dataops`, and the local-test password
`dataops_local_test`. These are development-only defaults. Override
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `TEST_POSTGRES_PORT`, and
`EVAL_TEST_PASSWORD` through exported environment variables if needed. Do not
reuse a production database. Do not use a `.env` override: this Python runner
reads process environment variables, while Compose alone would read `.env`.
Keep credentials consistent with an existing volume; changing an environment
variable does not change an already initialized PostgreSQL user's password.

To start only the service, inspect it, or stop it while keeping its volume:

```powershell
docker compose up -d --wait postgres-test
docker compose ps
docker compose down
```

For manual migration/testing in the same PowerShell session:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://dataops:dataops_local_test@127.0.0.1:55433/dataops_metadata_test'
python scripts/dev.py migrate
$env:TEST_DATABASE_URL = $env:DATABASE_URL
python -m pytest -v tests/integration/test_metadata_queries.py -k 'not evaluation_role'
```

Set `EVAL_RESTRICTED_DATABASE_URL` to an actual restricted-role connection to
run the permissions test manually; `test-db` handles this automatically.
Without connection variables, `python -m pytest` intentionally skips database
tests. Example credentials such as `USER` and `YOUR_TEST_DB` are rejected.
An older manually created `dataops-postgres-test` container on port 5433 can
still be tested with `scripts/test_metadata_queries.ps1`; it is separate from
this Compose service. Passwords with special characters must be URL-encoded.

## Download and inspect Olist

Download the **Brazilian E-Commerce Public Dataset by Olist** ZIP from
[Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
Kaggle may require an account and acceptance of its dataset terms. Keep the
source archive locally; datasets and generated reports are excluded from Git.

```powershell
python scripts/download_olist.py 'C:\path\to\archive.zip'
python scripts/inspect_olist.py
python scripts/profile_olist_orders.py
python scripts/run_olist_quality.py
```

The importer flattens CSV members into `data/raw/olist/`. The orders runners
write JSON under `data/reports/`. A missing source file is an input/setup error;
unit tests do not require a dataset download. Currently only orders has a
contract and dedicated runners in the original standalone workflow. The separate
recorded observation command below persists orders metadata to PostgreSQL.

## Delta Lake smoke test

Confirm Java is available with `java -version`. On Windows, provide compatible
Hadoop native binaries through `HADOOP_HOME`, or install the third-party build
used by this project:

```powershell
python scripts/setup_windows_hadoop.py
python scripts/delta_smoke_test.py
```

The setup helper downloads the zehelh/winutils Hadoop 3.4.2 release and checks
its pinned SHA-256 before extracting. Source and checksum are in the helper.
Linux/macOS do not need this Windows setup step.
The smoke test downloads Delta JARs into `.spark-ivy/` on first execution and
recreates only `data/delta_smoke/orders`. It checks writes, reads, partition
overwrite, and version-0 time travel. Windows may report a temporary-JAR cleanup
warning after successful assertions. This three-row demo is not a scale benchmark.

## Layout and architecture

- `dataops/contracts`, `quality`, `observability`: reusable validation/profiling.
- `dataops/db`, `migrations`: SQLAlchemy schema and Alembic revision history.
- `configs/datasets`: dataset contracts; `configs/spark`: Maven resolver settings.
- `tests/unit`, `tests/integration`: local checks and actual PostgreSQL queries.
- `docs/adr`, `docs/design`: architecture decisions and metadata query goals.

The metadata store separates `meta` operational tables from `eval` ground truth.
The restricted-role test checks SQLSTATE 42501 when querying evaluation labels.
See [metadata design](docs/design/metadata-schema.md) and
[target queries](docs/design/target-queries.md). The recorded observation command
below now wires Olist runs and reports into these metadata tables.

See the [clean-clone verification record](docs/design/clean-clone-verification.md)
for tested commands, results, and platform limitations.

## Migration acceptance and one recorded Olist run

After importing the Olist ZIP, use:

```powershell
python scripts/dev.py test-migrations
python scripts/dev.py record-olist
```

The first command creates its own empty, uniquely named PostgreSQL database and
checks upgrade-to-head, downgrade-to-base, and upgrade-to-head again. It also
seeds integer run relationships at the previous revision and verifies the UUID
migration and reversal preserve them. The temporary database is then dropped;
your configured metadata database is not downgraded or cleared.

The second command runs the integration tests (including restricted-role denial),
then records the actual orders CSV. It registers an immutable contract version,
creates a UUID run and UUID tasks, persists profile/schema/version/quality rows,
and closes the run with timestamps and a consistent status. Engine PASS/FAIL is
mapped to passed/failed in one module. Source SHA-256 identifies the snapshot.
Failure tests check that errors close the run and retain actual incident evidence.

Q1–Q5 SQL is shared by production verification and integration tests. Verification
uses the real run for Q1–Q4. Clean orders legitimately have no failed checks or
incidents. Q5 uses an explicitly configured evaluator connection and returns no
cases until curated labels exist; labels are never invented from check results.
The convenience command supplies the local database owner for this evaluator
connection. Detectors must use the separately tested read-only restricted role.

For a manually configured database, apply migrations, set DATABASE_URL and
optionally EVALUATION_DATABASE_URL, then run `python scripts/record_olist_run.py`.
Its JSON report is stored under `data/reports/recorded_olist_<uuid>.json`.

Eight [source contracts](docs/design/dataset-contracts.md) cover the seven core
Olist tables and a CSV export of UCI Online Retail. Foreign-key checks require
explicit parent CSV inputs; missing parents fail instead of silently skipping.
Logical-type enforcement remains deferred. ADRs 0001–0005 cover metadata,
Parquet/Delta on MinIO, Spark costs, replay clocks, ground-truth splits, and
run/status semantics; MinIO and replay scheduling are still future work.
