"""Cross-platform development commands; Make is an optional convenience."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def module(*args: str) -> None:
    run(sys.executable, "-m", *args)


def database_url(database: str, username: str, password_variable: str):
    """Build a connection URL from the project's .env file."""
    from dotenv import dotenv_values
    from sqlalchemy.engine import URL

    settings = dotenv_values(ROOT / ".env")
    password = settings.get(password_variable)
    if not password:
        raise RuntimeError(f"Set {password_variable} in .env")

    return URL.create(
        "postgresql+psycopg",
        username=username,
        password=password,
        host="127.0.0.1",
        port=int(settings.get("SHARED_POSTGRES_PORT") or "55432"),
        database=database,
    )


def metadata_database() -> None:
    """Select the real metadata database for application commands."""
    url = database_url("dataops_metadata", "dataops", "METADATA_DB_PASSWORD")
    os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)


def test_database() -> None:
    """Migrate the test database and verify normal and restricted access."""
    from dotenv import dotenv_values
    from psycopg import sql
    from sqlalchemy import create_engine

    run("docker", "compose", "up", "-d", "--wait", "postgres")

    url = database_url("dataops_metadata_test", "dataops_test", "METADATA_TEST_DB_PASSWORD")
    admin_url = database_url("postgres", "platform_admin", "SHARED_POSTGRES_ADMIN_PASSWORD")

    os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
    os.environ["TEST_DATABASE_URL"] = os.environ["DATABASE_URL"]
    os.environ["MIGRATION_ADMIN_DATABASE_URL"] = admin_url.render_as_string(hide_password=False)

    # Prove that the test database owner can run application migrations.
    module("alembic", "upgrade", "head")

    settings = dotenv_values(ROOT / ".env")
    restricted_password = settings.get("EVAL_TEST_PASSWORD")
    if not restricted_password:
        raise RuntimeError("Set EVAL_TEST_PASSWORD in .env")

    # Role administration requires admin privileges. Schema grants must
    # execute in the test database, where those schemas exist.
    engine = create_engine(admin_url.set(database=url.database))
    try:
        with engine.begin() as connection:
            if not connection.exec_driver_sql(
                "SELECT 1 FROM pg_roles WHERE rolname = 'dataops_restricted'"
            ).scalar():
                connection.exec_driver_sql("CREATE ROLE dataops_restricted")

            statement = sql.SQL(
                "ALTER ROLE dataops_restricted WITH LOGIN NOSUPERUSER "
                "NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD {}"
            ).format(sql.Literal(restricted_password))
            connection.exec_driver_sql(statement.as_string())

            connection.exec_driver_sql(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO dataops_restricted")
                .format(sql.Identifier(url.database))
                .as_string()
            )
            connection.exec_driver_sql("GRANT USAGE ON SCHEMA eval TO dataops_restricted")
            connection.exec_driver_sql("GRANT USAGE ON SCHEMA meta TO dataops_restricted")
            connection.exec_driver_sql(
                "GRANT SELECT ON ALL TABLES IN SCHEMA meta TO dataops_restricted"
            )
            connection.exec_driver_sql(
                "REVOKE ALL ON eval.incident_ground_truth FROM dataops_restricted"
            )
    finally:
        engine.dispose()

    os.environ["EVAL_RESTRICTED_DATABASE_URL"] = url.set(
        username="dataops_restricted", password=restricted_password
    ).render_as_string(hide_password=False)

    module(
        "pytest",
        "-v",
        "tests/integration/test_metadata_queries.py",
        "tests/integration/test_recorded_run.py",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["lint", "test", "migrate", "test-db", "test-migrations", "record-olist"]
    )
    args = parser.parse_args()
    if args.command == "lint":
        module("ruff", "check", ".")
        module("ruff", "format", "--check", ".")
        module("mypy")
    elif args.command == "test":
        module("pytest", "-v", "tests/unit")
    elif args.command == "migrate":
        metadata_database()
        module("alembic", "upgrade", "head")
    elif args.command == "test-db":
        test_database()
    elif args.command == "test-migrations":
        test_database()
        module("pytest", "-v", "tests/integration/test_migration_roundtrip.py")
    else:
        metadata_database()
        os.environ["EVALUATION_DATABASE_URL"] = os.environ["DATABASE_URL"]
        run(sys.executable, "scripts/record_olist_run.py")


if __name__ == "__main__":
    main()
