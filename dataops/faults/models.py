from dataclasses import dataclass
from typing import Literal

FaultType = Literal[
    "duplicate_key",
    "invalid_value",
    "null_value",
    "foreign_key_violation",
]


@dataclass(frozen=True)
class FaultSpec:
    """A deterministic fault-injection instruction."""

    fault_type: FaultType
    column: str
    row_indices: tuple[int, ...]
    expected_rule: str
    value: str | None = None
    source_row_index: int | None = None

    def __post_init__(self) -> None:
        supported = {
            "duplicate_key",
            "invalid_value",
            "null_value",
            "foreign_key_violation",
        }

        if self.fault_type not in supported:
            raise ValueError(f"Unsupported fault type: {self.fault_type}")

        if not self.column or not self.expected_rule:
            raise ValueError("Column and expected rule are required")

        if not self.row_indices:
            raise ValueError("At least one target row is required")

        if len(set(self.row_indices)) != len(self.row_indices):
            raise ValueError("Row indices must be unique")

        if any(index < 0 for index in self.row_indices):
            raise ValueError("Row indices cannot be negative")

        if self.fault_type == "duplicate_key":
            if self.source_row_index is None:
                raise ValueError("duplicate_key requires source_row_index")

            if self.source_row_index < 0:
                raise ValueError("source_row_index cannot be negative")

            if self.source_row_index in self.row_indices:
                raise ValueError("Source row cannot also be a target")

        elif self.source_row_index is not None:
            raise ValueError("source_row_index is only for duplicate_key")

        if self.fault_type in {"invalid_value", "foreign_key_violation"}:
            if self.value is None:
                raise ValueError(f"{self.fault_type} requires a value")


@dataclass(frozen=True)
class FaultGroundTruth:
    """Evaluation-only record of an injected fault."""

    fault_type: FaultType
    column: str
    affected_rows: tuple[int, ...]
    expected_rule: str
    original_values: tuple[str | None, ...]
    injected_values: tuple[str | None, ...]
