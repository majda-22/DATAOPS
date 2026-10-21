"""Expand metadata schema and add evaluation tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "14901026eeb4"
down_revision = "fc3c089e6bc9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create separate operational and evaluation namespaces.
    op.execute("CREATE SCHEMA meta")
    op.execute("CREATE SCHEMA eval")

    # Move existing tables without copying or dropping their data.
    for table in (
        "dataset_contracts",
        "pipeline_runs",
        "quality_results",
        "incidents",
    ):
        op.execute(f'ALTER TABLE public."{table}" SET SCHEMA meta')

    op.add_column(
        "pipeline_runs",
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=True),
        schema="meta",
    )

    # Convert existing JSON values to PostgreSQL JSONB.
    op.alter_column(
        "dataset_contracts",
        "contract_definition",
        schema="meta",
        existing_type=sa.JSON(),
        type_=postgresql.JSONB(),
        postgresql_using="contract_definition::jsonb",
    )
    op.alter_column(
        "quality_results",
        "details",
        schema="meta",
        existing_type=sa.JSON(),
        type_=postgresql.JSONB(),
        postgresql_using="details::jsonb",
    )
    op.alter_column(
        "incidents",
        "evidence",
        schema="meta",
        existing_type=sa.JSON(),
        type_=postgresql.JSONB(),
        postgresql_using="evidence::jsonb",
    )

    # Operational execution constraints.
    op.create_check_constraint(
        "ck_pipeline_runs_status",
        "pipeline_runs",
        "status IN ('pending', 'running', 'success', 'failed', 'cancelled')",
        schema="meta",
    )
    op.create_check_constraint(
        "ck_pipeline_rows_in",
        "pipeline_runs",
        "rows_in IS NULL OR rows_in >= 0",
        schema="meta",
    )
    op.create_check_constraint(
        "ck_pipeline_rows_out",
        "pipeline_runs",
        "rows_out IS NULL OR rows_out >= 0",
        schema="meta",
    )
    op.create_check_constraint(
        "ck_pipeline_finished_after_started",
        "pipeline_runs",
        "finished_at IS NULL OR finished_at >= started_at",
        schema="meta",
    )
    op.create_check_constraint(
        "ck_quality_results_status",
        "quality_results",
        "status IN ('passed', 'failed', 'warning', 'error')",
        schema="meta",
    )
    op.create_check_constraint(
        "ck_quality_failed_rows",
        "quality_results",
        "failed_rows >= 0",
        schema="meta",
    )
    op.create_check_constraint(
        "ck_incidents_severity",
        "incidents",
        "severity IN ('low', 'medium', 'high', 'critical')",
        schema="meta",
    )
    op.create_check_constraint(
        "ck_incidents_status",
        "incidents",
        "status IN ('open', 'investigating', 'resolved', 'dismissed')",
        schema="meta",
    )

    # Additional operational tables.
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_name", sa.String(150), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("row_count", sa.Integer()),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.UniqueConstraint("dataset_name", "version", name="uq_dataset_version"),
        sa.CheckConstraint(
            "row_count IS NULL OR row_count >= 0",
            name="ck_dataset_version_row_count",
        ),
        schema="meta",
    )
    op.create_index(
        "ix_dataset_versions_event_time",
        "dataset_versions",
        ["event_time"],
        schema="meta",
    )

    op.create_table(
        "schema_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_name", sa.String(150), nullable=False),
        sa.Column("schema_definition", postgresql.JSONB(), nullable=False),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="meta",
    )
    op.create_index(
        "ix_schema_snapshots_dataset_time",
        "schema_snapshots",
        ["dataset_name", "captured_at"],
        schema="meta",
    )

    op.create_table(
        "task_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "pipeline_run_id",
            sa.Integer(),
            sa.ForeignKey("meta.pipeline_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_name", sa.String(150), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("rows_in", sa.Integer()),
        sa.Column("rows_out", sa.Integer()),
        sa.Column("error_message", sa.Text()),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed', 'skipped', 'cancelled')",
            name="ck_task_runs_status",
        ),
        sa.CheckConstraint(
            "rows_in IS NULL OR rows_in >= 0",
            name="ck_task_rows_in",
        ),
        sa.CheckConstraint(
            "rows_out IS NULL OR rows_out >= 0",
            name="ck_task_rows_out",
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="ck_task_finished_after_started",
        ),
        schema="meta",
    )
    op.create_index(
        "ix_task_runs_pipeline",
        "task_runs",
        ["pipeline_run_id"],
        schema="meta",
    )

    op.create_index(
        "ix_pipeline_runs_name_started",
        "pipeline_runs",
        ["pipeline_name", "started_at"],
        schema="meta",
    )
    op.create_index(
        "ix_quality_results_run",
        "quality_results",
        ["pipeline_run_id"],
        schema="meta",
    )
    op.create_index(
        "ix_incidents_status_created",
        "incidents",
        ["status", "created_at"],
        schema="meta",
    )

    op.create_table(
        "table_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_name", sa.String(150), nullable=False),
        sa.Column(
            "pipeline_run_id",
            sa.Integer(),
            sa.ForeignKey("meta.pipeline_runs.id", ondelete="SET NULL"),
        ),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("column_profiles", postgresql.JSONB(), nullable=False),
        sa.Column(
            "profiled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("row_count >= 0", name="ck_table_profiles_row_count"),
        schema="meta",
    )
    op.create_index(
        "ix_table_profiles_dataset_time",
        "table_profiles",
        ["dataset_name", "profiled_at"],
        schema="meta",
    )

    op.create_table(
        "lineage_edges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_dataset", sa.String(150), nullable=False),
        sa.Column("target_dataset", sa.String(150), nullable=False),
        sa.Column(
            "pipeline_run_id",
            sa.Integer(),
            sa.ForeignKey("meta.pipeline_runs.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "details",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.UniqueConstraint(
            "source_dataset",
            "target_dataset",
            name="uq_lineage_source_target",
        ),
        sa.CheckConstraint(
            "source_dataset <> target_dataset",
            name="ck_lineage_not_self",
        ),
        schema="meta",
    )
    op.create_index(
        "ix_lineage_target",
        "lineage_edges",
        ["target_dataset"],
        schema="meta",
    )

    op.create_table(
        "incident_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer(),
            sa.ForeignKey("meta.incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("evidence_type", sa.String(100), nullable=False),
        sa.Column("evidence_payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="meta",
    )
    op.create_index(
        "ix_incident_evidence_incident",
        "incident_evidence",
        ["incident_id"],
        schema="meta",
    )

    # Evaluation data is deliberately stored outside meta.
    op.create_table(
        "incident_ground_truth",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_key", sa.String(150), nullable=False),
        sa.Column("expected_incident", sa.Boolean(), nullable=False),
        sa.Column("expected_category", sa.String(100)),
        sa.Column("expected_diagnosis", sa.Text()),
        sa.Column("split", sa.String(30), nullable=False),
        sa.Column(
            "labels",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("case_key", name="uq_ground_truth_case_key"),
        sa.CheckConstraint(
            "split IN ('train', 'validation', 'test', 'held_out')",
            name="ck_ground_truth_split",
        ),
        schema="eval",
    )


def downgrade() -> None:
    # Drop new tables in reverse dependency order.
    op.drop_table("incident_ground_truth", schema="eval")

    op.drop_index("ix_incident_evidence_incident", table_name="incident_evidence", schema="meta")
    op.drop_table("incident_evidence", schema="meta")

    op.drop_index("ix_lineage_target", table_name="lineage_edges", schema="meta")
    op.drop_table("lineage_edges", schema="meta")

    op.drop_index("ix_table_profiles_dataset_time", table_name="table_profiles", schema="meta")
    op.drop_table("table_profiles", schema="meta")

    op.drop_index("ix_task_runs_pipeline", table_name="task_runs", schema="meta")
    op.drop_table("task_runs", schema="meta")

    op.drop_index(
        "ix_schema_snapshots_dataset_time",
        table_name="schema_snapshots",
        schema="meta",
    )
    op.drop_table("schema_snapshots", schema="meta")

    op.drop_index(
        "ix_dataset_versions_event_time",
        table_name="dataset_versions",
        schema="meta",
    )
    op.drop_table("dataset_versions", schema="meta")

    op.drop_index("ix_pipeline_runs_name_started", table_name="pipeline_runs", schema="meta")
    op.drop_index("ix_quality_results_run", table_name="quality_results", schema="meta")
    op.drop_index("ix_incidents_status_created", table_name="incidents", schema="meta")

    for name, table in (
        ("ck_incidents_status", "incidents"),
        ("ck_incidents_severity", "incidents"),
        ("ck_quality_failed_rows", "quality_results"),
        ("ck_quality_results_status", "quality_results"),
        ("ck_pipeline_finished_after_started", "pipeline_runs"),
        ("ck_pipeline_rows_out", "pipeline_runs"),
        ("ck_pipeline_rows_in", "pipeline_runs"),
        ("ck_pipeline_runs_status", "pipeline_runs"),
    ):
        op.drop_constraint(name, table, schema="meta", type_="check")

    # Restore the original JSON column types.
    op.alter_column(
        "incidents",
        "evidence",
        schema="meta",
        existing_type=postgresql.JSONB(),
        type_=sa.JSON(),
        postgresql_using="evidence::json",
    )
    op.alter_column(
        "quality_results",
        "details",
        schema="meta",
        existing_type=postgresql.JSONB(),
        type_=sa.JSON(),
        postgresql_using="details::json",
    )
    op.alter_column(
        "dataset_contracts",
        "contract_definition",
        schema="meta",
        existing_type=postgresql.JSONB(),
        type_=sa.JSON(),
        postgresql_using="contract_definition::json",
    )

    # Move original tables back to public.
    op.drop_column("pipeline_runs", "event_time", schema="meta")

    for table in (
        "quality_results",
        "incidents",
        "pipeline_runs",
        "dataset_contracts",
    ):
        op.execute(f'ALTER TABLE meta."{table}" SET SCHEMA public')

    op.execute("DROP SCHEMA eval")
    op.execute("DROP SCHEMA meta")
