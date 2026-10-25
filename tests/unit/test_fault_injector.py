from copy import deepcopy

import pytest

from dataops.faults.injector import inject_fault
from dataops.faults.models import FaultSpec


@pytest.fixture
def orders():
    return [
        {
            "order_id": "order_001",
            "customer_id": "customer_001",
            "order_status": "delivered",
        },
        {
            "order_id": "order_002",
            "customer_id": "customer_002",
            "order_status": "shipped",
        },
    ]


@pytest.mark.parametrize(
    ("spec", "expected_value"),
    [
        (
            FaultSpec(
                fault_type="duplicate_key",
                column="order_id",
                row_indices=(1,),
                source_row_index=0,
                expected_rule="order_id_unique",
            ),
            "order_001",
        ),
        (
            FaultSpec(
                fault_type="invalid_value",
                column="order_status",
                row_indices=(1,),
                value="INVALID_STATUS",
                expected_rule="order_status_allowed",
            ),
            "INVALID_STATUS",
        ),
        (
            FaultSpec(
                fault_type="null_value",
                column="order_id",
                row_indices=(1,),
                expected_rule="order_id_not_null",
            ),
            None,
        ),
        (
            FaultSpec(
                fault_type="foreign_key_violation",
                column="customer_id",
                row_indices=(1,),
                value="UNKNOWN_CUSTOMER",
                expected_rule="orders_customer_fk",
            ),
            "UNKNOWN_CUSTOMER",
        ),
    ],
)
def test_inject_fault(orders, spec, expected_value):
    original = deepcopy(orders)

    corrupted, truth = inject_fault(orders, spec)

    assert corrupted[1][spec.column] == expected_value
    assert truth.expected_rule == spec.expected_rule
    assert truth.affected_rows == (1,)
    assert truth.original_values == (original[1][spec.column],)
    assert truth.injected_values == (expected_value,)

    # Original dataset must remain unchanged.
    assert orders == original

    # Injection must preserve row count.
    assert len(corrupted) == len(orders)


def test_invalid_row_index_is_rejected(orders):
    spec = FaultSpec(
        fault_type="null_value",
        column="order_id",
        row_indices=(99,),
        expected_rule="order_id_not_null",
    )

    with pytest.raises(IndexError):
        inject_fault(orders, spec)


def test_missing_column_is_rejected(orders):
    spec = FaultSpec(
        fault_type="null_value",
        column="missing_column",
        row_indices=(0,),
        expected_rule="missing_rule",
    )

    with pytest.raises(ValueError, match="Missing column"):
        inject_fault(orders, spec)


def test_invalid_duplicate_source_is_rejected():
    with pytest.raises(ValueError):
        FaultSpec(
            fault_type="duplicate_key",
            column="order_id",
            row_indices=(0,),
            source_row_index=0,
            expected_rule="order_id_unique",
        )


def test_fault_must_change_value(orders):
    spec = FaultSpec(
        fault_type="invalid_value",
        column="order_status",
        row_indices=(1,),
        value="shipped",
        expected_rule="order_status_allowed",
    )

    with pytest.raises(ValueError, match="would not change"):
        inject_fault(orders, spec)


def test_injection_is_deterministic(orders):
    spec = FaultSpec(
        fault_type="invalid_value",
        column="order_status",
        row_indices=(1,),
        value="INVALID_STATUS",
        expected_rule="order_status_allowed",
    )

    result1 = inject_fault(orders, spec)
    result2 = inject_fault(orders, spec)

    assert result1 == result2
