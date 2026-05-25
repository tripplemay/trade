"""B027 F001 — SnapshotLoader abstraction + PriceBar dataclass.

The abstract base is intentionally narrow (``fetch_daily_bars`` +
``health_check``) so the contract every vendor adapter must satisfy
is exercised here, separately from any Tiingo-specific behaviour.
The PriceBar dataclass is checked for the structural invariants the
backtest paths will lean on (immutable + slots + field shape).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import date

import pytest

from workbench_api.data.snapshot_loader import PriceBar, SnapshotLoader


def test_snapshot_loader_is_abstract() -> None:
    """The ABC must refuse instantiation — only subclasses may exist."""

    with pytest.raises(TypeError) as exc_info:
        SnapshotLoader()  # type: ignore[abstract]
    assert "abstract" in str(exc_info.value).lower()


def test_price_bar_is_frozen() -> None:
    """PriceBar is immutable; reassigning a field must raise."""

    bar = PriceBar(
        ticker="SPY",
        bar_date=date(2026, 5, 25),
        open=520.10,
        high=522.50,
        low=519.80,
        close=521.30,
        adj_close=521.30,
        volume=42_000_000,
    )
    with pytest.raises(FrozenInstanceError):
        bar.close = 999.99  # type: ignore[misc]


def test_price_bar_uses_slots() -> None:
    """slots=True keeps memory footprint tight and forbids dynamic attrs."""

    bar = PriceBar(
        ticker="QQQ",
        bar_date=date(2026, 5, 25),
        open=510.0,
        high=515.0,
        low=508.0,
        close=512.5,
        adj_close=512.5,
        volume=18_000_000,
    )
    with pytest.raises((AttributeError, TypeError)):
        bar.note = "should not stick"  # type: ignore[attr-defined]


def test_price_bar_fields_match_normalised_shape() -> None:
    """Adapter implementations must populate exactly this normalised shape.

    A future vendor that adds extra fields (corporate actions, after-hours
    volume, etc.) must extend the dataclass deliberately rather than
    silently passing through vendor-specific keys.
    """

    expected = {
        "ticker",
        "bar_date",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
    }
    assert {f.name for f in fields(PriceBar)} == expected
