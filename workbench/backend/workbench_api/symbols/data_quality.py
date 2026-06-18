"""B062 F003 — candidate-universe data-quality checks (§8 deep metrics).

Pure, network-free quality checks over already-fetched OHLCV series, so the
candidate A-share / HK universe can be **verified before it feeds any strategy**
(B061 deferred the §8 deep metrics; strategy scoring depends on reliable
full-history depth, correct adjustment, and cross-source consistency). The
runner (``scripts/test/ashare_quality_check.py``, executed by Codex on the VM in
F004) fetches via the providers and feeds these checks; this module stays pure
so the logic is unit-tested deterministically with synthetic samples.

**qfq canonical (B065 F003):** akshare ``adjust="qfq"`` (前复权) is the canonical
A-share price series — it is what the CN provider (B061/B062) and the trade
pipeline use everywhere, so the strategy and the lookup surface stay consistent.
B063 found the raw akshare-vs-baostock close levels disagree 2–60%; F003 adds two
**anchor-robust** lenses (daily-return + re-anchored-close deviation) that remove
the front-adjustment-base (口径) offset, so cross-source agreement can be measured
honestly. Where even the re-anchored residual stays large the discrepancy is a
genuine methodology/data difference — kept honest (not forced to <0.5%), with
akshare qfq retained as canonical. The real akshare↔baostock numbers are measured
on the VM by Codex (F004); baostock is CN-only (no HK cross-source).

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
    # B065 F003 — anchor-robust alignment lenses (the raw level dev above is the
    # B063 measure that saw 2–60%; these isolate the adjustment-anchor 口径).
    cross_source_return_max_dev: float | None
    cross_source_return_within_tolerance: bool | None
    cross_source_reanchored_max_pct_dev: float | None
    cross_source_reanchored_within_tolerance: bool | None
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


def _daily_returns(bars: list[PriceBar]) -> dict[date, float]:
    """date -> daily adjusted-close return. **Anchor-invariant**: two qfq series
    of the same underlying have identical daily returns regardless of which date
    the front-adjustment is anchored to, so this isolates a genuine data
    discrepancy from a pure adjustment-base (口径) offset."""

    ordered = sorted(bars, key=lambda b: b.bar_date)
    out: dict[date, float] = {}
    for prev, cur in zip(ordered, ordered[1:], strict=False):
        if prev.adj_close != 0:
            out[cur.bar_date] = cur.adj_close / prev.adj_close - 1.0
    return out


def cross_source_return_deviation(
    primary: list[PriceBar], secondary: list[PriceBar]
) -> tuple[int, float | None]:
    """Max abs **daily-return** difference between two sources (B065 F003).

    akshare qfq and baostock 前复权 can disagree on close *levels* (B063 found
    2–60%) because they anchor the front-adjustment differently, yet still track
    the same underlying. Comparing daily returns removes that anchor offset, so a
    small return deviation means the two sources agree up to 口径 (the level gap
    is a documented adjustment-base artifact, not a data error). Returns
    ``(overlapping_days, max_abs_return_diff)``; ``None`` when no overlap."""

    primary_returns = _daily_returns(primary)
    secondary_returns = _daily_returns(secondary)
    common = sorted(set(primary_returns) & set(secondary_returns))
    deviations = [abs(primary_returns[day] - secondary_returns[day]) for day in common]
    if not deviations:
        return 0, None
    return len(deviations), max(deviations)


def cross_source_reanchored_deviation(
    primary: list[PriceBar], secondary: list[PriceBar]
) -> tuple[int, float | None]:
    """Max abs pct close deviation after **re-anchoring** ``secondary`` to
    ``primary`` at their latest common day (B065 F003).

    If the two sources differ only by their front-adjustment anchor (口径), a
    single multiplicative re-scale at the latest overlap makes the historical
    closes line up — the residual deviation then measures genuine agreement. If
    it stays large, the discrepancy is a real methodology/data difference (kept
    honest, not forced to <0.5%). Returns ``(overlapping_days, max_pct_dev)``."""

    primary_close = {b.bar_date: b.close for b in primary}
    secondary_close = {b.bar_date: b.close for b in secondary}
    common = sorted(set(primary_close) & set(secondary_close))
    if not common:
        return 0, None
    anchor = common[-1]
    if secondary_close[anchor] == 0:
        return 0, None
    scale = primary_close[anchor] / secondary_close[anchor]
    deviations = [
        abs(secondary_close[day] * scale - primary_close[day]) / abs(primary_close[day])
        for day in common
        if primary_close[day] != 0
    ]
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
    _, return_dev = (
        cross_source_return_deviation(ordered, cross_source_bars)
        if cross_source_bars
        else (0, None)
    )
    _, reanchored_dev = (
        cross_source_reanchored_deviation(ordered, cross_source_bars)
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
        cross_source_return_max_dev=return_dev,
        cross_source_return_within_tolerance=(
            return_dev <= cross_source_tolerance if return_dev is not None else None
        ),
        cross_source_reanchored_max_pct_dev=reanchored_dev,
        cross_source_reanchored_within_tolerance=(
            reanchored_dev <= cross_source_tolerance if reanchored_dev is not None else None
        ),
        suspicious_jumps=count_suspicious_jumps(ordered, jump_threshold),
    )
