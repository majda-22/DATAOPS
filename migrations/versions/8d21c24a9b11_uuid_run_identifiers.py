"""Use UUID pipeline/task identifiers while preserving reversible integer identities."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "8d21c24a9b11"
down_revision = "14901026eeb4"
branch_labels = None
depends_on = None

REFERENCES = {
    "task_runs": "CASCADE",
    "quality_results": "CASCADE",
    "table_profiles": "SET NULL",
    "lineage_edges": "SET NULL",
    "incidents": "SET NULL",
}


def drop_run_foreign_keys() -> None:
    # Names from historical migrations are discovered, not guessed or regenerated.
    op.execute("""DO $$ DECLARE item record; BEGIN
        FOR item IN SELECT c.conname, r.relname FROM pg_constraint c
          JOIN pg_class r ON r.oid = c.conrelid
          JOIN pg_namespace n ON n.oid = r.relnamespace
          WHERE c.contype = 'f' AND c.confrelid = 'meta.pipeline_runs'::regclass
            AND n.nspname = 'meta'
            AND r.relname IN ('task_runs','quality_results','table_profiles','lineage_edges','incidents')
        LOOP EXECUTE format('ALTER TABLE meta.%I DROP CONSTRAINT %I', item.relname, item.conname);
        END LOOP; END $$""")


def recreate_run_foreign_keys(*, downgrading: bool = False) -> None:
    for table, action in REFERENCES.items():
        op.create_foreign_key(
            f"fk_{table}_pipeline_run_id_pipeline_runs",
            table,
            "pipeline_runs",
            ["pipeline_run_id"],
            ["id"],
            source_schema="meta",
            referent_schema="meta",
            ondelete=None if downgrading and table in {"quality_results", "incidents"} else action,
        )


def upgrade() -> None:
    drop_run_foreign_keys()
    for table in ("pipeline_runs", "task_runs"):
        op.drop_constraint(f"pk_{table}", table, schema="meta", type_="primary")
        op.alter_column(table, "id", new_column_name="legacy_id", schema="meta")
        op.create_unique_constraint(f"uq_{table}_legacy_id", table, ["legacy_id"], schema="meta")
        op.add_column(
            table,
            sa.Column(
                "id",
                UUID(as_uuid=True),
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            schema="meta",
        )
        op.create_primary_key(f"pk_{table}", table, ["id"], schema="meta")
    for table in REFERENCES:
        op.add_column(table, sa.Column("pipeline_run_uuid", UUID(as_uuid=True)), schema="meta")
        op.execute(
            f"UPDATE meta.{table} AS child SET pipeline_run_uuid = parent.id "
            f"FROM meta.pipeline_runs AS parent WHERE child.pipeline_run_id = parent.legacy_id"
        )
        op.drop_column(table, "pipeline_run_id", schema="meta")
        op.alter_column(
            table,
            "pipeline_run_uuid",
            new_column_name="pipeline_run_id",
            nullable=table not in {"task_runs", "quality_results"},
            schema="meta",
        )
    # Dropping the old reference column drops indexes on it as well.
    for table, name in (
        ("task_runs", "ix_task_runs_pipeline"),
        ("quality_results", "ix_quality_results_run"),
    ):
        op.create_index(name, table, ["pipeline_run_id"], schema="meta")
    recreate_run_foreign_keys()


def downgrade() -> None:
    drop_run_foreign_keys()
    for table in REFERENCES:
        op.add_column(table, sa.Column("pipeline_run_integer", sa.Integer()), schema="meta")
        op.execute(
            f"UPDATE meta.{table} AS child SET pipeline_run_integer = parent.legacy_id "
            f"FROM meta.pipeline_runs AS parent WHERE child.pipeline_run_id = parent.id"
        )
        op.drop_column(table, "pipeline_run_id", schema="meta")
        op.alter_column(
            table,
            "pipeline_run_integer",
            new_column_name="pipeline_run_id",
            nullable=table not in {"task_runs", "quality_results"},
            schema="meta",
        )
    for table in ("pipeline_runs", "task_runs"):
        op.drop_constraint(f"pk_{table}", table, schema="meta", type_="primary")
        op.drop_column(table, "id", schema="meta")
        op.drop_constraint(f"uq_{table}_legacy_id", table, schema="meta", type_="unique")
        op.alter_column(table, "legacy_id", new_column_name="id", schema="meta")
        op.create_primary_key(f"pk_{table}", table, ["id"], schema="meta")
    for table, name in (
        ("task_runs", "ix_task_runs_pipeline"),
        ("quality_results", "ix_quality_results_run"),
    ):
        op.create_index(name, table, ["pipeline_run_id"], schema="meta")
    recreate_run_foreign_keys(downgrading=True)
