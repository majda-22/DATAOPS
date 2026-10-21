"""Destructive acceptance checks restricted to a newly created disposable database."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from psycopg import sql
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

import dataops.db.models  # noqa: F401
from dataops.db.base import Base

ROOT = Path(__file__).resolve().parents[2]


def test_empty_upgrade_downgrade_upgrade_and_uuid_data_preservation():
    admin_url = os.getenv("MIGRATION_ADMIN_DATABASE_URL")
    if not admin_url:
        pytest.skip("Use make test-migrations to supply a dedicated PostgreSQL admin connection.")
    name = "migration_acceptance_" + uuid4().hex
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    target_url = make_url(admin_url).set(database=name)
    target = create_engine(target_url)
    env = dict(os.environ, DATABASE_URL=target_url.render_as_string(hide_password=False))

    def migrate(direction, revision):
        subprocess.run(
            [sys.executable, "-m", "alembic", direction, revision], cwd=ROOT, env=env, check=True
        )

    with admin.connect() as connection:
        connection.exec_driver_sql(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)).as_string()
        )
    try:
        # Empty database -> head -> base -> head is the acceptance sequence.
        migrate("upgrade", "head")
        assert set(Base.metadata.tables) <= {
            f"{schema}.{table}"
            for schema in ("meta", "eval")
            for table in inspect(target).get_table_names(schema=schema)
        }
        migrate("downgrade", "base")
        assert "meta" not in inspect(target).get_schema_names()
        assert "eval" not in inspect(target).get_schema_names()
        assert inspect(target).get_table_names() == ["alembic_version"]
        migrate("upgrade", "head")

        # Also prove existing integer relationships survive conversion and reversal.
        migrate("downgrade", "14901026eeb4")
        with target.begin() as connection:
            old_id = connection.execute(
                text("""INSERT INTO meta.pipeline_runs
                (pipeline_name,status,started_at) VALUES ('migration-preservation','success',now())
                RETURNING id""")
            ).scalar_one()
            connection.execute(
                text("""INSERT INTO meta.task_runs
                (pipeline_run_id,task_name,status) VALUES (:id,'preserved','success')"""),
                {"id": old_id},
            )
            connection.execute(
                text("""INSERT INTO meta.quality_results
                (pipeline_run_id,rule_id,status,failed_rows,details)
                VALUES (:id,'preserved','passed',0,'{}'::jsonb)"""),
                {"id": old_id},
            )
        migrate("upgrade", "head")
        with target.connect() as connection:
            row = connection.execute(
                text("""SELECT p.id,t.pipeline_run_id,t.id AS task_id
                FROM meta.pipeline_runs p JOIN meta.task_runs t ON t.pipeline_run_id=p.id
                WHERE p.legacy_id=:id"""),
                {"id": old_id},
            ).one()
            assert isinstance(row.id, UUID) and isinstance(row.task_id, UUID)
            assert row.id == row.pipeline_run_id
        migrate("downgrade", "14901026eeb4")
        with target.connect() as connection:
            assert (
                connection.execute(text("SELECT pipeline_run_id FROM meta.task_runs")).scalar_one()
                == old_id
            )
        migrate("upgrade", "head")
    finally:
        target.dispose()
        # The name is generated here, never supplied by a user or environment.
        assert name.startswith("migration_acceptance_") and len(name) == 53
        with admin.connect() as connection:
            connection.exec_driver_sql(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)).as_string()
            )
        admin.dispose()
