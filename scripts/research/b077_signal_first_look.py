#!/usr/bin/env python
"""B077 F002 — first-look IC / grouped forward-return for the 龙虎榜机构席位 signal.

NOT product code, NOT a backtest, NOT a verdict. A *first-look* that answers one
narrow question on the B070 survivorship-free universe (spec §0 / §2 F002): **is
there any correlation soufflé between the institutional-seat net-buy signal and
forward returns?** A soufflé → F003/next batch builds + de-biased-backtests a
follow strategy; no soufflé → honest 劝退. **No tradeable edge is claimed.**

Inputs (all read-only research artifacts):
  * ``data/research/b077/lhb_inst_events.csv`` — F002 fetch (机构买入净额 per LHB event).
  * B070 ``prices_daily.csv``                  — survivorship-FREE prices (incl delisted)
                                                 → forward returns carry no survivor bias.
  * B070 ``cn_pit_universe.csv`` (optional)    — the de-biased liquid membership.

Method (deliberately simple — a soufflé check, not a backtest):
  * Signal per LHB event = ``机构买入净额`` (institutional seat net buy) and the
    scale-normalised ``机构净买额占总成交额比`` (净额占比).
  * Forward return = adj-close return over N TRADING days, entered the **first
    trading day AFTER** the event (LHB is disclosed post-close → entering on the
    event-day close would be lookahead). Horizons N ∈ {1, 5, 10, 20}.
  * rank-IC = Spearman(signal, fwd-ret) pooled across events; grouped spread =
    mean fwd-ret of the top-quantile minus the bottom-quantile of the signal.

★ Honesty (焊死): (1) first-look ≠ tradeable edge — IC/spread are soufflé only, F003+;
(2) selection bias — LHB events are conditioned on 异动 (a move already happened), so
this measures a CONDITIONAL signal, not "institutions quietly accumulating"; (3) coverage
gap — small-cap LHB events (where institutions are most active) fall outside the B070
liquid universe, so forward returns cover the LARGER-name subset (B070's known small-cap
ceiling = residual bias, reported); (4) no lookahead — entry is t+1.

research-only / no broker / no real money / no production change. Pure stdlib + numpy;
deterministic; the parse/IC/grouping core is unit-tested offline.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

HORIZONS: tuple[int, ...] = (1, 5, 10, 20)
N_GROUPS = 5  # quintiles for the grouped forward-return spread
_MIN_PAIRS = 200  # below this an IC is too thin to read even as a soufflé


@dataclass(frozen=True)
class LhbEvent:
    event_date: date
    ticker: str
    inst_net_buy: float
    inst_net_buy_pct: float | None


# --------------------------------------------------------------------------- #
# Loading.
# --------------------------------------------------------------------------- #
def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_float(value: str) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if result != result else result


def load_events(path: Path) -> list[LhbEvent]:
    """LHB institutional-seat events (skip rows lacking a date / ticker / net-buy)."""
    out: list[LhbEvent] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            event_date = _parse_date(row.get("event_date", ""))
            ticker = (row.get("ticker") or "").strip()
            net_buy = _parse_float(row.get("inst_net_buy", ""))
            if event_date is None or not ticker or net_buy is None:
                continue
            out.append(
                LhbEvent(event_date, ticker, net_buy, _parse_float(row.get("inst_net_buy_pct", "")))
            )
    return out


def load_price_series(path: Path) -> dict[str, tuple[list[date], list[float]]]:
    """``{ticker: (sorted_dates, adj_closes)}`` from the B070 survivorship-free prices.

    Skips suspended/blank adj-close bars. The de-biased prices include delisted names,
    so a name that later delisted still contributes its real (often negative) forward
    return — no survivorship bias on the return side."""
    rows_by_ticker: dict[str, list[tuple[date, float]]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            bar_date = _parse_date(row.get("date", ""))
            ticker = (row.get("ticker") or "").strip()
            adj = _parse_float(row.get("adj_close", ""))
            if bar_date is None or not ticker or adj is None or adj <= 0:
                continue
            rows_by_ticker.setdefault(ticker, []).append((bar_date, adj))
    series: dict[str, tuple[list[date], list[float]]] = {}
    for ticker, rows in rows_by_ticker.items():
        rows.sort(key=lambda item: item[0])
        series[ticker] = ([d for d, _ in rows], [c for _, c in rows])
    return series


def load_universe_tickers(path: Path) -> set[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {(row.get("ticker") or "").strip() for row in csv.DictReader(handle)}


# --------------------------------------------------------------------------- #
# Forward returns (pure).
# --------------------------------------------------------------------------- #
def forward_returns(
    series: tuple[list[date], list[float]],
    event_date: date,
    horizons: tuple[int, ...] = HORIZONS,
) -> dict[int, float | None]:
    """``{N: adj_close[t1+N]/adj_close[t1] - 1}`` where ``t1`` is the first trading
    day STRICTLY AFTER ``event_date`` (no lookahead). ``None`` per N when the series
    runs out (a name that delisted within the horizon yields ``None`` for the longer
    N, which is correct — the position could not be held)."""
    dates, closes = series
    entry = bisect.bisect_right(dates, event_date)  # first index with date > event_date
    out: dict[int, float | None] = {}
    for n in horizons:
        exit_idx = entry + n
        if entry < len(closes) and exit_idx < len(closes) and closes[entry] > 0:
            out[n] = closes[exit_idx] / closes[entry] - 1.0
        else:
            out[n] = None
    return out


# --------------------------------------------------------------------------- #
# IC + grouped spread (pure, numpy).
# --------------------------------------------------------------------------- #
def _average_ranks(values: np.ndarray) -> np.ndarray:
    """Average (tie-aware) ranks — the basis of Spearman."""
    order = values.argsort(kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(1, len(values) + 1, dtype=float)
    # average ties
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
    """Spearman rank-IC = Pearson correlation of the average-ranks. ``None`` when
    there is no variance (a degenerate cross-section) or fewer than 2 pairs."""
    if len(signals) != len(returns) or len(signals) < 2:
        return None
    s = _average_ranks(np.asarray(signals, dtype=float))
    r = _average_ranks(np.asarray(returns, dtype=float))
    if s.std() == 0 or r.std() == 0:
        return None
    return float(np.corrcoef(s, r)[0, 1])


def grouped_spread(
    signals: list[float], returns: list[float], n_groups: int = N_GROUPS
) -> dict[str, Any]:
    """Quantile-bucket by signal; mean forward return per bucket + top−bottom spread."""
    if len(signals) < n_groups * 2:
        return {"n_groups": n_groups, "groups": [], "top_minus_bottom": None}
    sig = np.asarray(signals, dtype=float)
    ret = np.asarray(returns, dtype=float)
    order = sig.argsort(kind="mergesort")
    buckets = np.array_split(order, n_groups)
    group_means = [float(ret[idx].mean()) for idx in buckets]
    return {
        "n_groups": n_groups,
        "group_mean_returns": [round(m, 5) for m in group_means],
        "group_mean_signal": [round(float(sig[idx].mean()), 2) for idx in buckets],
        "top_minus_bottom": round(group_means[-1] - group_means[0], 5),
    }


# --------------------------------------------------------------------------- #
# Orchestration.
# --------------------------------------------------------------------------- #
def build_pairs(
    events: list[LhbEvent],
    prices: dict[str, tuple[list[date], list[float]]],
    *,
    universe: set[str] | None,
    horizons: tuple[int, ...] = HORIZONS,
) -> dict[str, Any]:
    """Join events to de-biased forward returns; pool (signal, fwd-ret) per horizon.

    Returns the pooled vectors + coverage bookkeeping. ``universe`` (when given)
    restricts to the de-biased liquid membership; events on tickers absent from the
    prices are dropped and counted (the small-cap coverage gap)."""
    net_buy: dict[int, list[float]] = {n: [] for n in horizons}
    pct: dict[int, list[float]] = {n: [] for n in horizons}
    fwd: dict[int, list[float]] = {n: [] for n in horizons}
    pct_fwd: dict[int, list[float]] = {n: [] for n in horizons}
    covered = 0
    no_price = 0
    out_of_universe = 0
    for event in events:
        if universe is not None and event.ticker not in universe:
            out_of_universe += 1
            continue
        series = prices.get(event.ticker)
        if series is None:
            no_price += 1
            continue
        rets = forward_returns(series, event.event_date, horizons)
        if all(r is None for r in rets.values()):
            no_price += 1
            continue
        covered += 1
        for n in horizons:
            r = rets[n]
            if r is None:
                continue
            net_buy[n].append(event.inst_net_buy)
            fwd[n].append(r)
            if event.inst_net_buy_pct is not None:
                pct[n].append(event.inst_net_buy_pct)
                pct_fwd[n].append(r)
    return {
        "net_buy": net_buy,
        "net_buy_fwd": fwd,
        "pct": pct,
        "pct_fwd": pct_fwd,
        "coverage": {
            "events_total": len(events),
            "events_covered": covered,
            "events_no_price": no_price,
            "events_out_of_universe": out_of_universe,
            "coverage_rate": round(covered / len(events), 4) if events else 0.0,
        },
    }


def analyse(pairs: dict[str, Any], horizons: tuple[int, ...] = HORIZONS) -> dict[str, Any]:
    """rank-IC + grouped spread per signal × horizon (with thin-sample guards)."""
    results: dict[str, Any] = {}
    for label, sig_key, ret_key in (
        ("inst_net_buy", "net_buy", "net_buy_fwd"),
        ("inst_net_buy_pct", "pct", "pct_fwd"),
    ):
        per_h: dict[str, Any] = {}
        for n in horizons:
            signals = pairs[sig_key][n]
            returns = pairs[ret_key][n]
            n_pairs = len(signals)
            ic = rank_ic(signals, returns) if n_pairs >= _MIN_PAIRS else None
            per_h[f"N{n}"] = {
                "n_pairs": n_pairs,
                "rank_ic": round(ic, 4) if ic is not None else None,
                "grouped": grouped_spread(signals, returns) if n_pairs >= _MIN_PAIRS else None,
                "thin": n_pairs < _MIN_PAIRS,
            }
        results[label] = per_h
    return results


_STRONG_IC = 0.03  # |rank-IC| worth a de-biased full backtest (F003+)
_FAINT_IC = 0.015  # |rank-IC| of a faint-but-real direction (sub-threshold)
_COVERAGE_FLOOR = 0.5  # below this the covered subset is too partial to conclude


def _directional_cells(per_h: dict[str, Any], floor: float) -> list[float]:
    """ICs in a signal's horizons clearing ``floor`` with a same-sign grouped spread."""
    out: list[float] = []
    for cell in per_h.values():
        ic = cell.get("rank_ic")
        grouped = cell.get("grouped") or {}
        tmb = grouped.get("top_minus_bottom")
        if ic is not None and abs(ic) >= floor and tmb is not None and (ic > 0) == (tmb > 0):
            out.append(ic)
    return out


def judge(analysis: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    """First-look verdict (NEVER a tradeable-edge claim — that is F003+). Three tiers:

      * ``SOUFFLE_WORTH_BACKTEST`` — ≥2 signal×horizon cells clear |IC|≥0.03 with a
        same-sign grouped spread → a soufflé worth a de-biased backtest.
      * ``INCONCLUSIVE_COVERAGE_LIMITED`` — no soufflé, but a signal shows a faint
        CONSISTENT direction (≥3 same-sign horizons, |IC|≥0.015) AND coverage is
        partial (<50%, the small-cap majority uncovered) → the deciding test is
        fuller small-cap coverage, not a clean conclusion. Neither GO nor 劝退.
      * ``NO_SOUFFLE`` — otherwise: honest 劝退."""
    strong = [ic for per_h in analysis.values() for ic in _directional_cells(per_h, _STRONG_IC)]
    best_faint_run = 0
    faint_sign = 0
    for per_h in analysis.values():
        faint = _directional_cells(per_h, _FAINT_IC)
        same_sign = [ic for ic in faint if ic > 0] or [ic for ic in faint if ic < 0]
        if len(same_sign) > best_faint_run:
            best_faint_run = len(same_sign)
            faint_sign = 1 if same_sign and same_sign[0] > 0 else -1
    coverage_rate = coverage.get("coverage_rate") or 0.0
    all_ics = strong or [
        ic for per_h in analysis.values() for ic in _directional_cells(per_h, _FAINT_IC)
    ]
    max_abs_ic = round(max((abs(i) for i in all_ics), default=0.0), 4)

    if len(strong) >= 2:
        verdict = "SOUFFLE_WORTH_BACKTEST"
        reason = (
            f"{len(strong)} signal×horizon cell(s) clear |rank-IC|≥{_STRONG_IC} with a "
            "same-sign grouped spread — a first-look soufflé worth a de-biased backtest "
            "(F003+). NOT a tradeable edge; selection bias + small-cap coverage gap apply."
        )
    elif best_faint_run >= 3 and coverage_rate < _COVERAGE_FLOOR:
        verdict = "INCONCLUSIVE_COVERAGE_LIMITED"
        reason = (
            f"A {'positive' if faint_sign > 0 else 'negative'} but FAINT, consistent "
            f"direction ({best_faint_run} horizons, |IC|≥{_FAINT_IC}, max {max_abs_ic}) "
            f"sits below the {_STRONG_IC} soufflé bar, AND only "
            f"{round(coverage_rate * 100, 1)}% of institutional LHB events are covered "
            "(the small-cap majority — where institutions are most active — is outside "
            "the B070 liquid universe). Deciding test = fetch small-cap prices and re-run; "
            "neither a clean soufflé (no GO) nor a clean zero (no outright 劝退)."
        )
    else:
        verdict = "NO_SOUFFLE"
        reason = (
            f"No signal×horizon clears |rank-IC|≥{_STRONG_IC} with a consistent grouped "
            "spread, and no faint consistent direction survives — first-look shows no "
            "correlation soufflé; honest 劝退 unless a richer construction changes it."
        )
    return {
        "verdict": verdict,
        "strong_cells": len(strong),
        "faint_consistent_horizons": best_faint_run,
        "max_abs_ic": max_abs_ic,
        "coverage_rate": coverage.get("coverage_rate"),
        "reason": reason,
    }


def run(
    *,
    events_csv: Path,
    prices_csv: Path,
    universe_csv: Path | None,
    horizons: tuple[int, ...] = HORIZONS,
) -> dict[str, Any]:
    events = load_events(events_csv)
    prices = load_price_series(prices_csv)
    universe = load_universe_tickers(universe_csv) if universe_csv else None
    pairs = build_pairs(events, prices, universe=universe, horizons=horizons)
    analysis = analyse(pairs, horizons)
    verdict = judge(analysis, pairs["coverage"])
    return {
        "probe": "b077_signal_first_look",
        "signal_source": "dragon_tiger_inst (stock_lhb_jgmmtj_em 机构买入净额)",
        "universe": "B070 survivorship-free PIT"
        + ("" if universe else " (prices-only, no membership filter)"),
        "horizons": list(horizons),
        "coverage": pairs["coverage"],
        "analysis": analysis,
        "verdict": verdict,
        "honesty": (
            "first-look ≠ tradeable edge (F003+); selection bias (异动-conditioned); "
            "small-cap LHB events under-covered by B070 liquid universe (residual bias "
            "toward larger names); entry t+1 (no lookahead); research-only/no-broker."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="B077 F002 first-look IC for LHB inst seats")
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--universe", type=Path, default=None, help="optional membership filter")
    parser.add_argument("--out", type=Path, default=None)
    cli = parser.parse_args(argv)

    result = run(events_csv=cli.events, prices_csv=cli.prices, universe_csv=cli.universe)
    text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    print(text)
    if cli.out:
        cli.out.parent.mkdir(parents=True, exist_ok=True)
        cli.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
