#!/usr/bin/env python
"""B105 F002 — Evaluator INDEPENDENT recomputation (does NOT import any b105 function).

Reuses ONLY the prior-batch-verified DATA machinery (b103.load_events / build_cohorts,
b094.load_prices / forward_returns — all Codex-verified in B094/B103/B104) to obtain the
SAME universe. Every portfolio number (weights, GROSS, NET, Sharpe, cohort-IC,
corr(IC,ret), AND the long-leg/short-leg decomposition + long-only-vs-index variant) is
re-derived here from scratch with independent code. Purpose: confirm the committed
result.json numbers and quantify how much the paper dollar-neutral L/S depends on the
(A-share-infeasible) short leg.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]


def avg_rank(a):
    """Independent average-rank (ties -> mean rank) via np.unique inverse+counts.

    Different algorithm than b094._avg_ranks (which uses a scan loop); implemented here
    from scratch so the recomputation does not lean on the code under review."""
    a = np.asarray(a, dtype=float)
    order = np.argsort(a, kind="mergesort")
    plain = np.empty(len(a), dtype=float)
    plain[order] = np.arange(1, len(a) + 1, dtype=float)   # 1..n dense ranks
    # average ranks within tie groups
    uniq, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
    # sum of plain ranks per unique value / count = average rank
    sums = np.zeros(len(uniq))
    np.add.at(sums, inv, plain)
    return (sums / counts)[inv]


def spearman(x, y):
    """Independent Spearman = Pearson of average-ranks."""
    rx, ry = avg_rank(x), avg_rank(y)
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


sys.path.insert(0, str(_ROOT / "scripts" / "research"))
import b103_lhb_inst_ic as b103  # noqa: E402  (verified data loader, B103)
from b094_youzi_ic import load_prices  # noqa: E402  (verified price loader, B094)

EVENTS = _ROOT / "data/research/b094_youzi/events.csv"
PRICES = _ROOT / "data/research/b094_youzi/prices.csv"
SEATS = _ROOT / "data/research/b104_seats/seats_expanded.csv"
MIN_NAMES = 5


def indep_rank_weights(sigs):
    """Independent demeaned-rank dollar-neutral unit-gross weights (scipy ranks, avg ties)."""
    a = np.asarray(sigs, dtype=float)
    if len(a) < 2:
        return None
    ranks = avg_rank(a)   # independent of b094._avg_ranks
    d = ranks - ranks.mean()
    denom = np.abs(d).sum()
    if denom == 0:
        return None
    return d / denom


def cagr(cum, n):
    return (1.0 + cum) ** (12.0 / n) - 1.0 if n > 0 and (1 + cum) > 0 else None


def sharpe(rets):
    a = np.asarray(rets, dtype=float)
    if len(a) < 2 or a.std(ddof=1) == 0:
        return None
    return float(a.mean() / a.std(ddof=1) * math.sqrt(12))


def tstat(rets):
    a = np.asarray(rets, dtype=float)
    if len(a) < 2 or a.std(ddof=1) == 0:
        return None
    return float(a.mean() / (a.std(ddof=1) / math.sqrt(len(a))))


def cum(rets):
    t = 1.0
    for r in rets:
        t *= 1.0 + r
    return t - 1.0


def main():
    events = b103.load_events(EVENTS, SEATS)
    prices = load_prices(PRICES)
    cohorts = b103.build_cohorts(events, prices, (1, 5, 10))["cohorts"]
    n_sampled = sum(1 for e in events if e.inst_buy_net is not None)
    print(f"inst_net_sampled_events = {n_sampled}   (report claims 1309)")

    for n in (1, 5, 10):
        gross, longleg, shortleg, lo_excess, lo_abs, idx, ics = [], [], [], [], [], [], []
        names_per = []
        for month in sorted(cohorts):
            rows = cohorts[month]
            pairs = [(r["inst_buy_net"], r["fwd"][n]) for r in rows
                     if r.get("inst_buy_net") is not None and r["fwd"][n] is not None]
            if len(pairs) < MIN_NAMES:
                continue
            sigs = np.array([p[0] for p in pairs], float)
            rets = np.array([p[1] for p in pairs], float)
            w = indep_rank_weights(sigs)
            if w is None:
                continue
            names_per.append(len(pairs))
            # dollar-neutral L/S
            gross.append(float(w @ rets))
            # leg decomposition (longs w>0 sum=+0.5, shorts w<0 sum=-0.5)
            longleg.append(float(w[w > 0] @ rets[w > 0]))
            shortleg.append(float(w[w < 0] @ rets[w < 0]))
            # long-only book: positive weights renormalized to full investment (sum u =1)
            u = np.where(w > 0, w, 0.0)
            u = u / u.sum()
            lo_abs.append(float(u @ rets))
            m = float(rets.mean())            # equal-weight cohort = index proxy
            idx.append(m)
            lo_excess.append(float(u @ rets) - m)   # long-only vs index (no short needed)
            ics.append(spearman(sigs, rets))

        k = len(gross)
        gt = tstat(gross)
        print(f"\n===== N{n}  ({k} cohorts, avg {np.mean(names_per):.1f} names) =====")
        print(f" GROSS L/S : cum {cum(gross):+.4f} ann {cagr(cum(gross),k):+.4f} "
              f"Sharpe {sharpe(gross):.3f} t {gt:.2f}  pos {sum(g>0 for g in gross)}/{k}")
        for bp in (30, 40, 50, 80):
            net = [g - bp / 10000.0 for g in gross]
            print(f"   NET {bp}bp: cum {cum(net):+.4f} ann {cagr(cum(net),k):+.4f} "
                  f"Sharpe {sharpe(net):.3f}  pos={cum(net)>0}")
        print(f" LONG leg contrib : mean {np.mean(longleg):+.5f}/mo  "
              f"cum {cum(longleg):+.4f} Sharpe {sharpe(longleg):.3f}  (gross exp 0.5)")
        print(f" SHORT leg contrib: mean {np.mean(shortleg):+.5f}/mo  "
              f"cum {cum(shortleg):+.4f} Sharpe {sharpe(shortleg):.3f}  (gross exp 0.5)")
        share = np.mean(shortleg) / (np.mean(longleg) + np.mean(shortleg)) * 100
        print(f"   -> SHORT leg = {share:.0f}% of gross mean; LONG leg = {100-share:.0f}%")
        # long-only vs index (the A-share-feasible implementation)
        loe_t = tstat(lo_excess)
        print(f" LONG-ONLY vs index (feasible): excess mean {np.mean(lo_excess):+.5f}/mo "
              f"cum {cum(lo_excess):+.4f} Sharpe {sharpe(lo_excess):.3f} t {loe_t:.2f}")
        for bp in (40,):
            # long-only trades the long book once (1.0 notional round trip) => 40bp
            net_lo = [e - bp / 10000.0 for e in lo_excess]
            print(f"   NET {bp}bp long-only-vs-index: cum {cum(net_lo):+.4f} "
                  f"ann {cagr(cum(net_lo),k)} Sharpe {sharpe(net_lo)}  pos={cum(net_lo)>0}")
        # IC consistency (independent Spearman)
        cc = float(np.corrcoef(ics, gross)[0, 1])
        ss = sum((a > 0) == (b > 0) for a, b in zip(ics, gross, strict=True))
        print(f" mean cohort IC {np.mean(ics):+.4f}  corr(IC,L/S ret) {cc:.3f}  "
              f"same-sign {ss}/{k} ({ss/k:.0%})")


if __name__ == "__main__":
    main()
