#!/usr/bin/env python
"""B094 — 游资 (hot-money) seat follow-signal FIRST-LOOK: forward-return rank-IC +
a simple long-only follow backtest vs baseline.

NOT product code, NOT a tradeable-edge claim, NOT the user's PRIMARY institutional
goal (that needs the paid Tushare ¥200). This is the FREE 游资/打板 second sleeve — a
KNOWN crowded / loss-prone game — so a NO-GO / INCONCLUSIVE is the expected honest
answer. No GO is manufactured.

Signal (★no look-ahead): for each LHB date T where a 游资 seat is a net BUYER, the
follow signal is known at CLOSE of T. We enter at T+1 (first trading day strictly
after T) and measure the forward return over T+1..T+1+N. Signal at T uses only <=T
data; the forward return is strictly >T. Two signals:
  * ``youzi_flag``    — binary 1 if the event is a 游资 BUY (解读 tag "实力游资买入"),
                        else 0. The cheap, full-coverage flag.
  * ``youzi_net``     — seat-level 游资 net buy (¥, from the seats sample) when present.

Analysis (deliberately simple — a first-look, not a strategy):
  * rank-IC = Spearman(signal, fwd-ret) pooled per horizon N ∈ {1,5,10}, sampled at
    MONTHLY frequency (one cohort per calendar month) to avoid overlap inflation, with
    a t-stat over the per-month cross-sectional ICs (Newey-West-free, simple mean/se).
  * follow backtest = each month, equal-weight the 游资-bought names, hold N days;
    compare mean forward return vs a BASELINE = equal-weight ALL LHB names that month
    (the "just buy the LHB" null). Edge = follow − baseline.

research-only / no broker / no real money / no production. Pure stdlib + numpy;
deterministic; the parse/IC/no-lookahead core is unit-tested offline.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import logging
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

HORIZONS: tuple[int, ...] = (1, 5, 10)
_MIN_PAIRS = 100
_STRONG_IC = 0.03      # |rank-IC| worth a de-biased full backtest
_FAINT_IC = 0.015      # faint-but-real direction
_MIN_MONTHS = 6        # need ≥ this many monthly cohorts for a t-stat


@dataclass(frozen=True)
class Event:
    event_date: date
    ticker: str
    lhb_net_buy: float | None
    youzi_flag: int
    youzi_net: float | None  # seat-level, from sample; None when not sampled


# --------------------------------------------------------------------------- #
# Loading.
# --------------------------------------------------------------------------- #
def _pdate(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _pfloat(value: object) -> float | None:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if result != result else result


def _is_youzi_jiedu(jiedu: str) -> bool:
    return "游资" in jiedu and "买" in jiedu and "卖" not in jiedu


def load_events(events_csv: Path, seats_csv: Path | None) -> list[Event]:
    """Join events.csv with the seat-level 游资 net buy from seats_sample.csv (if any)."""
    seat_net: dict[tuple[str, str], float] = {}
    if seats_csv and seats_csv.exists():
        with seats_csv.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                key = (str(row.get("event_date", "")), str(row.get("ticker", "")))
                net = _pfloat(row.get("youzi_buy_net"))
                if net is not None:
                    seat_net[key] = net
    out: list[Event] = []
    with events_csv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            event_date = _pdate(row.get("event_date", ""))
            ticker = str(row.get("ticker", "")).strip()
            if event_date is None or not ticker:
                continue
            jiedu = str(row.get("jiedu", ""))
            key = (event_date.isoformat(), ticker)
            out.append(Event(
                event_date=event_date,
                ticker=ticker,
                lhb_net_buy=_pfloat(row.get("lhb_net_buy")),
                youzi_flag=int(_is_youzi_jiedu(jiedu)),
                youzi_net=seat_net.get(key),
            ))
    return out


def load_prices(path: Path) -> dict[str, tuple[list[date], list[float]]]:
    """{ticker: (sorted_dates, adj_closes)} from the long-form prices.csv."""
    rows: dict[str, list[tuple[date, float]]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            bar_date = _pdate(row.get("date", ""))
            ticker = str(row.get("ticker", "")).strip()
            adj = _pfloat(row.get("adj_close"))
            if bar_date is None or not ticker or adj is None or adj <= 0:
                continue
            rows.setdefault(ticker, []).append((bar_date, adj))
    series: dict[str, tuple[list[date], list[float]]] = {}
    for ticker, pairs in rows.items():
        pairs.sort(key=lambda item: item[0])
        series[ticker] = ([d for d, _ in pairs], [c for _, c in pairs])
    return series


# --------------------------------------------------------------------------- #
# Forward returns (★no look-ahead) + IC (pure).
# --------------------------------------------------------------------------- #
def forward_returns(
    series: tuple[list[date], list[float]],
    event_date: date,
    horizons: tuple[int, ...] = HORIZONS,
) -> dict[int, float | None]:
    """{N: close[entry+N]/close[entry] - 1} where entry = first trading day STRICTLY
    AFTER event_date (bisect_right). No lookahead: entry index has date > event_date."""
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


def _avg_ranks(values: np.ndarray) -> np.ndarray:
    order = values.argsort(kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(1, len(values) + 1, dtype=float)
    sorted_vals = values[order]
    i, n = 0, len(values)
    while i < n:
        j = i
        while j + 1 < n and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    return ranks


def rank_ic(signals: list[float], returns: list[float]) -> float | None:
    """Spearman rank-IC = Pearson of average-ranks. None on degenerate cross-section."""
    if len(signals) != len(returns) or len(signals) < 2:
        return None
    s = _avg_ranks(np.asarray(signals, dtype=float))
    r = _avg_ranks(np.asarray(returns, dtype=float))
    if s.std() == 0 or r.std() == 0:
        return None
    return float(np.corrcoef(s, r)[0, 1])


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


# --------------------------------------------------------------------------- #
# Pairing + monthly IC + backtest.
# --------------------------------------------------------------------------- #
def build_cohorts(
    events: list[Event],
    prices: dict[str, tuple[list[date], list[float]]],
    horizons: tuple[int, ...] = HORIZONS,
) -> dict[str, Any]:
    """Join events -> forward returns; group into monthly cohorts. Each covered event
    contributes (youzi_flag, youzi_net, lhb_net_buy, fwd[N]). Also tracks coverage."""
    cohorts: dict[str, list[dict[str, Any]]] = {}
    covered = no_price = 0
    for ev in events:
        series = prices.get(ev.ticker)
        if series is None:
            no_price += 1
            continue
        rets = forward_returns(series, ev.event_date, horizons)
        if all(r is None for r in rets.values()):
            no_price += 1
            continue
        covered += 1
        cohorts.setdefault(_month_key(ev.event_date), []).append({
            "youzi_flag": ev.youzi_flag,
            "youzi_net": ev.youzi_net,
            "lhb_net_buy": ev.lhb_net_buy,
            "fwd": rets,
        })
    return {
        "cohorts": cohorts,
        "coverage": {
            "events_total": len(events),
            "events_covered": covered,
            "events_no_price": no_price,
            "coverage_rate": round(covered / len(events), 4) if events else 0.0,
            "n_months": len(cohorts),
        },
    }


def _tstat(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    arr = np.asarray(values, dtype=float)
    sd = arr.std(ddof=1)
    if sd == 0:
        return None
    return float(arr.mean() / (sd / math.sqrt(len(arr))))


def monthly_ic(cohorts: dict[str, list[dict[str, Any]]], signal_key: str,
               horizons: tuple[int, ...] = HORIZONS) -> dict[str, Any]:
    """Per-month cross-sectional rank-IC, then mean IC + t-stat across months.

    signal_key ∈ {'youzi_flag','youzi_net','lhb_net_buy'}. Events lacking the signal
    (e.g. youzi_net not sampled) are dropped for that signal only."""
    per_h: dict[str, Any] = {}
    for n in horizons:
        month_ics: list[float] = []
        pooled = 0
        for _, rows in sorted(cohorts.items()):
            sig, ret = [], []
            for row in rows:
                s = row.get(signal_key)
                r = row["fwd"][n]
                if s is None or r is None:
                    continue
                sig.append(float(s))
                ret.append(float(r))
            if len(sig) >= 5:
                ic = rank_ic(sig, ret)
                if ic is not None:
                    month_ics.append(ic)
                pooled += len(sig)
        mean_ic = round(float(np.mean(month_ics)), 4) if month_ics else None
        t = _tstat(month_ics)
        per_h[f"N{n}"] = {
            "mean_monthly_ic": mean_ic,
            "t_stat": round(t, 2) if t is not None else None,
            "n_months": len(month_ics),
            "n_pairs_pooled": pooled,
            "thin": len(month_ics) < _MIN_MONTHS or pooled < _MIN_PAIRS,
        }
    return per_h


def follow_backtest(cohorts: dict[str, list[dict[str, Any]]],
                    horizons: tuple[int, ...] = HORIZONS) -> dict[str, Any]:
    """Long-only 游资-follow vs baseline (all-LHB), monthly-cohort equal-weight.

    Each month: FOLLOW = mean fwd-ret of the youzi_flag==1 names; BASELINE = mean
    fwd-ret of ALL names that month. Report the mean over months + edge (follow−base)
    + a paired t-stat of the per-month (follow−base) differences."""
    out: dict[str, Any] = {}
    for n in horizons:
        follow_m, base_m, diff_m = [], [], []
        for _, rows in sorted(cohorts.items()):
            f_rets = [row["fwd"][n] for row in rows
                      if row["youzi_flag"] == 1 and row["fwd"][n] is not None]
            all_rets = [row["fwd"][n] for row in rows if row["fwd"][n] is not None]
            if not all_rets or not f_rets:
                continue
            f_mean = float(np.mean(f_rets))
            b_mean = float(np.mean(all_rets))
            follow_m.append(f_mean)
            base_m.append(b_mean)
            diff_m.append(f_mean - b_mean)
        if not diff_m:
            out[f"N{n}"] = {"n_months": 0, "thin": True}
            continue
        t = _tstat(diff_m)
        out[f"N{n}"] = {
            "n_months": len(diff_m),
            "follow_mean_ret": round(float(np.mean(follow_m)), 5),
            "baseline_mean_ret": round(float(np.mean(base_m)), 5),
            "edge_follow_minus_baseline": round(float(np.mean(diff_m)), 5),
            "edge_t_stat": round(t, 2) if t is not None else None,
            "months_follow_beats_base": int(sum(1 for d in diff_m if d > 0)),
            "thin": len(diff_m) < _MIN_MONTHS,
        }
    return out


# --------------------------------------------------------------------------- #
# Verdict.
# --------------------------------------------------------------------------- #
def judge(ic_flag: dict[str, Any], backtest: dict[str, Any],
          coverage: dict[str, Any]) -> dict[str, Any]:
    """First-look verdict for the 游资 follow signal (NEVER a tradeable-edge claim).

    A FOLLOW signal is only worth pursuing if it predicts HIGHER forward returns —
    i.e. a POSITIVE rank-IC and a POSITIVE follow-minus-baseline edge. A significant
    NEGATIVE result means following 游资 is actively HARMFUL, which is a NO-GO for the
    follow strategy (the honest, expected 劝退 for the crowded 打板 game), NOT an
    "inconclusive, needs more coverage" case.

      * GO — ≥2 horizons show a POSITIVE mean-IC≥0.03 with |t|≥2 AND a significant
        positive follow edge (|t|≥2) — a robust follow edge, surprising for a crowded
        game; warrants a de-biased full backtest. NOT yet a tradeable claim.
      * NO-GO — no positive edge: the best follow edge is ≤0 (and/or the significant
        IC/edge cells point NEGATIVE) → following 游资 has no edge, likely hurts.
      * INCONCLUSIVE — only a POSITIVE faint direction (positive IC≥0.015 / positive
        edge) that is sub-threshold or insignificant, so neither a clean GO nor a clean
        negative — the deciding test is fuller coverage.
    """
    strong_pos = []
    faint_pos = []
    sig_neg = []
    for cell in ic_flag.values():
        ic = cell.get("mean_monthly_ic")
        t = cell.get("t_stat")
        if ic is None or cell.get("thin"):
            continue
        if abs(ic) >= _STRONG_IC and t is not None and abs(t) >= 2.0:
            (strong_pos if ic > 0 else sig_neg).append(ic)
        elif ic >= _FAINT_IC:
            faint_pos.append(ic)
    edges = [c for c in backtest.values() if not c.get("thin")]
    pos_sig_edge = [c for c in edges
                    if c.get("edge_follow_minus_baseline", 0) > 0
                    and c.get("edge_t_stat") is not None and abs(c["edge_t_stat"]) >= 2.0]
    neg_sig_edge = [c for c in edges
                    if c.get("edge_follow_minus_baseline", 0) < 0
                    and c.get("edge_t_stat") is not None and abs(c["edge_t_stat"]) >= 2.0]
    best_edge = max((c.get("edge_follow_minus_baseline", 0) for c in edges), default=0.0)
    best_ic = max((abs(c.get("mean_monthly_ic") or 0) for c in ic_flag.values()), default=0.0)

    if len(strong_pos) >= 2 and pos_sig_edge:
        verdict = "GO"
        reason = (
            f"{len(strong_pos)} horizons show POSITIVE IC≥{_STRONG_IC} with |t|≥2 AND a "
            "significant positive follow edge — a robust follow edge, surprising for a "
            "crowded game; warrants a de-biased full backtest. NOT yet a tradeable claim."
        )
    elif best_edge <= 0 or sig_neg or neg_sig_edge:
        verdict = "NO-GO"
        harm = ""
        if sig_neg or neg_sig_edge:
            harm = (
                f" In fact {len(sig_neg)} IC horizon(s) and {len(neg_sig_edge)} follow-edge "
                "horizon(s) are SIGNIFICANTLY NEGATIVE (|t|≥2) — following 游资 buys actively "
                "UNDERPERFORMED just buying all LHB names."
            )
        reason = (
            f"No horizon shows a POSITIVE IC≥{_STRONG_IC} with |t|≥2, and the best 游资-follow "
            f"edge over the all-LHB baseline is {round(best_edge, 5)} (≤0).{harm} The honest "
            "劝退 for the crowded, loss-prone 打板 game — the expected outcome for this FREE "
            "secondary sleeve. The PRIMARY institutional-following goal needs the paid Tushare "
            "¥200 full-coverage LHB seats, not this."
        )
    else:
        verdict = "INCONCLUSIVE"
        reason = (
            f"A POSITIVE but faint direction (best IC={round(best_ic, 4)}, best edge="
            f"{round(best_edge, 5)}) sits below the {_STRONG_IC}/significance bar — neither a "
            "clean GO nor a clean negative. Deciding test = fuller price coverage. The 打板 "
            "game is crowded; the PRIMARY institutional goal needs the paid Tushare ¥200 seats."
        )
    return {
        "verdict": verdict,
        "strong_positive_ic_horizons": len(strong_pos),
        "significant_negative_ic_horizons": len(sig_neg),
        "faint_positive_ic_horizons": len(faint_pos),
        "best_abs_ic": round(best_ic, 4),
        "best_follow_edge": round(best_edge, 5),
        "significant_positive_edge_horizons": len(pos_sig_edge),
        "significant_negative_edge_horizons": len(neg_sig_edge),
        "reason": reason,
    }


def run(*, events_csv: Path, prices_csv: Path, seats_csv: Path | None,
        horizons: tuple[int, ...] = HORIZONS) -> dict[str, Any]:
    events = load_events(events_csv, seats_csv)
    prices = load_prices(prices_csv)
    built = build_cohorts(events, prices, horizons)
    cohorts = built["cohorts"]
    ic_flag = monthly_ic(cohorts, "youzi_flag", horizons)
    ic_net = monthly_ic(cohorts, "youzi_net", horizons)
    ic_lhb = monthly_ic(cohorts, "lhb_net_buy", horizons)
    backtest = follow_backtest(cohorts, horizons)
    verdict = judge(ic_flag, backtest, built["coverage"])
    n_youzi = sum(1 for e in events if e.youzi_flag == 1)
    n_seat_net = sum(1 for e in events if e.youzi_net is not None)
    return {
        "probe": "b094_youzi_ic",
        "signal": "游资 follow (解读 '实力游资买入' binary flag + seat-level 游资 net buy)",
        "horizons": list(horizons),
        "no_lookahead": "signal known at close T; entry t+1 (bisect_right); fwd ret strictly >T",
        "sampling": "monthly cohorts (one cross-section per calendar month; overlap-safe)",
        "coverage": built["coverage"],
        "counts": {
            "events": len(events),
            "youzi_flag_events": n_youzi,
            "youzi_flag_rate": round(n_youzi / len(events), 4) if events else 0.0,
            "seat_level_net_events": n_seat_net,
        },
        "ic_youzi_flag": ic_flag,
        "ic_youzi_seat_net": ic_net,
        "ic_lhb_net_buy_baseline_signal": ic_lhb,
        "follow_backtest_vs_baseline": backtest,
        "verdict": verdict,
        "honesty": (
            "FREE 游资/打板 second sleeve — a crowded, loss-prone game; NO-GO/INCONCLUSIVE "
            "is the expected valid answer. NOT the user's PRIMARY institutional goal (needs "
            "paid Tushare ¥200 full-coverage LHB seats). Selection bias: LHB events are "
            "异动-conditioned. Entry t+1 (no lookahead). research-only / no broker."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="B094 游资 follow-signal first-look IC")
    parser.add_argument("--events", type=Path,
                        default=Path("data/research/b094_youzi/events.csv"))
    parser.add_argument("--prices", type=Path,
                        default=Path("data/research/b094_youzi/prices.csv"))
    parser.add_argument("--seats", type=Path,
                        default=Path("data/research/b094_youzi/seats_sample.csv"))
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
