"""B029 F001 — FundamentalsLoader / FundamentalsRow contract.

The abstract base class is a behavioural surface: instantiation must
fail (abstract methods unimplemented), the row dataclass must mirror
the B025 fixture column layout 1:1, and the slots/frozen invariants
must hold so callers cannot accidentally mutate or extend a parsed
row in place.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import date

import pytest

from workbench_api.data.fundamentals_loader import (
    FundamentalsLoader,
    FundamentalsRow,
)


def test_fundamentals_loader_is_abstract_and_cannot_instantiate() -> None:
    """The contract is a behavioural surface, not a constructible type;
    a future adapter that forgets to implement either abstract method
    must fail at class definition (mypy) and instantiation (TypeError),
    not silently fall back to no-ops."""

    with pytest.raises(TypeError) as exc_info:
        FundamentalsLoader()  # type: ignore[abstract]
    assert "abstract" in str(exc_info.value).lower()


def test_fundamentals_row_has_expected_12_field_schema() -> None:
    """B025 fixture ``fundamentals.csv`` is 12 columns; the dataclass
    must mirror them 1:1 in the canonical order (Planner pre-impl
    adjudication 2026-05-26 decision #1)."""

    declared = tuple(f.name for f in fields(FundamentalsRow))
    expected = (
        "report_date",
        "ticker",
        "fiscal_quarter",
        "fiscal_quarter_end",
        "roe",
        "gross_margin",
        "fcf_yield",
        "debt_to_assets",
        "pe",
        "pb",
        "ev_ebitda",
        "earnings_yield",
    )
    assert declared == expected, (
        "FundamentalsRow field order must mirror B025 fixture fundamentals.csv "
        f"column layout 1:1. Expected {expected}; got {declared}."
    )
    assert len(declared) == 12


def test_fundamentals_row_is_frozen_and_uses_slots() -> None:
    """Immutability prevents downstream callers (B029 F002 backfill
    driver / B029 F003 PIT loader / B025 strategy code) from
    accidentally mutating a parsed row; ``__slots__`` keeps memory
    flat across the 30 ticker × 40 quarter row matrix at backfill
    time."""

    row = FundamentalsRow(
        report_date=date(2015, 2, 4),
        ticker="AAPL",
        fiscal_quarter="2014Q4",
        fiscal_quarter_end=date(2014, 12, 31),
        roe=0.4469,
        gross_margin=0.4353,
        fcf_yield=0.0418,
        debt_to_assets=0.2952,
        pe=20.57,
        pb=12.54,
        ev_ebitda=16.72,
        earnings_yield=0.0486,
    )
    with pytest.raises(FrozenInstanceError):
        row.roe = 0.5  # type: ignore[misc]
    # ``__slots__`` keeps memory flat — verify it exists on the type
    # (covers all 12 field names). On a frozen dataclass, trying to
    # set an unknown attribute trips the frozen ``__setattr__`` first
    # rather than the slots ``__setattr__``, so we assert the slots
    # invariant via the class attribute instead.
    assert hasattr(FundamentalsRow, "__slots__")
    declared_slots = set(FundamentalsRow.__slots__)
    expected = {
        "report_date",
        "ticker",
        "fiscal_quarter",
        "fiscal_quarter_end",
        "roe",
        "gross_margin",
        "fcf_yield",
        "debt_to_assets",
        "pe",
        "pb",
        "ev_ebitda",
        "earnings_yield",
    }
    assert declared_slots == expected


def test_fundamentals_row_uses_canonical_fiscal_quarter_format() -> None:
    """B025 fixture writes ``2014Q4`` (no hyphen). Decision #2 lock —
    a future adapter cannot drift to ``2014-Q4`` because B025 strategy
    code reads the fixture column directly (B025 F003 deterministic
    invariant)."""

    row = FundamentalsRow(
        report_date=date(2015, 2, 4),
        ticker="AAPL",
        fiscal_quarter="2014Q4",
        fiscal_quarter_end=date(2014, 12, 31),
        roe=0.4469,
        gross_margin=0.4353,
        fcf_yield=0.0418,
        debt_to_assets=0.2952,
        pe=20.57,
        pb=12.54,
        ev_ebitda=16.72,
        earnings_yield=0.0486,
    )
    assert "Q" in row.fiscal_quarter
    assert "-Q" not in row.fiscal_quarter, (
        "fiscal_quarter must use the compact YYYYQn form (no hyphen); "
        "B025 fixture writes 2014Q4."
    )
    assert row.fiscal_quarter == "2014Q4"
