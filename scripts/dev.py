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


def test_database() -> None:
    """Start the dedicated Compose database, migrate it, and test both roles."""
    from psycopg import sql
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL

    run("docker", "compose", "up", "-d", "--wait", "postgres-test")
    url = URL.create(
        "postgresql+psycopg",
        username=os.getenv("POSTGRES_USER", "dataops"),
        password=os.getenv("POSTGRES_PASSWORD", "dataops_local_test"),
        host="127.0.0.1",
        port=int(os.getenv("TEST_POSTGRES_PORT", "55433")),
        database=os.getenv("POSTGRES_DB", "dataops_metadata_test"),
    )
    # This command always targets the dedicated Compose database, never DATABASE_URL.
    os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
    os.environ["TEST_DATABASE_URL"] = os.environ["DATABASE_URL"]
    module("alembic", "upgrade", "head")
    engine = create_engine(url)
    restricted_password = os.getenv("EVAL_TEST_PASSWORD", "restricted_local_test")
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
            connection.exec_driver_sql(
                "REVOKE ALL ON eval.incident_ground_truth FROM dataops_restricted"
            )
    finally:
        engine.dispose()
    os.environ["EVAL_RESTRICTED_DATABASE_URL"] = url.set(
        username="dataops_restricted", password=restricted_password
    ).render_as_string(hide_password=False)
    module("pytest", "-v", "tests/integration/test_metadata_queries.py")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["lint", "test", "migrate", "test-db"])
    args = parser.parse_args()
    if args.command == "lint":
        module("ruff", "check", ".")
        module("ruff", "format", "--check", ".")
        module("mypy")
    elif args.command == "test":
        module("pytest", "-v", "tests/unit")
    elif args.command == "migrate":
        if not os.getenv("DATABASE_URL"):
            parser.error("Set DATABASE_URL to the database you intend to migrate.")
        module("alembic", "upgrade", "head")
    else:
        test_database()


if __name__ == "__main__":
    main()
