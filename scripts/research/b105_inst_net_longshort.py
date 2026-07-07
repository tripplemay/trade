#!/usr/bin/env python
"""B105 — does B104's inst_buy_net +0.15 rank-IC translate to a COST-SURVIVING tradeable
long-short return?

B104 (Codex-verified) found the per-event institutional net-buy (``inst_buy_net``, ¥
summed over "机构专用" seats) has a 5-day forward-return rank-IC of ~0.148 (t=2.92) /
10-day ~0.162 (t=2.84) on 485 price-covered pairs / 35 monthly cohorts — a REAL ranking
signal (higher inst_buy_net -> higher forward return). BUT B103's binary equal-weight
"follow all inst-buyers" backtest was NON-positive: a binary follow throws the RANKING
away. The resolution is a RANK-WEIGHTED dollar-neutral long-short (overweight high
inst_buy_net, short low), which mathematically captures the IC (portfolio return grows
with IC x cross-sectional return spread). This probe quantifies that gross return and
asks whether it SURVIVES realistic A-share small-cap LHB trading costs NET.

Machinery reuse (verbatim, NO re-fetch): the no-look-ahead cohort builder + inst_buy_net
loader come from B103 (``b103_lhb_inst_ic``), which imports B094's verified primitives
(``forward_returns`` bisect_right entry STRICTLY T+1, ``rank_ic``, ``_avg_ranks``,
``_tstat``, ``load_prices``, monthly cohorts). Only the PORTFOLIO layer is new here.

Portfolio construction (deliberately simple + standard):
  * Each monthly cohort, take the names with a known ``inst_buy_net`` and a valid N-day
    forward return. Rank them cross-sectionally by inst_buy_net (average ranks for ties).
  * DEMEAN the ranks (d_i = rank_i - mean_rank) so the book is DOLLAR-NEUTRAL (sum w = 0),
    then NORMALIZE to unit gross exposure (sum|w| = 1): w_i = d_i / sum_j|d_j|. This is the
    standard rank-weighted long-short: monotone increasing in inst_buy_net, longs the top
    names, shorts the bottom, uses ALL pairs (not thin quintiles).
  * GROSS cohort return = sum_i w_i * fwd_ret_i. Hold to the horizon (5d primary, 10d),
    enter T+1 (no look-ahead). Rebalance monthly -> the per-cohort returns are a
    monthly-frequency P&L series; cumulative = prod(1+r)-1; annualized Sharpe = mean/sd *
    sqrt(12).

Cost model (honest, A-share small/active LHB names):
  * Gross exposure is normalized to sum|w| = 1, so opening the book trades 1.0 unit of
    notional and closing it trades 1.0 unit -> exactly ONE round-trip of 1.0 notional per
    monthly cohort. NET cohort return = GROSS - round_trip_bps * 1.0.
  * Central round-trip = 40bp. Justification (round-trip = buy leg + sell leg):
      - commission ~2.5bp/side x2                = 5bp
      - stamp duty 5bp (sell side only, post-2023-08 A-share rate)
      - slippage / market impact on small, often limit-active LHB names ~15bp/side x2 = 30bp
      => ~40bp central; 30bp optimistic (liquid names / patient fills), 50bp realistic-high,
         80bp conservative (hard-to-trade 涨停 names). Reported as a 30/40/50/80 sensitivity.

Honesty (unchanged from B103/B104): FREE akshare LHB, 2022-2024, survivorship-limited
(delisted names omitted), LHB-selection-conditioned (already-moved names). A net-positive
here is an UPPER BOUND, NOT tradeable, NOT survivorship-clean. The paid Tushare ¥200
full-history LHB (2005+, delisted, ~50x sample, cleaner seats) remains the decisive clean
test. research-only / no broker / no production.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

# Reuse the VERIFIED no-look-ahead machinery (B103 -> B094). NO re-fetch, NO new stats core.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import b103_lhb_inst_ic as b103  # noqa: E402
from b094_youzi_ic import (  # noqa: E402
    HORIZONS,
    _avg_ranks,
    _tstat,
    load_prices,
    rank_ic,
)

logger = logging.getLogger(__name__)

_MIN_NAMES = 5            # min cross-sectional names per cohort (matches B094 monthly_ic)
_MONTHS_PER_YEAR = 12     # cohorts are monthly -> sqrt(12) Sharpe annualization
_CENTRAL_BPS = 40.0       # central round-trip cost (see module docstring justification)
_SENSITIVITY_BPS = (30.0, 40.0, 50.0, 80.0)
_GROSS_EXPOSURE = 1.0     # sum|w| normalization -> exactly one round-trip / cohort


# --------------------------------------------------------------------------- #
# Portfolio layer (the ONLY new logic; the no-look-ahead core is imported).
# --------------------------------------------------------------------------- #
def rank_weights(signals: list[float]) -> np.ndarray | None:
    """Rank-weighted DOLLAR-NEUTRAL long-short weights from a cross-section of signals.

    w_i = (rank_i - mean_rank) / sum_j|rank_j - mean_rank|. Properties (all asserted in
    tests): sum(w) == 0 (dollar-neutral), sum|w| == 1 (unit gross exposure), and w is
    MONOTONE increasing in the signal (higher inst_buy_net -> larger long weight). Returns
    None on a degenerate cross-section (<2 names or all signals tied)."""
    arr = np.asarray(signals, dtype=float)
    if len(arr) < 2:
        return None
    ranks = _avg_ranks(arr)                 # average ranks (ties -> mean rank), from B094
    demeaned = ranks - ranks.mean()
    denom = float(np.abs(demeaned).sum())
    if denom == 0.0:                         # all signals equal -> no cross-sectional bet
        return None
    return demeaned / denom


def longshort_series(cohorts: dict[str, list[dict[str, Any]]], n: int,
                     min_names: int = _MIN_NAMES) -> list[dict[str, Any]]:
    """Per-monthly-cohort GROSS long-short return for horizon N (rank-weighted on
    inst_buy_net). Also records the cohort rank-IC so IC->return consistency is testable.

    No look-ahead: fwd returns come from B103/B094 forward_returns (entry STRICTLY T+1)."""
    out: list[dict[str, Any]] = []
    for month, rows in sorted(cohorts.items()):
        pairs = [(row["inst_buy_net"], row["fwd"][n]) for row in rows
                 if row.get("inst_buy_net") is not None and row["fwd"][n] is not None]
        if len(pairs) < min_names:
            continue
        sigs = [float(p[0]) for p in pairs]
        rets = [float(p[1]) for p in pairs]
        weights = rank_weights(sigs)
        if weights is None:
            continue
        gross = float(np.dot(weights, np.asarray(rets, dtype=float)))
        cohort_ic = rank_ic(sigs, rets)
        out.append({
            "month": month,
            "n_names": len(pairs),
            "gross_ret": gross,
            "cohort_ic": round(cohort_ic, 4) if cohort_ic is not None else None,
        })
    return out


def _cumulative(returns: list[float]) -> float:
    """Compounded cumulative return prod(1+r) - 1 over the cohort P&L series."""
    total = 1.0
    for r in returns:
        total *= 1.0 + r
    return total - 1.0


def _annualized_sharpe(returns: list[float]) -> float | None:
    """Monthly-cohort Sharpe annualized by sqrt(12). None on <2 obs or zero variance."""
    if len(returns) < 2:
        return None
    arr = np.asarray(returns, dtype=float)
    sd = arr.std(ddof=1)
    if sd == 0:
        return None
    return float(arr.mean() / sd * math.sqrt(_MONTHS_PER_YEAR))


def _annualized_return(cum: float, n_months: int) -> float | None:
    """CAGR from cumulative return over n_months monthly cohorts."""
    if n_months <= 0 or (1.0 + cum) <= 0:
        return None
    return float((1.0 + cum) ** (_MONTHS_PER_YEAR / n_months) - 1.0)


def net_returns(gross: list[float], round_trip_bps: float,
                gross_exposure: float = _GROSS_EXPOSURE) -> list[float]:
    """Charge a round-trip cost on the full unit-gross book, once per monthly cohort.

    One round-trip of `gross_exposure` notional per cohort (open + close). NET is strictly
    below GROSS whenever round_trip_bps > 0."""
    cost = round_trip_bps / 10_000.0 * gross_exposure
    return [g - cost for g in gross]


def summarize_horizon(series: list[dict[str, Any]]) -> dict[str, Any]:
    """GROSS + NET (central + full sensitivity) summary for one horizon."""
    gross = [row["gross_ret"] for row in series]
    n_months = len(gross)
    if n_months == 0:
        return {"n_cohorts": 0, "thin": True}

    gross_cum = _cumulative(gross)
    gross_sharpe = _annualized_sharpe(gross)
    gross_t = _tstat(gross)
    gross_mean = float(np.mean(gross))

    sensitivity: dict[str, Any] = {}
    for bps in _SENSITIVITY_BPS:
        net = net_returns(gross, bps)
        net_cum = _cumulative(net)
        sensitivity[f"{int(bps)}bp"] = {
            "net_mean_monthly_ret": round(float(np.mean(net)), 5),
            "net_cum_ret": round(net_cum, 4),
            "net_ann_ret": (round(v, 4) if (v := _annualized_return(net_cum, n_months))
                            is not None else None),
            "net_ann_sharpe": (round(s, 3) if (s := _annualized_sharpe(net)) is not None
                               else None),
            "net_positive": net_cum > 0,
        }

    central = sensitivity[f"{int(_CENTRAL_BPS)}bp"]
    return {
        "n_cohorts": n_months,
        "thin": n_months < 6,
        "avg_names_per_cohort": round(float(np.mean([r["n_names"] for r in series])), 1),
        "gross_mean_monthly_ret": round(gross_mean, 5),
        "gross_cum_ret": round(gross_cum, 4),
        "gross_ann_ret": (round(v, 4) if (v := _annualized_return(gross_cum, n_months))
                          is not None else None),
        "gross_ann_sharpe": round(gross_sharpe, 3) if gross_sharpe is not None else None,
        "gross_t_stat": round(gross_t, 2) if gross_t is not None else None,
        "months_gross_positive": int(sum(1 for g in gross if g > 0)),
        "turnover": {
            "round_trips_per_cohort": _GROSS_EXPOSURE,
            "gross_exposure_sum_abs_w": _GROSS_EXPOSURE,
            "round_trips_per_year": _MONTHS_PER_YEAR,
            "note": ("Cohorts are independent (enter T+1, exit T+1+N, flat between) -> "
                     "exactly ONE round-trip of unit-gross notional per monthly cohort; "
                     f"~{_MONTHS_PER_YEAR} round-trips/yr. Annual cost drag ~= "
                     f"{_MONTHS_PER_YEAR} x round_trip_bps (e.g. 40bp -> ~4.8%/yr)."),
        },
        "central_bps": _CENTRAL_BPS,
        "net_central": central,
        "cost_sensitivity": sensitivity,
    }


def ic_return_consistency(series: list[dict[str, Any]]) -> dict[str, Any]:
    """Sanity check that the long-short return TRACKS the rank-IC it is meant to harvest:
    per cohort, the rank-weighted return and the rank-IC should share sign on average, and
    their cross-cohort correlation should be POSITIVE. This confirms the portfolio actually
    monetizes the IC (not some unrelated artifact)."""
    ics = [row["cohort_ic"] for row in series if row["cohort_ic"] is not None]
    rets = [row["gross_ret"] for row in series if row["cohort_ic"] is not None]
    if len(ics) < 2:
        return {"n": len(ics), "thin": True}
    corr = None
    if np.std(ics) > 0 and np.std(rets) > 0:
        corr = float(np.corrcoef(ics, rets)[0, 1])
    same_sign = sum(1 for a, b in zip(ics, rets, strict=True) if (a > 0) == (b > 0))
    return {
        "n_cohorts": len(ics),
        "mean_cohort_ic": round(float(np.mean(ics)), 4),
        "mean_gross_ret": round(float(np.mean(rets)), 5),
        "corr_ic_vs_lsret": round(corr, 3) if corr is not None else None,
        "cohorts_same_sign": same_sign,
        "same_sign_rate": round(same_sign / len(ics), 3),
        "note": ("Positive corr + majority same-sign => the rank-weighted L/S return is the "
                 "monetization of the inst_buy_net rank-IC, as intended."),
    }


# --------------------------------------------------------------------------- #
# Verdict.
# --------------------------------------------------------------------------- #
def judge(summaries: dict[str, Any]) -> dict[str, Any]:
    """Does the +0.15 IC translate to a GROSS long-short return (it should) and SURVIVE
    realistic costs NET?

      * GO (cost-surviving, survivorship-caveated) — headline horizons show a POSITIVE
        GROSS return AND, at the CENTRAL 40bp round-trip, a POSITIVE net cumulative return
        with net annualized Sharpe >= 0.5 that also stays positive at 50bp. The IC is a
        cost-surviving edge on free data -> strengthens the paid ¥200 case. NOT tradeable.
      * INCONCLUSIVE — GROSS positive but NET only marginally so at 40bp (Sharpe < 0.5) or
        it flips negative by 50bp -> the edge exists but is on the cost knife-edge; the
        clean, lower-friction paid ¥200 test decides.
      * NO-GO (costs eat it) — GROSS positive (IC is real) but NET goes NON-positive at the
        central 40bp -> the IC exists but is NOT cheaply tradeable on these small/active
        free-data names. Still consistent with pursuing the cleaner paid ¥200 seats.
      * NO-GROSS — GROSS itself non-positive at the headline horizons -> the IC did NOT
        translate as expected (would contradict B104; investigate)."""
    headline = [h for h in ("N5", "N10") if not summaries.get(h, {}).get("thin", True)]
    gross_pos = [h for h in headline if summaries[h]["gross_cum_ret"] > 0]

    def _net(h: str, bp: int) -> dict[str, Any]:
        return summaries[h]["cost_sensitivity"][f"{bp}bp"]

    net40_pos = [h for h in headline if _net(h, 40)["net_positive"]]
    net40_sharpe_ok = [h for h in net40_pos
                       if (_net(h, 40)["net_ann_sharpe"] or 0) >= 0.5]
    net50_pos = [h for h in headline if _net(h, 50)["net_positive"]]

    if not gross_pos:
        verdict = "NO-GROSS"
        reason = ("The GROSS rank-weighted long-short return is NON-positive at the headline "
                  "horizons — the +0.15 IC did NOT translate into a positive spread, which "
                  "would CONTRADICT B104's IC. Investigate construction before any cost read.")
    elif net40_pos and net40_sharpe_ok and net50_pos:
        verdict = "GO"
        reason = (
            f"GROSS long-short is positive at {gross_pos} and, at the CENTRAL 40bp round-trip, "
            f"NET stays positive with annualized Sharpe>=0.5 at {net40_sharpe_ok} and remains "
            f"net-positive even at 50bp ({net50_pos}). B104's inst_buy_net IC is a "
            "COST-SURVIVING long-short edge on FREE data -> STRENGTHENS the paid ¥200 case. "
            "Survivorship UPPER BOUND, NOT tradeable, NOT survivorship-clean.")
    elif net40_pos:
        verdict = "INCONCLUSIVE"
        reason = (
            f"GROSS is positive at {gross_pos} and NET is still positive at 40bp ({net40_pos}) "
            "but only MARGINALLY (annualized Sharpe<0.5 and/or it flips negative by 50bp) — the "
            "edge sits on the cost knife-edge. The cleaner, lower-friction paid Tushare ¥200 "
            "full-history LHB is the deciding test.")
    else:
        verdict = "NO-GO"
        reason = (
            f"GROSS is positive at {gross_pos} (the IC is REAL, consistent with B104) but NET "
            "goes NON-positive at the central 40bp round-trip: costs EAT the edge on these "
            "small/active free-data names. The signal exists but is NOT cheaply tradeable here. "
            "The paid ¥200 clean seats (deeper, cleaner, potentially lower-friction slice) "
            "remain the decisive test.")
    return {
        "verdict": verdict,
        "headline_horizons": headline,
        "gross_positive_horizons": gross_pos,
        "net_positive_at_40bp": net40_pos,
        "net_sharpe_ge_0p5_at_40bp": net40_sharpe_ok,
        "net_positive_at_50bp": net50_pos,
        "central_round_trip_bps": _CENTRAL_BPS,
        "reason": reason,
    }


def run(*, events_csv: Path, prices_csv: Path, seats_csv: Path | None,
        horizons: tuple[int, ...] = HORIZONS) -> dict[str, Any]:
    events = b103.load_events(events_csv, seats_csv)
    prices = load_prices(prices_csv)
    built = b103.build_cohorts(events, prices, horizons)
    cohorts = built["cohorts"]

    summaries: dict[str, Any] = {}
    consistency: dict[str, Any] = {}
    for n in horizons:
        series = longshort_series(cohorts, n)
        summaries[f"N{n}"] = summarize_horizon(series)
        consistency[f"N{n}"] = ic_return_consistency(series)
    verdict = judge(summaries)

    n_net_sampled = sum(1 for e in events if e.inst_buy_net is not None)
    return {
        "probe": "b105_inst_net_longshort",
        "question": ("Does B104's inst_buy_net +0.15 rank-IC translate to a positive GROSS "
                     "rank-weighted long-short return, and does it SURVIVE realistic A-share "
                     "small-cap LHB costs NET?"),
        "construction": ("monthly cohorts; rank names by inst_buy_net; demeaned-rank weights "
                         "normalized to sum|w|=1 (dollar-neutral, unit gross); GROSS = sum "
                         "w_i*fwd_i; enter T+1 (no look-ahead); monthly rebalance; sqrt(12) "
                         "annualization"),
        "cost_model": ("round-trip on unit-gross book once per cohort; central 40bp "
                       "(2.5bp/side commission + 5bp sell stamp duty + ~15bp/side small-cap "
                       "slippage); 30/40/50/80bp sensitivity"),
        "no_lookahead": ("reused verbatim from B103/B094: LHB list for T disclosed AFTER close "
                         "T; entry T+1 (bisect_right, strictly > T); fwd ret strictly > T"),
        "horizons": list(horizons),
        "coverage": built["coverage"],
        "inst_net_sampled_events": n_net_sampled,
        "longshort_by_horizon": summaries,
        "ic_return_consistency": consistency,
        "verdict": verdict,
        "honesty": (
            "FREE akshare LHB, 2022-2024, survivorship-limited (delisted omitted), "
            "LHB-selection-conditioned (already-moved names). Even a net-positive is an UPPER "
            "BOUND, NOT tradeable, NOT survivorship-clean, and ignores borrow availability / "
            "shorting frictions on the A-share short leg (a real constraint on this exact "
            "long-short). The paid Tushare ¥200 full-history LHB (2005+, delisted, ~50x "
            "sample, cleaner seats) remains the DECISIVE clean test. research-only / no broker."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="B105 inst_buy_net rank-weighted long-short cost-survival test")
    parser.add_argument("--events", type=Path,
                        default=Path("data/research/b094_youzi/events.csv"))
    parser.add_argument("--prices", type=Path,
                        default=Path("data/research/b094_youzi/prices.csv"))
    parser.add_argument("--seats", type=Path,
                        default=Path("data/research/b104_seats/seats_expanded.csv"))
    parser.add_argument("--out", type=Path, default=None)
    cli = parser.parse_args(argv)

    result = run(events_csv=cli.events, prices_csv=cli.prices,
                 seats_csv=cli.seats if cli.seats.exists() else None)
    text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    print(text)
    if cli.out:
        cli.out.parent.mkdir(parents=True, exist_ok=True)
        cli.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
