from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from dataops.db.models import PipelineRun


def get_pipeline_history(
    session: Session,
    pipeline_name: str,
    limit: int = 10,
) -> list[dict]:
    """Retrieve observable pipeline execution history."""

    if not pipeline_name.strip():
        raise ValueError("Pipeline name is required")

    if not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100")

    statement = (
        select(
            PipelineRun.id,
            PipelineRun.pipeline_name,
            PipelineRun.status,
            PipelineRun.started_at,
            PipelineRun.finished_at,
            PipelineRun.rows_in,
            PipelineRun.rows_out,
        )
        .where(PipelineRun.pipeline_name == pipeline_name)
        .order_by(PipelineRun.started_at.desc(), PipelineRun.id.desc())
        .limit(limit)
    )

    rows = session.execute(statement).all()

    return [
        {
            "run_id": str(row.id),
            "pipeline_name": row.pipeline_name,
            "status": row.status,
            "started_at": row.started_at.isoformat(),
            "finished_at": (row.finished_at.isoformat() if row.finished_at is not None else None),
            "rows_in": row.rows_in,
            "rows_out": row.rows_out,
        }
        for row in rows
    ]


def get_pipeline_run_by_id(
    session: Session,
    run_id: UUID,
) -> dict | None:
    """Retrieve a specific pipeline run by its identifier."""

    statement = select(
        PipelineRun.id,
        PipelineRun.pipeline_name,
        PipelineRun.status,
        PipelineRun.started_at,
        PipelineRun.finished_at,
        PipelineRun.rows_in,
        PipelineRun.rows_out,
    ).where(PipelineRun.id == run_id)

    row = session.execute(statement).one_or_none()

    if row is None:
        return None

    return {
        "run_id": str(row.id),
        "pipeline_name": row.pipeline_name,
        "status": row.status,
        "started_at": row.started_at.isoformat(),
        "finished_at": (row.finished_at.isoformat() if row.finished_at is not None else None),
        "rows_in": row.rows_in,
        "rows_out": row.rows_out,
    }
