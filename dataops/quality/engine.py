import csv
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NotRequired, TypedDict
from uuid import UUID, uuid4

from dataops.contracts.models import DatasetContract


class Check(TypedDict):
    rule_id: str
    rule_type: str
    column: str | None
    columns: list[str]
    values: list[str]
    min_rows: NotRequired[int]
    reference_dataset: NotRequired[str]
    reference_columns: NotRequired[list[str]]


class CheckState(TypedDict):
    check: Check
    failed_rows: int
    seen_keys: set[tuple[str, ...]]
    examples: list[dict[str, Any]]


def _build_checks(contract: DatasetContract) -> list[Check]:
    """Combine explicit rules with missing automatic integrity checks."""
    checks: list[Check] = []
    explicit_not_null = set()
    explicit_unique = set()
    used_ids = {rule.id for rule in contract.quality_rules} | {
        key.id for key in contract.foreign_keys
    }

    def generated_id(base: str) -> str:
        candidate = base
        suffix = 2
        while candidate in used_ids:
            candidate = f"{base}__{suffix}"
            suffix += 1
        used_ids.add(candidate)
        return candidate

    for rule in contract.quality_rules:
        check: Check = {
            "rule_id": rule.id,
            "rule_type": rule.type,
            "column": rule.column,
            "columns": rule.columns or [],
            "values": rule.values or [],
        }
        if rule.min_rows is not None:
            check["min_rows"] = rule.min_rows
        checks.append(check)

        if rule.type == "not_null":
            explicit_not_null.add(rule.column)

        elif rule.type == "unique":
            explicit_unique.add(frozenset(rule.columns or []))

    # Automatically check every non-nullable column.
    for column in contract.columns:
        if not column.nullable and column.name not in explicit_not_null:
            checks.append(
                {
                    "rule_id": generated_id(f"auto_not_null_{column.name}"),
                    "rule_type": "not_null",
                    "column": column.name,
                    "columns": [],
                    "values": [],
                }
            )

    # A primary key must be unique. A matching explicit rule is sufficient.
    primary_key = tuple(contract.primary_key)
    if primary_key and frozenset(primary_key) not in explicit_unique:
        checks.append(
            {
                "rule_id": generated_id("auto_primary_key_unique"),
                "rule_type": "unique",
                "column": None,
                "columns": list(primary_key),
                "values": [],
            }
        )

    for key in contract.foreign_keys:
        checks.append(
            {
                "rule_id": key.id,
                "rule_type": "foreign_key",
                "column": None,
                "columns": key.columns,
                "values": [],
                "reference_dataset": key.reference_dataset,
                "reference_columns": key.reference_columns,
            }
        )
    return checks


def _validate_header(columns: Sequence[str] | None, required: set[str], path: Path) -> None:
    if not columns:
        raise ValueError(f"CSV has no header: {path}")
    if len(columns) != len(set(columns)):
        raise ValueError(f"CSV contains duplicate column names: {path}")
    if required - set(columns):
        raise ValueError(f"CSV is missing contract columns: {sorted(required - set(columns))}")


def evaluate_csv(
    csv_path: str | Path,
    contract: DatasetContract,
    *,
    reference_data: Mapping[str, str | Path] | None = None,
    run_id: UUID | str | None = None,
) -> dict:
    """Evaluate explicit quality rules and automatic integrity checks."""
    if contract.format != "csv":
        raise ValueError("The CSV reference engine requires a csv contract.")
    csv_path = Path(csv_path)
    run_id = str(UUID(str(run_id))) if run_id is not None else str(uuid4())
    started_at = datetime.now(UTC)

    checks = _build_checks(contract)
    reference_keys: dict[str, set[tuple[str, ...]]] = {}
    for check in checks:
        if check["rule_type"] != "foreign_key":
            continue
        dataset = check["reference_dataset"]
        if reference_data is None or dataset not in reference_data:
            raise ValueError(f"Foreign-key validation requires reference data for {dataset}.")
        reference_path = Path(reference_data[dataset])
        columns = check["reference_columns"]
        keys: set[tuple[str, ...]] = set()
        with reference_path.open(encoding="utf-8-sig", newline="") as reference_file:
            reader = csv.DictReader(reference_file)
            _validate_header(reader.fieldnames, set(columns), reference_path)
            for row in reader:
                key = tuple((row.get(column) or "").strip() for column in columns)
                if all(key):
                    if key in keys:
                        raise ValueError(f"Reference key is not unique in {dataset}: {key}")
                    keys.add(key)
        reference_keys[check["rule_id"]] = keys
    rule_states: dict[str, CheckState] = {
        check["rule_id"]: {
            "check": check,
            "failed_rows": 0,
            "seen_keys": set(),
            "examples": [],
        }
        for check in checks
    }

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        expected_columns = {column.name for column in contract.columns}
        _validate_header(reader.fieldnames, expected_columns, csv_path)

        row_count = 0

        for row in reader:
            row_count += 1

            for rule_id, state in rule_states.items():
                check = state["check"]
                rule_type = check["rule_type"]
                if rule_type == "min_row_count":
                    continue
                failed = False
                example = None

                if rule_type == "not_null":
                    column = check["column"] or ""
                    value = row.get(column)
                    failed = value is None or not value.strip()

                    if failed:
                        example = {
                            "row_number": row_count + 1,
                            "value": value,
                        }

                elif rule_type == "unique":
                    columns = check["columns"]
                    key = tuple((row.get(column) or "").strip() for column in columns)

                    # Missing key components are reported by not-null checks.
                    if all(key):
                        if key in state["seen_keys"]:
                            failed = True
                            example = {
                                "row_number": row_count + 1,
                                "key": dict(zip(columns, key)),
                            }
                        else:
                            state["seen_keys"].add(key)

                elif rule_type == "accepted_values":
                    column = check["column"] or ""
                    value = (row.get(column) or "").strip()
                    failed = value not in set(check["values"])

                    if failed:
                        example = {
                            "row_number": row_count + 1,
                            "value": value,
                        }

                elif rule_type == "foreign_key":
                    key = tuple((row.get(column) or "").strip() for column in check["columns"])
                    # SQL MATCH SIMPLE: null components are left to nullability rules.
                    failed = all(key) and key not in reference_keys[rule_id]
                    if failed:
                        example = {
                            "row_number": row_count + 1,
                            "key": dict(zip(check["columns"], key)),
                        }
                else:
                    raise ValueError(f"Unsupported quality rule: {rule_type}")

                if failed:
                    state["failed_rows"] += 1
                    if len(state["examples"]) < 5 and example is not None:
                        state["examples"].append(example)

    results = []

    for rule_id, state in rule_states.items():
        failed_rows = state["failed_rows"]
        failed_check = failed_rows > 0
        if state["check"]["rule_type"] == "min_row_count":
            minimum = state["check"]["min_rows"]
            failed_check = row_count < minimum
            state["examples"] = (
                [{"minimum_rows": minimum, "observed_rows": row_count}] if failed_check else []
            )

        results.append(
            {
                "rule_id": rule_id,
                "rule_type": state["check"]["rule_type"],
                "status": "FAIL" if failed_check else "PASS",
                "checked_rows": row_count,
                "failed_rows": failed_rows,
                "examples": state["examples"],
            }
        )

    finished_at = datetime.now(UTC)
    overall_status = "FAIL" if any(result["status"] == "FAIL" for result in results) else "PASS"

    return {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "dataset": contract.dataset,
        "contract_version": contract.version,
        "source_file": csv_path.name,
        "row_count": row_count,
        "status": overall_status,
        "results": results,
    }
