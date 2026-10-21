# PostgreSQL integration tests

`python scripts/dev.py test-db` starts the dedicated Compose service, applies
all migrations, configures the operational-read-only role, and runs the query,
permission, and recording-lifecycle tests. Use `python scripts/dev.py test-migrations`
for the empty-database upgrade/downgrade/upgrade acceptance sequence. It creates
and drops only a uniquely named disposable database and also verifies legacy
integer relationships survive UUID conversion and reversal.

For the existing `dataops-postgres-test` Docker container, run from Project:

```powershell
.\scripts\test_metadata_queries.ps1
```

This reads the container's configured credentials without printing them and uses
its published port (currently **5433**, not 5432). It also sets TEST_DATABASE_URL
in the current PowerShell process, so the original pytest command can run afterward.
It does not apply migrations or start the container.

Use a running PostgreSQL server and a dedicated test database. The strings
`USER`, `PASSWORD`, and `YOUR_TEST_DB` are examples, not working credentials.
The tests insert fixtures in transactions and roll them back. They do not
start PostgreSQL, create a database, or run migrations automatically.

From Project, in the activated virtual environment:

1. Set `TEST_DATABASE_URL` to the real connection URL for your dedicated database.
   Use the format `postgresql+psycopg://username:password@host:port/database`.
   URL-encode special characters in credentials.
2. Check the actual host and port, for example:

   ```powershell
   Test-NetConnection 127.0.0.1 -Port 5432
   ```

   If this fails, start the PostgreSQL service/container or correct the address
   and published port before running pytest.
3. Apply migrations to that dedicated database and run the tests:

   ```powershell
   $env:DATABASE_URL = $env:TEST_DATABASE_URL
   python -m alembic upgrade head
   python -m pytest -v tests/integration/test_metadata_queries.py
   ```

The optional permissions test also needs `EVAL_RESTRICTED_DATABASE_URL` for a
separate role that cannot SELECT from `eval.incident_ground_truth`. Without it,
that one test skips. Do not use the database owner for the restricted-role URL.

Connection attempts use a five-second timeout per address. Explicitly configured
but invalid/unreachable databases fail; they are not reported as passing tests.
