"""B059 F001 — pure price-statistics helpers.

Derives the headline numbers the detail page shows from a cached OHLCV
series: the latest EOD close, the trailing 52-week intraday high / low, and
total-return windows (1M / 3M / 6M / 1Y / YTD). All pure functions over a
list of :class:`PriceBar` — no DB, no network — so they unit-test directly
and stay source-agnostic.

Returns are total returns ``latest_close / base_close - 1`` where ``base`` is
the close on the latest trading day **on or before** the window's start date
(tolerating weekends / holidays). A window whose start predates the series
yields ``None`` — we degrade honestly rather than fabricate (v0.9.21).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from workbench_api.data.snapshot_loader import PriceBar

_WEEK52_DAYS = 365

# (label, lookback days); ``None`` days means YTD (base = close on/before Jan 1).
_RETURN_WINDOWS: tuple[tuple[str, int | None], ...] = (
    ("1M", 30),
    ("3M", 91),
    ("6M", 182),
    ("1Y", 365),
    ("YTD", None),
)


@dataclass(frozen=True, slots=True)
class PriceStats:
    latest_close: float
    as_of: date
    week52_high: float | None
    week52_low: float | None
    returns: dict[str, float | None]


def compute_price_stats(
    bars: list[PriceBar], *, as_of: date | None = None
) -> PriceStats:
    """Compute headline stats from ``bars``. ``as_of`` anchors the windows
    (defaults to the latest bar's date)."""

    if not bars:
        raise ValueError("compute_price_stats requires at least one bar")

    ordered = sorted(bars, key=lambda b: b.bar_date)
    latest = ordered[-1]
    ref = as_of or latest.bar_date
    latest_close = latest.close

    window_start = ref - timedelta(days=_WEEK52_DAYS)
    window_bars = [b for b in ordered if b.bar_date >= window_start]
    week52_high = max((b.high for b in window_bars), default=None)
    week52_low = min((b.low for b in window_bars), default=None)

    returns: dict[str, float | None] = {}
    for label, days in _RETURN_WINDOWS:
        target = date(ref.year, 1, 1) if days is None else ref - timedelta(days=days)
        base = _close_on_or_before(ordered, target)
        if base is None or base == 0.0:
            returns[label] = None
        else:
            returns[label] = latest_close / base - 1.0

    return PriceStats(
        latest_close=latest_close,
        as_of=latest.bar_date,
        week52_high=week52_high,
        week52_low=week52_low,
        returns=returns,
    )


def _close_on_or_before(ordered_bars: list[PriceBar], target: date) -> float | None:
    """Return the close on the latest ``bar_date <= target`` (``ordered_bars``
    must be ascending), or ``None`` when no bar is at/ before ``target``."""

    chosen: float | None = None
    for bar in ordered_bars:
        if bar.bar_date <= target:
            chosen = bar.close
        else:
            break
    return chosen
