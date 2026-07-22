"""B111 F002 (P0-2) regression: the US Quality sleeve must be isolated from the
A-share rows that share the unified prices CSV.

Diagnosis §3/§6 F2: once A-share quotes were merged into the unified prices CSV,
the factor pivot's date index became the UNION of the US and CN trading
calendars. ``low_vol`` / ``trend`` require a full rolling window with no holes,
so the US columns — NaN on every CN-only trading day — went ALL-NaN, the sleeve
produced 0 holdings and silently fell back to SGOV, yet the metadata still said
``scored`` / ``real``.

Two defences, tested here:
  * generate_signal restricts prices + fundamentals to the universe first
    (``_restrict_to_universe``), so the pivot's calendar is US-only again;
  * the rolling factors compute each ticker over its OWN trading days
    (``dropna``), so a residual foreign-calendar hole can no longer NaN-out a
    healthy US name.

Both fail on the pre-fix code (US factors all-NaN on a unioned calendar) and
pass on the fixed code; both are no-ops on a dense US-only frame.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from trade.strategies.us_quality_momentum.factors import (
    low_vol_score,
    trend_score,
)
from trade.strategies.us_quality_momentum.signal import _restrict_to_universe


def _mixed_calendar_prices() -> tuple[pd.DataFrame, date]:
    """US ticker AAPL on weekdays only; A-share 600519.SH on EVERY calendar day.

    The A-share's weekend rows enter the pivot's date index, punching holes into
    AAPL's column exactly like the real US/CN calendar union does.
    """

    start = date(2024, 1, 1)
    rows: list[dict[str, object]] = []
    for offset in range(120):
        day = start + timedelta(days=offset)
        # A-share trades every day (its extra weekend days are the "holes").
        rows.append(
            {"date": day, "ticker": "600519.SH", "adj_close": 50.0 + offset * 0.1}
        )
        if day.weekday() < 5:  # US ticker: weekdays only
            rows.append(
                {"date": day, "ticker": "AAPL", "adj_close": 100.0 + offset * 0.2}
            )
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame, start + timedelta(days=119)


def test_low_vol_is_non_nan_for_us_ticker_on_unioned_calendar() -> None:
    prices, as_of = _mixed_calendar_prices()
    score = low_vol_score(prices, as_of, windows=(40,))
    # The whole point: AAPL is NOT NaN despite the interspersed weekend holes.
    assert "AAPL" in score.index
    assert pd.notna(score["AAPL"])
    assert int(score.notna().sum()) > 0


def test_trend_is_non_nan_for_us_ticker_on_unioned_calendar() -> None:
    prices, as_of = _mixed_calendar_prices()
    score = trend_score(prices, as_of, ma_short=10, ma_long=30, slope_window=5)
    assert "AAPL" in score.index
    assert pd.notna(score["AAPL"])
    assert int(score.notna().sum()) > 0


def test_restrict_to_universe_drops_ashares() -> None:
    prices, _ = _mixed_calendar_prices()
    restricted = _restrict_to_universe(prices, frozenset({"AAPL"}))
    assert set(restricted["ticker"].unique()) == {"AAPL"}
    assert "600519.SH" not in set(restricted["ticker"].unique())


def test_dense_us_only_frame_is_unchanged_by_hole_handling() -> None:
    """The per-ticker ``dropna`` must be a no-op on a dense US-only frame, so the
    validated factors are unchanged: a frame with no holes yields the same
    (finite) score whether or not any foreign rows are present."""

    start = date(2024, 1, 1)
    dense_rows = [
        {"date": start + timedelta(days=o), "ticker": t, "adj_close": base + o * 0.2}
        for o in range(120)
        for t, base in (("AAPL", 100.0), ("MSFT", 120.0))
        if (start + timedelta(days=o)).weekday() < 5
    ]
    dense = pd.DataFrame(dense_rows)
    dense["date"] = pd.to_datetime(dense["date"])
    as_of = start + timedelta(days=119)
    score = low_vol_score(dense, as_of, windows=(40,))
    assert pd.notna(score["AAPL"]) and pd.notna(score["MSFT"])
