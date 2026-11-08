from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from dataops.db.models import PipelineRun
from dataops.diagnosis.pipeline_history import get_pipeline_history, get_pipeline_run_by_id


def test_pipeline_history_returns_newest_first(pg_engine):
    now = datetime.now(UTC)
    pipeline_name = f"test_pipeline_{uuid4().hex}"

    with Session(pg_engine) as session:
        with session.begin():
            for index in range(3):
                session.add(
                    PipelineRun(
                        id=uuid4(),
                        pipeline_name=pipeline_name,
                        status="success",
                        started_at=now + timedelta(minutes=index),
                        finished_at=now + timedelta(minutes=index + 1),
                        rows_in=100,
                    )
                )

        runs = get_pipeline_history(session, pipeline_name, limit=2)

        assert len(runs) == 2
        assert runs[0]["started_at"] > runs[1]["started_at"]
        assert all(run["pipeline_name"] == pipeline_name for run in runs)


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_pipeline_history_rejects_invalid_limit(pg_engine, limit):
    with Session(pg_engine) as session:
        with pytest.raises(ValueError):
            get_pipeline_history(session, "olist_bronze_quality", limit)


def test_pipeline_run_lookup_by_id(pg_engine):
    run_id = uuid4()

    with Session(pg_engine) as session:
        with session.begin():
            session.add(
                PipelineRun(
                    id=run_id,
                    pipeline_name="test_run_lookup",
                    status="success",
                    started_at=datetime.now(UTC),
                    rows_in=100,
                )
            )

        result = get_pipeline_run_by_id(session, run_id)

        assert result is not None
        assert result["run_id"] == str(run_id)
        assert result["pipeline_name"] == "test_run_lookup"
        assert result["rows_in"] == 100


def test_pipeline_run_lookup_missing(pg_engine):
    with Session(pg_engine) as session:
        assert get_pipeline_run_by_id(session, uuid4()) is None
