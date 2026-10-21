from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dataops.db.base import Base


class DatasetContract(Base):
    __tablename__ = "dataset_contracts"
    __table_args__ = (
        UniqueConstraint("dataset_name", "version", name="uq_contract_dataset_version"),
        {"schema": "meta"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_name: Mapped[str] = mapped_column(String(150), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    contract_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint("dataset_name", "version", name="uq_dataset_version"),
        CheckConstraint("row_count IS NULL OR row_count >= 0", name="ck_dataset_version_row_count"),
        Index("ix_dataset_versions_event_time", "event_time"),
        {"schema": "meta"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_name: Mapped[str] = mapped_column(String(150), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    row_count: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class SchemaSnapshot(Base):
    __tablename__ = "schema_snapshots"
    __table_args__ = (
        Index("ix_schema_snapshots_dataset_time", "dataset_name", "captured_at"),
        {"schema": "meta"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_name: Mapped[str] = mapped_column(String(150), nullable=False)
    schema_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed', 'cancelled')",
            name="ck_pipeline_runs_status",
        ),
        CheckConstraint("rows_in IS NULL OR rows_in >= 0", name="ck_pipeline_rows_in"),
        CheckConstraint("rows_out IS NULL OR rows_out >= 0", name="ck_pipeline_rows_out"),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_pipeline_finished_after_started",
        ),
        Index("ix_pipeline_runs_name_started", "pipeline_name", "started_at"),
        {"schema": "meta"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("meta.dataset_contracts.id"), nullable=True
    )
    pipeline_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_in: Mapped[int | None] = mapped_column(Integer)
    rows_out: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)


class TaskRun(Base):
    __tablename__ = "task_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed', 'skipped', 'cancelled')",
            name="ck_task_runs_status",
        ),
        CheckConstraint("rows_in IS NULL OR rows_in >= 0", name="ck_task_rows_in"),
        CheckConstraint("rows_out IS NULL OR rows_out >= 0", name="ck_task_rows_out"),
        CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="ck_task_finished_after_started",
        ),
        Index("ix_task_runs_pipeline", "pipeline_run_id"),
        {"schema": "meta"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("meta.pipeline_runs.id", ondelete="CASCADE"), nullable=False
    )
    task_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_in: Mapped[int | None] = mapped_column(Integer)
    rows_out: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)


class QualityResult(Base):
    __tablename__ = "quality_results"
    __table_args__ = (
        CheckConstraint(
            "status IN ('passed', 'failed', 'warning', 'error')",
            name="ck_quality_results_status",
        ),
        CheckConstraint("failed_rows >= 0", name="ck_quality_failed_rows"),
        Index("ix_quality_results_run", "pipeline_run_id"),
        {"schema": "meta"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("meta.pipeline_runs.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TableProfile(Base):
    __tablename__ = "table_profiles"
    __table_args__ = (
        CheckConstraint("row_count >= 0", name="ck_table_profiles_row_count"),
        Index("ix_table_profiles_dataset_time", "dataset_name", "profiled_at"),
        {"schema": "meta"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_name: Mapped[str] = mapped_column(String(150), nullable=False)
    pipeline_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("meta.pipeline_runs.id", ondelete="SET NULL")
    )
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_profiles: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    profiled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LineageEdge(Base):
    __tablename__ = "lineage_edges"
    __table_args__ = (
        UniqueConstraint("source_dataset", "target_dataset", name="uq_lineage_source_target"),
        CheckConstraint("source_dataset <> target_dataset", name="ck_lineage_not_self"),
        Index("ix_lineage_target", "target_dataset"),
        {"schema": "meta"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_dataset: Mapped[str] = mapped_column(String(150), nullable=False)
    target_dataset: Mapped[str] = mapped_column(String(150), nullable=False)
    pipeline_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("meta.pipeline_runs.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_incidents_severity",
        ),
        CheckConstraint(
            "status IN ('open', 'investigating', 'resolved', 'dismissed')",
            name="ck_incidents_status",
        ),
        Index("ix_incidents_status_created", "status", "created_at"),
        {"schema": "meta"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pipeline_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("meta.pipeline_runs.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    diagnosis: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IncidentEvidence(Base):
    __tablename__ = "incident_evidence"
    __table_args__ = (
        Index("ix_incident_evidence_incident", "incident_id"),
        {"schema": "meta"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("meta.incidents.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IncidentGroundTruth(Base):
    __tablename__ = "incident_ground_truth"
    __table_args__ = (
        UniqueConstraint("case_key", name="uq_ground_truth_case_key"),
        CheckConstraint(
            "split IN ('train', 'validation', 'test', 'held_out')",
            name="ck_ground_truth_split",
        ),
        {"schema": "eval"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_key: Mapped[str] = mapped_column(String(150), nullable=False)
    expected_incident: Mapped[bool] = mapped_column(Boolean, nullable=False)
    expected_category: Mapped[str | None] = mapped_column(String(100))
    expected_diagnosis: Mapped[str | None] = mapped_column(Text)
    split: Mapped[str] = mapped_column(String(30), nullable=False)
    labels: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
