
import csv
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from dataops.contracts.models import DatasetContract


def evaluate_csv(
    csv_path: str | Path,
    contract: DatasetContract,
) -> dict:
    """Evaluate supported quality rules against a CSV file."""

    csv_path = Path(csv_path)
    run_id = str(uuid4())
    started_at = datetime.now(UTC)

    results = []
    rule_states = {}

    for rule in contract.quality_rules:
        rule_states[rule.id] = {
            "rule": rule,
            "failed_rows": 0,
            "seen_keys": set(),
            "examples": [],
        }

    with csv_path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {csv_path}")

        actual_columns = set(reader.fieldnames)
        expected_columns = {column.name for column in contract.columns}

        missing_columns = expected_columns - actual_columns
        if missing_columns:
            raise ValueError(
                f"CSV is missing contract columns: {sorted(missing_columns)}"
            )

        row_count = 0

        for row in reader:
            row_count += 1

            for rule_id, state in rule_states.items():
                rule = state["rule"]
                failed = False
                example = None

                if rule.type == "not_null":
                    value = row.get(rule.column or "")
                    failed = value is None or not value.strip()
                    example = {
                        "row_number": row_count + 1,
                        "value": value,
                    }

                elif rule.type == "unique":
                    key_columns = rule.columns or []
                    key = tuple(
                        (row.get(column) or "").strip()
                        for column in key_columns
                    )

                    # A separate not-null rule should report missing keys.
                    # Don't treat a missing key as a duplicate.
                    if all(key):
                        if key in state["seen_keys"]:
                            failed = True
                            example = {
                                "row_number": row_count + 1,
                                "key": dict(zip(key_columns, key)),
                            }
                        else:
                            state["seen_keys"].add(key)

                elif rule.type == "accepted_values":
                    value = (row.get(rule.column or "") or "").strip()
                    allowed = set(rule.values or [])
                    failed = value not in allowed
                    example = {
                        "row_number": row_count + 1,
                        "value": value,
                    }

                else:
                    raise ValueError(
                        f"Unsupported quality rule: {rule.type}"
                    )

                if failed:
                    state["failed_rows"] += 1
                    if len(state["examples"]) < 5 and example is not None:
                        state["examples"].append(example)

    for rule_id, state in rule_states.items():
        failed_rows = state["failed_rows"]

        results.append(
            {
                "rule_id": rule_id,
                "rule_type": state["rule"].type,
                "status": "PASS" if failed_rows == 0 else "FAIL",
                "checked_rows": row_count,
                "failed_rows": failed_rows,
                "examples": state["examples"],
            }
        )

    finished_at = datetime.now(UTC)

    overall_status = (
    "FAIL"
    if any(result["status"] == "FAIL" for result in results)
    else "PASS"
    )

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
