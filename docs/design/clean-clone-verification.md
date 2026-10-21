# Clean-clone verification — 2026-10-21

The repository was pushed to `https://github.com/majda-22/DATAOPS.git`, then
cloned from GitHub into a separate `fresh-validation` directory. A new Python
3.11 virtual environment was created there; the original environment was not
reused. Pip installed `.[db,dev,spark]`, including PySpark 4.2.0 and Delta Spark
4.4.1. Cached dependency downloads were allowed, but no installed packages,
Hadoop binaries, or project-local JAR caches were copied from the working tree.

## Results

| Command / capability | Result |
| --- | --- |
| `make install` | Editable installation and Git hook installation succeeded |
| `make lint` | Ruff lint, formatting check, and mypy passed |
| `make test` | 39 unit tests passed |
| `make test-db` | 6 integration tests passed, including restricted-role denial |
| `make migrate` | Succeeded at migration head `14901026eeb4` |
| `python -m pre_commit run --all-files` | All three hooks passed |
| Windows Hadoop setup helper | Download and pinned SHA-256 verification succeeded |
| Olist ZIP importer | Imported 9 CSV files from the existing local snapshot |
| Olist inspection / profiling / quality scripts | Completed; 99,441 orders; all 7 quality checks passed |
| Delta smoke test | Write/read, partition overwrite, version-0 time travel, and final row count passed |

GNU Make was run through the `gmake.exe` bundled with Strawberry Perl because
`make` was not on this Windows machine's PATH. The cross-platform Python command
runner remains the documented alternative.

The fresh database used a separate Compose project and a new volume on port
55434. Both Alembic revisions ran against an empty database. The restricted
test role was provisioned automatically. The default developer service on port
55433 was also tested independently.

## Limits and observed environment issues

- Olist acquisition from Kaggle was documented but not authenticated or downloaded
  anew. The import path was tested with a ZIP made from the user's existing nine
  CSVs. A fresh user still needs to obtain the dataset under its terms.
- Dependency and Git downloads required network access outside the agent sandbox.
  A sandboxed failure to reach a package registry was not treated as a code failure.
- Windows Spark logs can include startup heartbeat messages and failure to delete
  a temporary Snappy JAR during shutdown. The Delta assertions completed. Those
  native-runtime messages are not suppressed by the demo.
  Direct subprocess checks confirmed exit code 0 for the Delta smoke test,
  `make migrate`, and `make test-db`; PowerShell's redirected-stderr error
  records were not used as the process exit status.
- The run validates one Windows/Python 3.11 environment, not a Linux or Python
  3.12 compatibility matrix. The three-row Delta demo is not a scale test.

Source-data reports and dependency/runtime caches remain ignored by Git.
