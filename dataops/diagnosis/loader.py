from uuid import UUID

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from dataops.diagnosis.pipeline_history import get_pipeline_run_by_id
from dataops.diagnosis.repository import get_scenario_evidence


def make_evidence_loader(engine: Engine):
    """Create an evidence-only loader for LangGraph."""

    def load_evidence(
        experiment_id: UUID,
        scenario_name: str,
    ) -> dict | None:
        with Session(engine) as session:
            return get_scenario_evidence(
                session,
                experiment_id,
                scenario_name,
            )

    return load_evidence


def make_pipeline_run_loader(engine: Engine):
    """Create a pipeline run loader for LangGraph."""

    def load_pipeline_run(run_id: UUID) -> dict | None:
        with Session(engine) as session:
            return get_pipeline_run_by_id(session, run_id)

    return load_pipeline_run
