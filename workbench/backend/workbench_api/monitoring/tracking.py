"""B080 F002 — paper-vs-benchmark tracking error + turnover (pure, trade-free).

Tracking error = the volatility of the paper strategy's daily excess return over
its benchmark (SPY for the funded modes; CSI300 for the cn_attack research modes —
the CLI supplies the right benchmark series). Turnover reads the paper rebalance
log. All pure: the CLI feeds DB-read series in.
"""

from __future__ import annotations

from datetime import date
from typing import Any

# Per-strategy benchmark (spec §2 F002 / F004). The CN research modes are benchmarked to
# CSI300 (沪深300); the funded / US modes stay SPY. Keyed by strategy_id.
STRATEGY_BENCHMARK: dict[str, str] = {
    "cn_attack_quality_momentum": "CSI300",
    "cn_attack_pure_momentum": "CSI300",
    # B082 F003 — the 红利低波 defensive sleeve is an A-share mode, benchmarked to CSI300.
    "cn_dividend_lowvol": "CSI300",
    "master_portfolio": "SPY",
    "regime_adaptive": "SPY",
}


def _daily_returns(series: list[tuple[date, float]]) -> dict[date, float]:
    """``{date: level/prev_level - 1}`` for a date-sorted level series."""

    out: dict[date, float] = {}
    prev: float | None = None
    for d, level in sorted(series):
        if prev is not None and prev > 0:
            out[d] = level / prev - 1.0
        prev = level
    return out


def tracking_error(
    paper_navs: list[tuple[date, float]],
    benchmark: list[tuple[date, float]],
) -> dict[str, Any]:
    """Std of the daily ``(paper_return − benchmark_return)`` over dates present in
    BOTH series. ``{value, meta}``; ``value`` is ``None`` when < 2 overlapping days
    (partial → honest degrade)."""

    paper_ret = _daily_returns(paper_navs)
    bench_ret = _daily_returns(benchmark)
    common = sorted(set(paper_ret) & set(bench_ret))
    diffs = [paper_ret[d] - bench_ret[d] for d in common]
    meta: dict[str, Any] = {"overlap_days": len(diffs), "partial": len(diffs) < 20}
    if len(diffs) < 2:
        return {"value": None, "meta": meta}
    mean = sum(diffs) / len(diffs)
    var = sum((x - mean) ** 2 for x in diffs) / (len(diffs) - 1)
    return {"value": round(var**0.5, 6), "meta": meta}


def turnover_metrics(
    rebalances: list[tuple[date, float]],
    *,
    activated_on: date | None = None,
    as_of: date | None = None,
) -> dict[str, dict[str, Any]]:
    """Rebalance count / total + avg cost / annualised rebalance frequency from the
    paper rebalance log (``[(rebalance_date, cost), ...]``)."""

    n = len(rebalances)
    total_cost = round(sum(c for _, c in rebalances), 4)
    avg_cost = round(total_cost / n, 4) if n else None
    freq: float | None = None
    if activated_on and as_of and as_of > activated_on:
        years = (as_of - activated_on).days / 365.0
        freq = round(n / years, 3) if years > 0 else None
    return {
        "turnover_rebalance_count": {"value": float(n), "meta": {}},
        "turnover_total_cost": {"value": total_cost, "meta": {"avg_cost": avg_cost}},
        "turnover_rebalance_freq_yr": {"value": freq, "meta": {}},
    }
