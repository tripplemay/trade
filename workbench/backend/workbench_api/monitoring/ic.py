"""B080 F002 — holdings-level rolling rank-IC (pure, testable).

The two cn_attack modes persist post-no-trade-band **holdings** (equal
target_weight), not the raw momentum score, so this measures the *holdings*
information coefficient — labelled ``fidelity="holdings"`` everywhere, not a pure
signal IC (spec §0). The three core functions (:func:`forward_returns`,
:func:`rank_ic`) are migrated verbatim from ``scripts/research/b077_signal_first_look.py``
(already unit-tested); the rolling-window + t-stat + partial-coverage helpers are
new. All pure — the CLI feeds them DB-read data so this module never touches the
DB or ``trade``.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

import numpy as np

# N-day forward-return horizons the panel reports.
HORIZONS: tuple[int, ...] = (5, 10, 20)
# Rolling window for the IC mean / t-stat (≈ 12 months of trading days).
ROLLING_WINDOW_DAYS = 365


def forward_returns(
    series: tuple[list[date], list[float]],
    event_date: date,
    horizons: tuple[int, ...] = HORIZONS,
) -> dict[int, float | None]:
    """``{N: close[t1+N]/close[t1] - 1}`` where ``t1`` is the first trading day
    STRICTLY AFTER ``event_date`` (no lookahead). ``None`` per N when the series
    runs out (a delisted name yields ``None`` for the longer N — correct)."""

    dates, closes = series
    entry = bisect.bisect_right(dates, event_date)
    out: dict[int, float | None] = {}
    for n in horizons:
        exit_idx = entry + n
        if entry < len(closes) and exit_idx < len(closes) and closes[entry] > 0:
            out[n] = closes[exit_idx] / closes[entry] - 1.0
        else:
            out[n] = None
    return out


def _average_ranks(values: np.ndarray) -> np.ndarray:
    """Average (tie-aware) ranks — the basis of Spearman."""

    order = values.argsort(kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(1, len(values) + 1, dtype=float)
    sorted_vals = values[order]
    i = 0
    n = len(values)
    while i < n:
        j = i
        while j + 1 < n and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        if j > i:
            ranks[order[i : j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    return ranks


def rank_ic(signals: list[float], returns: list[float]) -> float | None:
    """Spearman rank-IC = Pearson of the average-ranks. ``None`` on a degenerate
    (no-variance) cross-section or fewer than 2 pairs."""

    if len(signals) != len(returns) or len(signals) < 2:
        return None
    s = _average_ranks(np.asarray(signals, dtype=float))
    r = _average_ranks(np.asarray(returns, dtype=float))
    if s.std() == 0 or r.std() == 0:
        return None
    return float(np.corrcoef(s, r)[0, 1])


def holdings_ic_for_date(
    holdings: list[tuple[str, float]],
    price_series: dict[str, tuple[list[date], list[float]]],
    as_of: date,
    horizon: int,
) -> float | None:
    """Cross-sectional holdings-IC on one ``as_of``: rank of held weight vs the
    N-day forward return. ``holdings`` = ``[(symbol, target_weight), ...]`` (CASH
    already excluded by the caller); ``price_series`` maps symbol → (dates, closes).
    Symbols with no forward return at this horizon drop out."""

    signals: list[float] = []
    returns: list[float] = []
    for symbol, weight in holdings:
        series = price_series.get(symbol)
        if series is None:
            continue
        fwd = forward_returns(series, as_of, (horizon,)).get(horizon)
        if fwd is None:
            continue
        signals.append(weight)
        returns.append(fwd)
    return rank_ic(signals, returns)


def rolling_ic(
    dated_ics: Sequence[tuple[date, float | None]],
    as_of: date,
    window_days: int = ROLLING_WINDOW_DAYS,
) -> dict[str, Any]:
    """Rolling mean IC + t-stat over the trailing ``window_days`` ending ``as_of``.

    Returns ``{value, meta}`` where ``value`` is the mean IC (``None`` when no
    usable daily IC in the window) and ``meta`` carries the t-stat, sample count,
    and — critically — a ``partial`` flag + ``coverage_days`` when the available
    history is shorter than the window (honest degrade, never raises). ``fidelity``
    is stamped ``"holdings"`` by the caller/panel per spec §0.
    """

    cutoff = as_of - timedelta(days=window_days)
    window = [ic for d, ic in dated_ics if cutoff < d <= as_of and ic is not None]
    dates_all = [d for d, _ in dated_ics]
    earliest = min(dates_all) if dates_all else as_of
    coverage_days = (as_of - earliest).days
    partial = coverage_days < window_days
    meta: dict[str, Any] = {
        "n": len(window),
        "coverage_days": coverage_days,
        "window_days": window_days,
        "partial": partial,
    }
    if not window:
        meta["t_stat"] = None
        return {"value": None, "meta": meta}
    arr = np.asarray(window, dtype=float)
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    t_stat = float(mean * math.sqrt(len(arr)) / std) if std > 0 else None
    meta["t_stat"] = t_stat
    return {"value": round(mean, 6), "meta": meta}
