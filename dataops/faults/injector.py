from collections.abc import Mapping, Sequence

from dataops.faults.models import FaultGroundTruth, FaultSpec

Record = dict[str, str | None]


def inject_fault(
    data: Sequence[Mapping[str, str | None]],
    spec: FaultSpec,
) -> tuple[list[Record], FaultGroundTruth]:
    """Inject a fault without modifying the original records."""

    if not data:
        raise ValueError("Cannot inject faults into an empty dataset")

    if any(spec.column not in record for record in data):
        raise ValueError(f"Missing column: {spec.column}")

    if any(index >= len(data) for index in spec.row_indices):
        raise IndexError("Fault target row is outside the dataset")

    if spec.source_row_index is not None and spec.source_row_index >= len(data):
        raise IndexError("Fault source row is outside the dataset")

    # Copy every row so the original input stays unchanged.
    corrupted = [dict(record) for record in data]

    original_values = tuple(corrupted[index][spec.column] for index in spec.row_indices)

    for index in spec.row_indices:
        if spec.fault_type == "duplicate_key":
            assert spec.source_row_index is not None
            new_value = corrupted[spec.source_row_index][spec.column]

        elif spec.fault_type == "null_value":
            new_value = None

        else:
            new_value = spec.value

        if corrupted[index][spec.column] == new_value:
            raise ValueError(f"Fault would not change row {index}: {spec.column}")

        corrupted[index][spec.column] = new_value

    injected_values = tuple(corrupted[index][spec.column] for index in spec.row_indices)

    ground_truth = FaultGroundTruth(
        fault_type=spec.fault_type,
        column=spec.column,
        affected_rows=spec.row_indices,
        expected_rule=spec.expected_rule,
        original_values=original_values,
        injected_values=injected_values,
    )

    return corrupted, ground_truth
