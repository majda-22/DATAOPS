"""Validate migration history and PostgreSQL DDL without a running server."""

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def migration_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=StringIO())
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    return config


def test_revision_identifiers_match_migration_filenames():
    scripts = ScriptDirectory.from_config(migration_config())
    for revision in scripts.walk_revisions():
        assert Path(revision.path).name.startswith(revision.revision + "_")


def test_pipeline_event_time_is_migrated_in_both_directions(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://offline@localhost/offline")
    config = migration_config()
    command.upgrade(config, "head", sql=True)
    upgrade_sql = config.output_buffer.getvalue()
    assert (
        "ALTER TABLE meta.pipeline_runs ADD COLUMN event_time TIMESTAMP WITH TIME ZONE"
        in upgrade_sql
    )
    assert "<NEW_REVISION_ID>" not in upgrade_sql

    config.output_buffer = StringIO()
    command.downgrade(config, "14901026eeb4:fc3c089e6bc9", sql=True)
    downgrade_sql = config.output_buffer.getvalue()
    assert "ALTER TABLE meta.pipeline_runs DROP COLUMN event_time" in downgrade_sql
