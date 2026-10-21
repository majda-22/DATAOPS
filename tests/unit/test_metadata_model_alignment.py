"""Keep new ORM tables consistent with the schema created by Alembic."""

from pathlib import Path
from unittest.mock import Mock

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, MetaData, Table
from sqlalchemy.dialects.postgresql import dialect

import dataops.db.models  # noqa: F401
from dataops.db.base import Base


def test_expanded_models_match_migration_constraints_defaults_and_nullability(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    revision = ScriptDirectory.from_config(config).get_revision("14901026eeb4").module
    migrated = MetaData(naming_convention=Base.metadata.naming_convention)
    operations = Mock()
    operations.create_table.side_effect = lambda name, *args, **kwargs: Table(
        name, migrated, *args, **kwargs
    )
    monkeypatch.setattr(revision, "op", operations)
    revision.upgrade()

    def server_default(column):
        if column.server_default is None:
            return None
        return str(column.server_default.arg.compile(dialect=dialect()))

    for name, expected in migrated.tables.items():
        actual = Base.metadata.tables[name]
        assert set(actual.columns.keys()) == set(expected.columns.keys()), name
        for column in expected.columns:
            orm_column = actual.c[column.name]
            assert orm_column.nullable == column.nullable, f"{name}.{column.name}"
            assert server_default(orm_column) == server_default(column), (
                f"Server default mismatch: {name}.{column.name}"
            )
        expected_checks = {
            (constraint.name, str(constraint.sqltext))
            for constraint in expected.constraints
            if isinstance(constraint, CheckConstraint)
        }
        actual_checks = {
            (constraint.name, str(constraint.sqltext))
            for constraint in actual.constraints
            if isinstance(constraint, CheckConstraint)
        }
        assert actual_checks == expected_checks, name
