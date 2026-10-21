from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

LogicalType = Literal[
    "string",
    "integer",
    "float",
    "boolean",
    "timestamp",
    "date",
]

Layer = Literal["bronze", "silver", "gold"]
DataFormat = Literal["csv", "parquet"]


class ColumnContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    logical_type: LogicalType
    nullable: bool


class QualityRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["not_null", "unique", "accepted_values"]
    column: str | None = None
    columns: list[str] | None = None
    values: list[str] | None = None

    @model_validator(mode="after")
    def validate_rule_fields(self):
        if self.type == "not_null" and not self.column:
            raise ValueError("A not_null rule must define 'column'.")

        if self.type == "unique" and not self.columns:
            raise ValueError("A unique rule must define a non-empty 'columns' list.")

        if self.type == "accepted_values":
            if not self.column:
                raise ValueError("An accepted_values rule must define 'column'.")
            if not self.values:
                raise ValueError("An accepted_values rule must define non-empty 'values'.")

        return self


class DatasetContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str
    version: int = Field(ge=1)
    description: str
    layer: Layer
    format: DataFormat
    columns: list[ColumnContract]
    primary_key: list[str]
    quality_rules: list[QualityRule]

    @model_validator(mode="after")
    def validate_contract_consistency(self):
        column_names = [column.name for column in self.columns]
        columns_by_name = {column.name: column for column in self.columns}

        if len(column_names) != len(set(column_names)):
            raise ValueError("Column names must be unique.")

        if not column_names:
            raise ValueError("A contract must define at least one column.")

        if not self.primary_key:
            raise ValueError("A contract must define a primary key.")

        if len(self.primary_key) != len(set(self.primary_key)):
            raise ValueError("Primary key columns must be unique.")

        unknown_key_columns = set(self.primary_key) - set(column_names)
        if unknown_key_columns:
            raise ValueError(
                f"Primary key references unknown columns: {sorted(unknown_key_columns)}"
            )

        nullable_key_columns = [name for name in self.primary_key if columns_by_name[name].nullable]
        if nullable_key_columns:
            raise ValueError(
                f"Primary key columns cannot be nullable: {sorted(nullable_key_columns)}"
            )

        rule_ids = [rule.id for rule in self.quality_rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Quality rule IDs must be unique.")

        for rule in self.quality_rules:
            referenced_columns = []

            if rule.column:
                referenced_columns.append(rule.column)

            if rule.columns:
                referenced_columns.extend(rule.columns)

            unknown_columns = set(referenced_columns) - set(column_names)
            if unknown_columns:
                raise ValueError(
                    f"Rule '{rule.id}' references unknown columns: {sorted(unknown_columns)}"
                )

            if rule.type == "unique" and (len(rule.columns or []) != len(set(rule.columns or []))):
                raise ValueError(f"Rule '{rule.id}' contains duplicate unique columns.")

        return self
