#!/usr/bin/env python
"""B103 — LHB INSTITUTIONAL-buying follow-signal FIRST-LOOK on the FULL free akshare
LHB (52k events, all stocks 2022-2024): forward-return rank-IC + a long-only follow
backtest vs an all-LHB baseline.

This is the user's PRIMARY signal — daily LHB 机构专用席位 net buying = 跟踪机构建仓.
B077 probed it only on the b070 large-cap universe (19% coverage -> INCONCLUSIVE).
B094 fetched the FULL LHB but tested only 游资 (retail, NO-GO). The institutional
signal on the full free LHB was NEVER tested. This closes that gap — the decisive FREE
test of the primary signal on broader data than B077.

Memory prior (state ONCE, do NOT tune): LHB institutional seats are NOISY / can be
masked via proxy accounts (马甲). A NO-GO / INCONCLUSIVE is plausible and honest. No GO
is manufactured. If free NO-GO, the paid Tushare ¥200 (full history 2005+, delisted,
cleaner seats) remains the clean test.

Signal (★no look-ahead): the akshare 解读 (jiedu) column tags each LHB event with
"N家机构买入" or "N家机构卖出" (N institutions net-bought / net-sold that day). The LHB
list for day T is disclosed AFTER close of T, so the tag is known at close of T. We
enter T+1 (first trading day STRICTLY after T, bisect_right) and measure forward return
over T+1..T+1+N. Signal at T uses only <=T data; forward return strictly >T. Signals:
  * ``inst_buy_flag``  — binary 1 iff "N家机构买入" (>=1 inst bought), else 0 (covers
                         both 卖出 and non-institutional events). Full-coverage flag.
  * ``inst_count``     — signed institution count: +N for N家机构买入, -N for N家机构卖出,
                         0 for non-institutional. Graded magnitude signal.
  * ``inst_buy_net``   — per-event institutional net buy ¥ (from the 800-event seats
                         sample) — the thinner-but-exact secondary signal; cross-checked
                         against the jiedu flag.

Analysis (deliberately simple — a first-look, not a strategy):
  * rank-IC = Spearman(signal, fwd-ret) per horizon N in {1,5,10}, sampled at MONTHLY
    frequency (one cross-section per calendar month) to avoid overlap inflation, with a
    t-stat over the per-month cross-sectional ICs.
  * follow backtest = each month, equal-weight the institution-BOUGHT names, hold N days;
    compare vs a BASELINE = equal-weight ALL LHB names that month (the "just buy the LHB"
    null). Edge = follow - baseline, with a paired per-month t-stat.

The pure no-look-ahead machinery (bisect_right entry, forward_returns, rank_ic, tstat,
monthly_ic, price loading) is IMPORTED from the VERIFIED b094_youzi_ic.py.

research-only / no broker / no real money / no production. Deterministic; the
parse/IC/no-lookahead core is unit-tested offline.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

# Reuse the VERIFIED pure machinery from B094 (same directory).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import b094_youzi_ic as b094  # noqa: E402
from b094_youzi_ic import (  # noqa: E402
    HORIZONS,
    _month_key,
    _pdate,
    _pfloat,
    _tstat,
    load_prices,
    monthly_ic,
    rank_ic,
)

logger = logging.getLogger(__name__)

_MIN_PAIRS = b094._MIN_PAIRS
_STRONG_IC = b094._STRONG_IC
_FAINT_IC = b094._FAINT_IC
_MIN_MONTHS = b094._MIN_MONTHS

# The akshare 解读 institutional tag, e.g. "1家机构买入，成功率54.27%".
_INST_TAG = re.compile(r"(\d+)家机构(买入|卖出)")


# --------------------------------------------------------------------------- #
# Signal parsing.
# --------------------------------------------------------------------------- #
def parse_inst_jiedu(jiedu: str) -> tuple[int, int]:
    """Parse the institutional tag from an akshare 解读 string.

    Returns ``(inst_buy_flag, inst_count_signed)``:
      * "N家机构买入…"  -> (1, +N)   institutions net-bought
      * "N家机构卖出…"  -> (0, -N)   institutions net-sold (NOT a buy)
      * anything else   -> (0,  0)   no institutional seat on this LHB event

    The direction is taken from the FIRST 家机构 tag (akshare emits exactly one such tag
    per event — buy and sell never co-occur in this dataset)."""
    match = _INST_TAG.search(jiedu or "")
    if match is None:
        return 0, 0
    count = int(match.group(1))
    if match.group(2) == "买入":
        return 1, count
    return 0, -count


@dataclass(frozen=True)
class Event:
    event_date: date
    ticker: str
    lhb_net_buy: float | None
    inst_buy_flag: int
    inst_count: int              # signed: +N buy, -N sell, 0 none
    inst_buy_net: float | None   # per-event institutional net ¥, from sample; else None


def load_events(events_csv: Path, seats_csv: Path | None) -> list[Event]:
    """Load LHB events, parse the jiedu institutional tag, and join the per-event
    institutional net buy (``inst_buy_net``) from the seats sample when present."""
    seat_net: dict[tuple[str, str], float] = {}
    if seats_csv and seats_csv.exists():
        with seats_csv.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                key = (str(row.get("event_date", "")), str(row.get("ticker", "")))
                net = _pfloat(row.get("inst_buy_net"))
                if net is not None:
                    seat_net[key] = net
    out: list[Event] = []
    with events_csv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            event_date = _pdate(row.get("event_date", ""))
            ticker = str(row.get("ticker", "")).strip()
            if event_date is None or not ticker:
                continue
            flag, count = parse_inst_jiedu(str(row.get("jiedu", "")))
            key = (event_date.isoformat(), ticker)
            out.append(Event(
                event_date=event_date,
                ticker=ticker,
                lhb_net_buy=_pfloat(row.get("lhb_net_buy")),
                inst_buy_flag=flag,
                inst_count=count,
                inst_buy_net=seat_net.get(key),
            ))
    return out


# --------------------------------------------------------------------------- #
# Pairing -> monthly cohorts (★no look-ahead via imported forward_returns).
# --------------------------------------------------------------------------- #
def build_cohorts(
    events: list[Event],
    prices: dict[str, tuple[list[date], list[float]]],
    horizons: tuple[int, ...] = HORIZONS,
) -> dict[str, Any]:
    """Join events -> forward returns (entry STRICTLY after T); group into monthly
    cohorts. Each covered event contributes its inst signals + fwd[N]."""
    cohorts: dict[str, list[dict[str, Any]]] = {}
    covered = no_price = 0
    for ev in events:
        series = prices.get(ev.ticker)
        if series is None:
            no_price += 1
            continue
        rets = b094.forward_returns(series, ev.event_date, horizons)
        if all(r is None for r in rets.values()):
            no_price += 1
            continue
        covered += 1
        cohorts.setdefault(_month_key(ev.event_date), []).append({
            "inst_buy_flag": ev.inst_buy_flag,
            "inst_count": ev.inst_count,
            "inst_buy_net": ev.inst_buy_net,
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


def inst_follow_backtest(cohorts: dict[str, list[dict[str, Any]]],
                         horizons: tuple[int, ...] = HORIZONS) -> dict[str, Any]:
    """Long-only institution-follow vs baseline (all-LHB), monthly-cohort equal-weight.

    Each month: FOLLOW = mean fwd-ret of the ``inst_buy_flag==1`` names; BASELINE = mean
    fwd-ret of ALL names that month. Report the mean over months + edge (follow-base) +
    a paired t-stat of the per-month (follow-base) differences."""
    out: dict[str, Any] = {}
    for n in horizons:
        follow_m, base_m, diff_m = [], [], []
        for _, rows in sorted(cohorts.items()):
            f_rets = [row["fwd"][n] for row in rows
                      if row["inst_buy_flag"] == 1 and row["fwd"][n] is not None]
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


def inst_net_crosscheck(events: list[Event]) -> dict[str, Any]:
    """Cross-check the jiedu ``inst_buy_flag`` against the exact per-event
    ``inst_buy_net`` on the 800-event seats sample. Do the two institutional signals
    AGREE on direction? Also report the rank-IC-style sign agreement."""
    sampled = [e for e in events if e.inst_buy_net is not None]
    n = len(sampled)
    if n == 0:
        return {"n_sample": 0}
    # Confusion between jiedu-buy-flag and (inst_buy_net > 0).
    flag_and_pos = sum(1 for e in sampled if e.inst_buy_flag == 1 and e.inst_buy_net > 0)
    flag_and_nonpos = sum(1 for e in sampled if e.inst_buy_flag == 1 and e.inst_buy_net <= 0)
    noflag_and_pos = sum(1 for e in sampled if e.inst_buy_flag == 0 and e.inst_buy_net > 0)
    noflag_and_nonpos = sum(1 for e in sampled if e.inst_buy_flag == 0 and e.inst_buy_net <= 0)
    agree = flag_and_pos + noflag_and_nonpos
    # Rank correlation of the signed inst_count vs inst_buy_net (both institutional).
    counts = [float(e.inst_count) for e in sampled]
    nets = [float(e.inst_buy_net) for e in sampled if e.inst_buy_net is not None]
    ic = rank_ic(counts, nets) if len(counts) == len(nets) else None
    return {
        "n_sample": n,
        "sample_inst_net_positive": sum(1 for e in sampled if e.inst_buy_net > 0),
        "confusion": {
            "flag1_net_pos": flag_and_pos,
            "flag1_net_nonpos": flag_and_nonpos,
            "flag0_net_pos": noflag_and_pos,
            "flag0_net_nonpos": noflag_and_nonpos,
        },
        "direction_agreement_rate": round(agree / n, 4),
        "rank_ic_count_vs_net": round(ic, 4) if ic is not None else None,
        "note": (
            "jiedu 'N家机构买入' flag vs exact inst_buy_net>0 on the 800-event sample. High "
            "agreement => the free jiedu tag faithfully encodes institutional net-buy "
            "direction (parsing is sound); it does NOT by itself imply predictive edge."
        ),
    }


# --------------------------------------------------------------------------- #
# Verdict (institutional framing; NEVER a tradeable-edge claim).
# --------------------------------------------------------------------------- #
def judge(ic_flag: dict[str, Any], backtest: dict[str, Any]) -> dict[str, Any]:
    """First-look verdict for the LHB institutional-follow signal.

    A FOLLOW signal is worth pursuing only if institution-bought names earn HIGHER
    forward returns — a POSITIVE rank-IC AND a POSITIVE follow-minus-baseline edge. A
    significant NEGATIVE result means following institutional buys is actively HARMFUL
    (NO-GO). This matches the memory prior that LHB institutional seats are noisy / 马甲.

      * GO — >=2 horizons show POSITIVE mean-IC>=0.03 with |t|>=2 AND a significant
        positive follow edge (|t|>=2). Surprising given the noisy-seats prior; warrants a
        de-biased full backtest and, potentially, the paid ¥200 clean-seat confirmation.
        NOT yet a tradeable claim.
      * NO-GO — no positive edge: best follow edge <=0 and/or significant NEGATIVE IC or
        edge -> following LHB institutional buys has no edge / hurts. The honest 劝退 for
        the free/noisy seats; the paid ¥200 clean seats remain the deciding clean test.
      * INCONCLUSIVE — only a POSITIVE faint direction (IC>=0.015 / positive edge) that is
        sub-threshold or insignificant -> deciding test = the paid ¥200 full-history
        clean-seat LHB (2005+, delisted survivors).
    """
    strong_pos: list[float] = []
    faint_pos: list[float] = []
    sig_neg: list[float] = []
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
            f"{len(strong_pos)} horizons show POSITIVE IC>={_STRONG_IC} with |t|>=2 AND a "
            "significant positive follow edge — a robust institutional-follow edge on the "
            "FREE LHB, surprising given the noisy/马甲 prior; warrants a de-biased full "
            "backtest and the paid ¥200 clean-seat confirmation. NOT yet a tradeable claim."
        )
    elif best_edge <= 0 or sig_neg or neg_sig_edge:
        verdict = "NO-GO"
        harm = ""
        if sig_neg or neg_sig_edge:
            harm = (
                f" In fact {len(sig_neg)} IC horizon(s) and {len(neg_sig_edge)} follow-edge "
                "horizon(s) are SIGNIFICANTLY NEGATIVE (|t|>=2) — following LHB institutional "
                "buys actively UNDERPERFORMED just buying all LHB names."
            )
        reason = (
            f"No horizon shows a POSITIVE IC>={_STRONG_IC} with |t|>=2, and the best "
            f"institution-follow edge over the all-LHB baseline is {round(best_edge, 5)} "
            f"(<=0).{harm} This is the honest 劝退 for the FREE LHB institutional seats — "
            "consistent with the memory prior that they are noisy / maskable via 马甲. The "
            "PRIMARY institutional goal's deciding CLEAN test is the paid Tushare ¥200 "
            "full-history LHB (2005+, delisted survivors, cleaner seat identification)."
        )
    else:
        verdict = "INCONCLUSIVE"
        reason = (
            f"A POSITIVE but faint direction (best IC={round(best_ic, 4)}, best edge="
            f"{round(best_edge, 5)}) sits below the {_STRONG_IC}/significance bar — neither a "
            "clean GO nor a clean negative. Deciding test = the paid Tushare ¥200 "
            "full-history clean-seat LHB. Free data cannot settle it."
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
    ic_flag = monthly_ic(cohorts, "inst_buy_flag", horizons)
    ic_count = monthly_ic(cohorts, "inst_count", horizons)
    ic_net = monthly_ic(cohorts, "inst_buy_net", horizons)
    ic_lhb = monthly_ic(cohorts, "lhb_net_buy", horizons)
    backtest = inst_follow_backtest(cohorts, horizons)
    crosscheck = inst_net_crosscheck(events)
    verdict = judge(ic_flag, backtest)

    n_inst_buy = sum(1 for e in events if e.inst_buy_flag == 1)
    n_inst_sell = sum(1 for e in events if e.inst_count < 0)
    n_inst_any = n_inst_buy + n_inst_sell
    n_net_sampled = sum(1 for e in events if e.inst_buy_net is not None)
    return {
        "probe": "b103_lhb_inst_ic",
        "signal": ("LHB institutional follow (解读 'N家机构买入' binary flag + signed "
                   "institution count + per-event inst_buy_net sample)"),
        "horizons": list(horizons),
        "no_lookahead": ("LHB list for T disclosed AFTER close T; signal known at close T; "
                         "entry t+1 (bisect_right, strictly > T); fwd ret strictly > T"),
        "sampling": "monthly cohorts (one cross-section per calendar month; overlap-safe)",
        "coverage": built["coverage"],
        "counts": {
            "events": len(events),
            "inst_tagged_events": n_inst_any,
            "inst_tagged_rate": round(n_inst_any / len(events), 4) if events else 0.0,
            "inst_buy_events": n_inst_buy,
            "inst_sell_events": n_inst_sell,
            "inst_buy_rate": round(n_inst_buy / len(events), 4) if events else 0.0,
            "inst_net_sampled_events": n_net_sampled,
        },
        "ic_inst_buy_flag": ic_flag,
        "ic_inst_count_signed": ic_count,
        "ic_inst_buy_net_sample": ic_net,
        "ic_lhb_net_buy_baseline_signal": ic_lhb,
        "follow_backtest_vs_baseline": backtest,
        "inst_net_crosscheck": crosscheck,
        "verdict": verdict,
        "honesty": (
            "PRIMARY signal, FREE LHB (akshare), 2022-2024, all stocks. Memory prior: LHB "
            "institutional seats are noisy / maskable via 马甲 — NO-GO/INCONCLUSIVE is a "
            "plausible honest answer; no GO is manufactured. Selection bias: LHB events are "
            "异动-conditioned (already-moved names). Survivorship: akshare free feed omits "
            "delisted names. Entry t+1 (no lookahead). The deciding CLEAN test is the paid "
            "Tushare ¥200 full-history LHB. research-only / no broker."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="B103 LHB institutional follow-signal first-look IC")
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
