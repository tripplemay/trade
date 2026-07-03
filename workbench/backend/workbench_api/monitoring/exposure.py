"""B080 F002 — market-cap exposure / crowding metrics (pure, trade-free).

Answers the 2024-02 micro-cap-stampede lesson (spec §0): monitor how small / how
concentrated the paper holdings are. Reads a point-in-time market-cap cross-section
(``cn_size.csv``: ``data_date, ticker, market_cap``) with the same PIT caliber as
``trade.strategies.cn_attack_momentum_quality.size`` (latest ``data_date <= as_of``
per ticker) — replicated here as a tiny groupby-last so the monitoring package
stays free of ``trade`` (§12.10.2). Industry/sector exposure is deliberately out of
scope (fundamentals_cache isolation red line).
"""

from __future__ import annotations

from datetime import date
from typing import Any


def pit_universe_caps(
    rows: list[tuple[date, str, float]], as_of: date
) -> dict[str, float]:
    """PIT market cap per ticker = the latest ``data_date <= as_of`` row's cap.

    ``rows`` = ``[(data_date, ticker, market_cap), ...]`` (the parsed cn_size CSV).
    """

    latest: dict[str, tuple[date, float]] = {}
    for data_date, ticker, cap in rows:
        if data_date > as_of:
            continue
        prev = latest.get(ticker)
        if prev is None or data_date > prev[0]:
            latest[ticker] = (data_date, cap)
    return {ticker: cap for ticker, (_, cap) in latest.items()}


def _percentile_rank(sorted_caps: list[float], cap: float) -> float:
    """Fraction of the universe with a cap ≤ ``cap`` (0..1)."""

    import bisect

    if not sorted_caps:
        return 0.0
    return bisect.bisect_right(sorted_caps, cap) / len(sorted_caps)


def exposure_metrics(
    holdings: list[tuple[str, float]], universe_caps: dict[str, float]
) -> dict[str, dict[str, Any]]:
    """``{metric: {value, meta}}`` for median market-cap percentile, small-cap
    fraction, and HHI concentration, from ``holdings`` = ``[(symbol, weight), ...]``
    and the PIT ``universe_caps`` (symbol → market cap).

    - ``exposure_median_cap_pctile`` — median (over held names) of each name's
      market-cap percentile in the universe (low → small-cap tilted).
    - ``exposure_smallcap_frac`` — fraction of held names below the universe median
      cap.
    - ``exposure_hhi`` — Σ weight² (higher → more concentrated).
    """

    hhi = round(sum(w * w for _, w in holdings), 6) if holdings else None
    sorted_caps = sorted(universe_caps.values())
    universe_median = (
        sorted_caps[len(sorted_caps) // 2] if sorted_caps else None
    )
    held_caps = [
        (sym, universe_caps[sym]) for sym, _ in holdings if sym in universe_caps
    ]
    n_covered = len(held_caps)
    covered_meta = {"held": len(holdings), "cap_covered": n_covered}

    if not held_caps:
        pctile_value: float | None = None
        smallcap_value: float | None = None
    else:
        pctiles = sorted(_percentile_rank(sorted_caps, cap) for _, cap in held_caps)
        pctile_value = round(pctiles[len(pctiles) // 2], 4)
        if universe_median is None:
            smallcap_value = None
        else:
            below = sum(1 for _, cap in held_caps if cap < universe_median)
            smallcap_value = round(below / n_covered, 4)

    return {
        "exposure_median_cap_pctile": {"value": pctile_value, "meta": covered_meta},
        "exposure_smallcap_frac": {"value": smallcap_value, "meta": covered_meta},
        "exposure_hhi": {"value": hhi, "meta": {"held": len(holdings)}},
    }
