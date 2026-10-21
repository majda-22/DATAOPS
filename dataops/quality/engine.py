import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict
from uuid import uuid4

from dataops.contracts.models import DatasetContract


class Check(TypedDict):
    rule_id: str
    rule_type: str
    column: str | None
    columns: list[str]
    values: list[str]


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

    for rule in contract.quality_rules:
        check: Check = {
            "rule_id": rule.id,
            "rule_type": rule.type,
            "column": rule.column,
            "columns": rule.columns or [],
            "values": rule.values or [],
        }
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
                    "rule_id": f"auto_not_null_{column.name}",
                    "rule_type": "not_null",
                    "column": column.name,
                    "columns": [],
                    "values": [],
                }
            )

    # A primary key must be unique. A matching explicit rule is sufficient.
    primary_key = tuple(contract.primary_key)
    if frozenset(primary_key) not in explicit_unique:
        checks.append(
            {
                "rule_id": "auto_primary_key_unique",
                "rule_type": "unique",
                "column": None,
                "columns": list(primary_key),
                "values": [],
            }
        )

    return checks


def evaluate_csv(
    csv_path: str | Path,
    contract: DatasetContract,
) -> dict:
    """Evaluate explicit quality rules and automatic integrity checks."""
    csv_path = Path(csv_path)
    run_id = str(uuid4())
    started_at = datetime.now(UTC)

    checks = _build_checks(contract)
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

        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {csv_path}")

        actual_columns = set(reader.fieldnames)
        expected_columns = {column.name for column in contract.columns}

        missing_columns = expected_columns - actual_columns
        if missing_columns:
            raise ValueError(f"CSV is missing contract columns: {sorted(missing_columns)}")

        row_count = 0

        for row in reader:
            row_count += 1

            for rule_id, state in rule_states.items():
                check = state["check"]
                rule_type = check["rule_type"]
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

                else:
                    raise ValueError(f"Unsupported quality rule: {rule_type}")

                if failed:
                    state["failed_rows"] += 1
                    if len(state["examples"]) < 5 and example is not None:
                        state["examples"].append(example)

    results = []

    for rule_id, state in rule_states.items():
        failed_rows = state["failed_rows"]

        results.append(
            {
                "rule_id": rule_id,
                "rule_type": state["check"]["rule_type"],
                "status": "PASS" if failed_rows == 0 else "FAIL",
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
