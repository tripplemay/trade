#!/usr/bin/env python
"""B102 — insider-BUYING signal on the SMALL-CAP sleeve: announcement-lagged rank-IC
(5/20/60d) + event/magnitude long backtest vs a small-cap equal-weight baseline, reported
GROSS and NET of a realistic small-cap round-trip cost.

REUSE (no re-implementation of the no-look-ahead core): the cohort/entry/forward-return
machinery is imported verbatim from ``b101_insider_ic`` — same rule that an event is
bucketed by ANNOUNCEMENT month M and the cohort ENTERS on the first trading day of month
M+1 (strictly AFTER every announcement in the cohort; NO look-ahead). Only the price panel
differs: here it is the B102 small-cap fetch, not the B101 liquid panel.

★ TWO SMALL-CAP-SPECIFIC HONEST CAVEATS (both disclosed in every output):
  1. SURVIVORSHIP (upward): ak.stock_zh_a_daily only returns CURRENTLY-listed names;
     delisted small-caps are absent. Small-caps delist more, so any edge here is an
     OPTIMISTIC UPPER BOUND. Unfixable with free data.
  2. LIQUIDITY COST: small-caps are expensive to trade. We charge a realistic ROUND-TRIP
     cost each monthly rebalance on the ACTIVE (insider-following) long book, which turns
     over ~fully every month as the buyer cohort changes. Default 50bp; a 30/50/80bp
     sensitivity is reported. Cost justification (small-cap A-share, round-trip):
        commission ~2.5bp/side (round-trip 5bp)
      + stamp duty 5bp (sell only, post-2023-08 halving)
      + transfer/过户 ~0.1bp (negligible)
      + bid-ask half-spread ~15-20bp/side on a thin small-cap (round-trip 30-40bp)
      + residual market impact on low-ADV names (a few bp)
      => ~40-50bp round-trip central estimate; 50bp is a conservative-but-not-extreme base.
     The passive small-cap BASELINE is a buy-and-hold equal weight (low turnover) and is
     left GROSS, so NET excess = active-net-cum minus baseline-gross-cum is the honest
     deployable comparison (active pays its high turnover; passive barely trades).

research-only / no broker / no real money / no production change / no paid data.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

# Reuse the B101 no-look-ahead core VERBATIM (announcement-lagged cohort + fwd returns).
from scripts.research.b101_insider_ic import (
    _HORIZONS,
    _compound,
    load_events,
    run,
)

logger = logging.getLogger(__name__)

_DIR = Path("data/research/b102_smallcap")
_PRICES_PKL = _DIR / "prices.pkl"
_OUT = _DIR / "ic_result.json"

# Realistic small-cap round-trip trading cost (basis points). See module docstring.
_COST_BPS_BASE = 50.0
_COST_BPS_GRID = (30.0, 50.0, 80.0)


def load_smallcap_prices_wide() -> Any:
    """Small-cap long-form price panel -> wide (date x code) adj_close. Same shape the
    B101 ``run`` expects; only the underlying names differ."""
    import pandas as pd

    px = pd.read_pickle(_PRICES_PKL)
    wide = px.pivot_table(index="date", columns="code", values="adj_close", aggfunc="last")
    return wide.sort_index()


def apply_cost(per_month_rets: list[float], cost_bps: float) -> dict[str, Any]:
    """Charge a round-trip cost each monthly rebalance on the active long book (assume
    ~full turnover: the insider-buyer cohort is re-formed monthly). Returns net per-period
    mean + net compounded path."""
    c = cost_bps / 10_000.0
    net = [r - c for r in per_month_rets]
    return {
        "cost_bps": cost_bps,
        "net_mean_ret": round(sum(net) / len(net), 4) if net else None,
        "net_cum_ret": round(_compound(net), 4) if net else None,
    }


def net_of_cost_block(result: dict[str, Any], event_rets: list[float],
                      mag_rets: list[float], base_cum_gross: float | None,
                      cost_bps: float) -> dict[str, Any]:
    """GROSS-vs-NET block for one horizon at one cost level. Baseline stays GROSS (passive,
    low-turnover); active books pay the round-trip each rebalance."""
    ev_net = apply_cost(event_rets, cost_bps)
    mag_net = apply_cost(mag_rets, cost_bps)
    return {
        "cost_bps": cost_bps,
        "event_net_cum": ev_net["net_cum_ret"],
        "mag_net_cum": mag_net["net_cum_ret"],
        "baseline_gross_cum": round(base_cum_gross, 4) if base_cum_gross is not None else None,
        "event_net_excess_vs_baseline": (
            round(ev_net["net_cum_ret"] - base_cum_gross, 4)
            if ev_net["net_cum_ret"] is not None and base_cum_gross is not None else None),
        "mag_net_excess_vs_baseline": (
            round(mag_net["net_cum_ret"] - base_cum_gross, 4)
            if mag_net["net_cum_ret"] is not None and base_cum_gross is not None else None),
    }


def _per_month_rets(run_result: dict[str, Any], key: str) -> list[float]:
    """Pull the per-month realized returns (scored months only) out of a B101 run dict."""
    return [m[key] for m in run_result["per_month"] if m.get(key) is not None]


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ev = load_events()
    wide = load_smallcap_prices_wide()
    ev = ev[ev["code"].isin(set(wide.columns))].copy()

    result: dict[str, Any] = {
        "sleeve": "SMALL-CAP (non-B070-liquid) insider-buying sleeve",
        "prior": (
            "Same signal as B101 (PRIMARY buy_pct = summed 占总股本比例 per stock/month, "
            "cross-sectional rank; SECONDARY n_events). Cohort entry = first trading day "
            "of month AFTER announcement month (no look-ahead). Prior: small-caps are "
            "WHERE insider signal should concentrate if it exists anywhere free."),
        "n_events_in_universe": int(len(ev)),
        "n_stocks_in_universe": int(ev["code"].nunique()),
        "cost_model": {
            "base_bps": _COST_BPS_BASE,
            "grid_bps": list(_COST_BPS_GRID),
            "basis": (
                "small-cap A-share round-trip: commission ~5bp + stamp 5bp (sell) + "
                "spread ~30-40bp + impact; charged each monthly rebalance on the active "
                "long book (~full turnover); passive baseline left gross"),
        },
        "survivorship_caveat": (
            "UPWARD bias: ak.stock_zh_a_daily returns only currently-listed names; "
            "delisted small-caps absent. Measured edge is an OPTIMISTIC UPPER BOUND."),
        "runs": {},
    }

    for label, col in (("primary_buy_pct", "buy_pct"), ("secondary_n_events", "n_events")):
        for h in _HORIZONS:
            key = f"{label}__h{h}"
            r = run(ev, wide, col, h)
            event_rets = _per_month_rets(r, "event_ret")
            mag_rets = _per_month_rets(r, "mag_ret")
            base_cum = r["base_cum_ret"]
            r["net_of_cost"] = {
                f"{int(bps)}bps": net_of_cost_block(r, event_rets, mag_rets, base_cum, bps)
                for bps in _COST_BPS_GRID
            }
            result["runs"][key] = r
            base_block = r["net_of_cost"][f"{int(_COST_BPS_BASE)}bps"]
            logger.info(
                "%s meanIC=%s t=%s | GROSS eventCum=%s baseCum=%s excess=%s | "
                "NET@%gbp eventCum=%s netExcess=%s",
                key, r["mean_ic"], r["ic_t_stat"], r["event_cum_ret"],
                r["base_cum_ret"], r["event_excess_cum"], _COST_BPS_BASE,
                base_block["event_net_cum"], base_block["event_net_excess_vs_baseline"])

    with open(_OUT, "w") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    logger.info("wrote %s", _OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
