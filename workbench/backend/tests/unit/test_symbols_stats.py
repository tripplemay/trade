"""B059 F001 — compute_price_stats: 52-week range + window returns.

Pure-function tests (no DB / network). Pins the headline numbers the detail
page shows and the honest-degradation contract: a window that predates the
series yields ``None``, never a fabricated zero.
"""

from __future__ import annotations

from datetime import date

import pytest

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.symbols.stats import compute_price_stats


def _bar(d: date, close: float, *, high: float, low: float) -> PriceBar:
    return PriceBar(
        ticker="TEST",
        bar_date=d,
        open=close,
        high=high,
        low=low,
        close=close,
        adj_close=close,
        volume=1_000,
    )


def _full_series() -> list[PriceBar]:
    return [
        _bar(date(2025, 6, 13), 100.0, high=105.0, low=90.0),
        _bar(date(2025, 12, 31), 120.0, high=125.0, low=118.0),
        _bar(date(2026, 3, 13), 110.0, high=160.0, low=108.0),
        _bar(date(2026, 5, 13), 130.0, high=135.0, low=128.0),
        _bar(date(2026, 6, 13), 150.0, high=152.0, low=148.0),
    ]


def test_latest_close_and_as_of() -> None:
    stats = compute_price_stats(_full_series(), as_of=date(2026, 6, 13))
    assert stats.latest_close == 150.0
    assert stats.as_of == date(2026, 6, 13)


def test_52_week_high_low_uses_intraday_high_low() -> None:
    stats = compute_price_stats(_full_series(), as_of=date(2026, 6, 13))
    # The 160.0 spike is an intraday HIGH on 2026-03-13 (close is only 110).
    assert stats.week52_high == 160.0
    # 90.0 is the intraday LOW on the boundary bar (2025-06-13, exactly 365d).
    assert stats.week52_low == 90.0


def test_window_returns_use_close_on_or_before_window_start() -> None:
    stats = compute_price_stats(_full_series(), as_of=date(2026, 6, 13))
    r = stats.returns
    # 1M base = 2026-05-13 close 130 (latest on/before 2026-05-14).
    assert r["1M"] == pytest.approx(150.0 / 130.0 - 1.0)
    # 3M base = 2026-03-13 close 110 (latest on/before 2026-03-14).
    assert r["3M"] == pytest.approx(150.0 / 110.0 - 1.0)
    # 6M base = 2025-06-13 close 100 (no bar between 2025-06 and 2025-12-13).
    assert r["6M"] == pytest.approx(150.0 / 100.0 - 1.0)
    # 1Y base = 2025-06-13 close 100 (exactly 365d, on/before holds).
    assert r["1Y"] == pytest.approx(150.0 / 100.0 - 1.0)
    # YTD base = last close of prior year 2025-12-31 = 120.
    assert r["YTD"] == pytest.approx(150.0 / 120.0 - 1.0)


def test_insufficient_history_degrades_to_none_not_zero() -> None:
    short = [
        _bar(date(2026, 5, 1), 100.0, high=101.0, low=99.0),
        _bar(date(2026, 5, 14), 105.0, high=106.0, low=104.0),
        _bar(date(2026, 6, 13), 110.0, high=111.0, low=109.0),
    ]
    stats = compute_price_stats(short, as_of=date(2026, 6, 13))
    # 1M base = 2026-05-14 close 105 exists.
    assert stats.returns["1M"] == pytest.approx(110.0 / 105.0 - 1.0)
    # The series doesn't reach back far enough for these → None (not 0.0).
    assert stats.returns["3M"] is None
    assert stats.returns["6M"] is None
    assert stats.returns["1Y"] is None
    assert stats.returns["YTD"] is None


def test_single_bar_returns_all_none_but_keeps_range() -> None:
    stats = compute_price_stats(
        [_bar(date(2026, 6, 13), 200.0, high=210.0, low=190.0)],
        as_of=date(2026, 6, 13),
    )
    assert stats.latest_close == 200.0
    assert stats.week52_high == 210.0
    assert stats.week52_low == 190.0
    assert all(v is None for v in stats.returns.values())


def test_empty_series_raises() -> None:
    with pytest.raises(ValueError, match="at least one bar"):
        compute_price_stats([], as_of=date(2026, 6, 13))


def test_as_of_defaults_to_latest_bar_date() -> None:
    stats = compute_price_stats(_full_series())
    assert stats.as_of == date(2026, 6, 13)
    assert stats.latest_close == 150.0
