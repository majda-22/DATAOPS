from sqlalchemy import CheckConstraint
from sqlalchemy.dialects import postgresql

import dataops.db.models  # noqa: F401
from dataops.db.base import Base


def test_expected_tables_and_schemas_exist() -> None:
    expected = {
        ("meta", "dataset_contracts"),
        ("meta", "dataset_versions"),
        ("meta", "schema_snapshots"),
        ("meta", "pipeline_runs"),
        ("meta", "task_runs"),
        ("meta", "quality_results"),
        ("meta", "table_profiles"),
        ("meta", "lineage_edges"),
        ("meta", "incidents"),
        ("meta", "incident_evidence"),
        ("eval", "incident_ground_truth"),
    }

    actual = {(table.schema, table.name) for table in Base.metadata.tables.values()}

    assert expected <= actual


def test_all_flexible_metadata_columns_use_jsonb() -> None:
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if column.name in {
                "contract_definition",
                "metadata_json",
                "schema_definition",
                "details",
                "column_profiles",
                "evidence",
                "evidence_payload",
                "labels",
            }:
                assert isinstance(column.type, postgresql.JSONB), (
                    f"{table.fullname}.{column.name} should use JSONB"
                )


def test_task_runs_reference_pipeline_runs() -> None:
    table = Base.metadata.tables["meta.task_runs"]

    foreign_keys = {fk.target_fullname for column in table.columns for fk in column.foreign_keys}

    assert "meta.pipeline_runs.id" in foreign_keys


def test_incident_evidence_references_incidents() -> None:
    table = Base.metadata.tables["meta.incident_evidence"]

    foreign_keys = {fk.target_fullname for column in table.columns for fk in column.foreign_keys}

    assert "meta.incidents.id" in foreign_keys


def test_operational_tables_have_no_ground_truth_foreign_key() -> None:
    for table in Base.metadata.tables.values():
        if table.schema != "meta":
            continue

        for column in table.columns:
            for foreign_key in column.foreign_keys:
                assert not foreign_key.target_fullname.startswith("eval.incident_ground_truth.")


def test_pipeline_run_status_constraint_exists() -> None:
    table = Base.metadata.tables["meta.pipeline_runs"]

    expressions = [
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    ]

    assert any("status IN" in expression for expression in expressions)


def test_ground_truth_is_in_eval_schema() -> None:
    table = Base.metadata.tables["eval.incident_ground_truth"]

    assert table.schema == "eval"
    assert "case_key" in table.columns
    assert "split" in table.columns
    assert "expected_incident" in table.columns
