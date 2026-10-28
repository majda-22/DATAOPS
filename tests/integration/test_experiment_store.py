from uuid import uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from dataops.db.models import EvaluationExperiment, EvaluationScenario
from dataops.evaluation.history import (
    get_experiment_details,
    list_experiments,
)
from dataops.evaluation.metrics import calculate_metrics
from dataops.evaluation.runner import ExperimentScenario, run_experiment
from dataops.evaluation.store import persist_experiment


def fake_detector(data):
    failed = data["invalid"]

    return {
        "status": "FAIL" if failed else "PASS",
        "results": [
            {
                "rule_id": "order_status_allowed",
                "status": "FAIL" if failed else "PASS",
            }
        ],
    }


def test_persist_experiment(pg_engine):
    # Refuse to modify the production metadata database.
    assert pg_engine.url.database == "dataops_metadata_test"

    experiment = run_experiment(
        [
            ExperimentScenario("clean_1", {"invalid": False}),
            ExperimentScenario("clean_2", {"invalid": False}),
        ],
        fake_detector,
    )

    metrics = calculate_metrics(experiment)

    connection = pg_engine.connect()
    outer_transaction = connection.begin()

    try:
        with Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        ) as session:
            from dataops.evaluation.store import persist_experiment

            experiment_id = persist_experiment(
                session,
                experiment,
                metrics,
            )

            stored = session.get(EvaluationExperiment, experiment_id)

            assert stored is not None
            assert stored.metrics["total_scenarios"] == 2

            scenario_count = session.scalar(
                select(func.count(EvaluationScenario.id)).where(
                    EvaluationScenario.experiment_id == experiment_id
                )
            )

            assert scenario_count == 2

    finally:
        outer_transaction.rollback()
        connection.close()


def make_test_experiment():
    experiment = run_experiment(
        [
            ExperimentScenario(
                "clean",
                {"invalid": False},
            ),
            ExperimentScenario(
                "another_clean",
                {"invalid": False},
            ),
        ],
        fake_detector,
    )

    return experiment, calculate_metrics(experiment)


@pytest.fixture
def isolated_session(pg_engine):
    """Use the test database and roll back all test changes."""
    if pg_engine.url.database != "dataops_metadata_test":
        pytest.fail("Refusing to write outside dataops_metadata_test")

    connection = pg_engine.connect()
    transaction = connection.begin()

    try:
        with Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session
    finally:
        transaction.rollback()
        connection.close()


def test_duplicate_experiment_is_rejected(isolated_session):
    experiment, metrics = make_test_experiment()

    # First insertion succeeds.
    persist_experiment(isolated_session, experiment, metrics)

    # Same experiment UUID must be rejected.
    with pytest.raises(ValueError, match="already persisted"):
        persist_experiment(isolated_session, experiment, metrics)

    # Original experiment still exists.
    stored = isolated_session.get(
        EvaluationExperiment,
        experiment.experiment_id,
    )

    assert stored is not None

    count = isolated_session.scalar(
        select(func.count(EvaluationScenario.id)).where(
            EvaluationScenario.experiment_id == experiment.experiment_id
        )
    )

    assert count == 2


def test_scenario_failure_rolls_back_experiment(isolated_session):
    experiment, metrics = make_test_experiment()

    def reject_scenario_insert(session, flush_context, instances):
        if any(isinstance(obj, EvaluationScenario) for obj in session.new):
            raise RuntimeError("Simulated scenario insert failure")

    event.listen(
        isolated_session,
        "before_flush",
        reject_scenario_insert,
    )

    try:
        with pytest.raises(
            RuntimeError,
            match="Simulated scenario insert failure",
        ):
            persist_experiment(isolated_session, experiment, metrics)
    finally:
        event.remove(
            isolated_session,
            "before_flush",
            reject_scenario_insert,
        )

    # The parent experiment must not survive the failed transaction.
    assert (
        isolated_session.get(
            EvaluationExperiment,
            experiment.experiment_id,
        )
        is None
    )

    # Neither should its scenarios.
    count = isolated_session.scalar(
        select(func.count(EvaluationScenario.id)).where(
            EvaluationScenario.experiment_id == experiment.experiment_id
        )
    )

    assert count == 0


def test_invalid_metrics_do_not_modify_existing_data(isolated_session):
    experiment, metrics = make_test_experiment()

    persist_experiment(isolated_session, experiment, metrics)

    original = isolated_session.get(
        EvaluationExperiment,
        experiment.experiment_id,
    )

    assert original is not None
    original_metrics = dict(original.metrics)

    # Create inconsistent metrics deliberately.
    from dataclasses import replace

    invalid_metrics = replace(
        metrics,
        total_scenarios=999,
    )

    with pytest.raises(ValueError, match="do not match"):
        persist_experiment(
            isolated_session,
            experiment,
            invalid_metrics,
        )

    isolated_session.expire_all()

    stored = isolated_session.get(
        EvaluationExperiment,
        experiment.experiment_id,
    )

    assert stored is not None
    assert stored.metrics == original_metrics


def test_list_experiments_returns_saved_experiment(isolated_session):
    experiment, metrics = make_test_experiment()

    persist_experiment(isolated_session, experiment, metrics)

    history = list_experiments(isolated_session, limit=20)

    matching = [item for item in history if item["experiment_id"] == str(experiment.experiment_id)]

    assert len(matching) == 1
    assert matching[0]["metrics"]["total_scenarios"] == 2


def test_get_experiment_details(isolated_session):
    experiment, metrics = make_test_experiment()

    persist_experiment(isolated_session, experiment, metrics)

    details = get_experiment_details(
        isolated_session,
        experiment.experiment_id,
    )

    assert details is not None
    assert details["experiment_id"] == str(experiment.experiment_id)
    assert details["metrics"]["total_scenarios"] == 2
    assert len(details["scenarios"]) == 2

    names = {scenario["name"] for scenario in details["scenarios"]}

    assert names == {"clean", "another_clean"}


def test_missing_experiment_returns_none(isolated_session):
    result = get_experiment_details(
        isolated_session,
        uuid4(),
    )

    assert result is None


def test_invalid_history_limit_is_rejected(isolated_session):
    with pytest.raises(ValueError, match="positive"):
        list_experiments(isolated_session, limit=0)
