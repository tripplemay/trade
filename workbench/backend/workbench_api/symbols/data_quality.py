"""B062 F003 — candidate-universe data-quality checks (§8 deep metrics).

Pure, network-free quality checks over already-fetched OHLCV series, so the
candidate A-share / HK universe can be **verified before it feeds any strategy**
(B061 deferred the §8 deep metrics; strategy scoring depends on reliable
full-history depth, correct adjustment, and cross-source consistency). The
runner (``scripts/test/ashare_quality_check.py``, executed by Codex on the VM in
F004) fetches via the providers and feeds these checks; this module stays pure
so the logic is unit-tested deterministically with synthetic samples.

request-path safe: stdlib + :class:`PriceBar` only — no akshare / trade import.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from workbench_api.data.snapshot_loader import PriceBar

# Cross-source agreement tolerance (akshare vs baostock same-day close), §8.3.
DEFAULT_CROSS_SOURCE_TOLERANCE = 0.005  # 0.5%
# Day-over-day adjusted-close move beyond this is a suspected data error (a true
# qfq series absorbs dividends/splits, so genuine moves rarely exceed this).
DEFAULT_JUMP_THRESHOLD = 0.35


@dataclass(frozen=True, slots=True)
class SymbolQualityReport:
    """Structured §8 quality verdict for one candidate symbol."""

    symbol: str
    rows: int
    first_date: str | None
    last_date: str | None
    history_years: float | None
    meets_history_floor: bool | None
    adjustment_available: bool | None
    cross_source_overlap_days: int
    cross_source_max_pct_dev: float | None
    cross_source_within_tolerance: bool | None
    suspicious_jumps: int


def history_years(bars: list[PriceBar]) -> float | None:
    """Span of the series in years (last - first), or None for < 2 bars."""
    if len(bars) < 2:
        return None
    ordered = sorted(bars, key=lambda b: b.bar_date)
    days = (ordered[-1].bar_date - ordered[0].bar_date).days
    return round(days / 365.25, 2)


def adjustment_available(
    qfq_bars: list[PriceBar], raw_bars: list[PriceBar]
) -> bool | None:
    """True when the front-adjusted (qfq) series differs from the raw series —
    i.e. the source actually applies adjustment. None when either is empty.

    Compares the earliest overlapping close: for any symbol with a historical
    dividend/split the qfq close diverges from the raw close; equal across the
    full history means no adjustment was applied."""
    if not qfq_bars or not raw_bars:
        return None
    qfq_by_date = {b.bar_date: b.close for b in qfq_bars}
    raw_by_date = {b.bar_date: b.close for b in raw_bars}
    common = sorted(set(qfq_by_date) & set(raw_by_date))
    if not common:
        return None
    earliest = common[0]
    return abs(qfq_by_date[earliest] - raw_by_date[earliest]) > 1e-6


def cross_source_deviation(
    primary: list[PriceBar], secondary: list[PriceBar]
) -> tuple[int, float | None]:
    """Same-day close agreement between two sources (akshare vs baostock).

    Returns ``(overlapping_days, max_abs_pct_deviation)``; the deviation is None
    when there is no overlapping day."""
    sec_by_date = {b.bar_date: b.close for b in secondary}
    deviations: list[float] = []
    for bar in primary:
        other = sec_by_date.get(bar.bar_date)
        if other is None or bar.close == 0:
            continue
        deviations.append(abs(other - bar.close) / abs(bar.close))
    if not deviations:
        return 0, None
    return len(deviations), max(deviations)


def count_suspicious_jumps(
    bars: list[PriceBar], threshold: float = DEFAULT_JUMP_THRESHOLD
) -> int:
    """Count day-over-day adjusted-close moves beyond ``threshold`` (suspected
    data errors in a qfq series)."""
    ordered = sorted(bars, key=lambda b: b.bar_date)
    jumps = 0
    for prev, cur in zip(ordered, ordered[1:], strict=False):
        if prev.adj_close == 0:
            continue
        if abs(cur.adj_close / prev.adj_close - 1.0) > threshold:
            jumps += 1
    return jumps


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def assess_symbol(
    symbol: str,
    *,
    qfq_bars: list[PriceBar],
    raw_bars: list[PriceBar] | None = None,
    cross_source_bars: list[PriceBar] | None = None,
    history_floor_years: float = 3.0,
    cross_source_tolerance: float = DEFAULT_CROSS_SOURCE_TOLERANCE,
    jump_threshold: float = DEFAULT_JUMP_THRESHOLD,
) -> SymbolQualityReport:
    """Aggregate the §8 quality metrics for one symbol into a report.

    ``qfq_bars`` is the front-adjusted primary series; ``raw_bars`` (optional)
    drives the adjustment check; ``cross_source_bars`` (optional, A-share's
    baostock series) drives cross-source agreement."""
    ordered = sorted(qfq_bars, key=lambda b: b.bar_date)
    years = history_years(ordered)
    overlap, max_dev = (
        cross_source_deviation(ordered, cross_source_bars)
        if cross_source_bars
        else (0, None)
    )
    return SymbolQualityReport(
        symbol=symbol,
        rows=len(ordered),
        first_date=_iso(ordered[0].bar_date) if ordered else None,
        last_date=_iso(ordered[-1].bar_date) if ordered else None,
        history_years=years,
        meets_history_floor=(years >= history_floor_years) if years is not None else None,
        adjustment_available=(
            adjustment_available(ordered, raw_bars) if raw_bars is not None else None
        ),
        cross_source_overlap_days=overlap,
        cross_source_max_pct_dev=max_dev,
        cross_source_within_tolerance=(
            max_dev <= cross_source_tolerance if max_dev is not None else None
        ),
        suspicious_jumps=count_suspicious_jumps(ordered, jump_threshold),
    )
