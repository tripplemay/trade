# B094 — 游资 (retail hot-money) 席位 first-look

> **Research-only.** No production code, no strategy product code, no ¥200 paid data touched.
> New code lives in `scripts/research/`, tests in `tests/unit/`, data cached (gitignored) in
> `data/research/b094_youzi/`. All data free via `akshare`.

## Honest frame (read first)

This is the **FREE, documented "second sleeve"** of the smart-money backlog — tracking
**游资/打板** (chasing limit-ups). It is **NOT** the user's PRIMARY institutional-following
goal. That primary goal needs the paid **Tushare ¥200** full-coverage LHB *institutional*
seats (`top_inst`, 2005+, incl. small-cap/delisted) and is deliberately left for the user
(see `docs/research/ashare-smart-money-paid-data-sources-2026-06.md`).

游资/打板 is a **known crowded, loss-prone game** (post-close T+1 disclosure → fully public →
拥挤; 异动-conditioned subset of high-risk stocks). A **NO-GO / INCONCLUSIVE was the expected
and fully valid outcome** — like B092/B093's honest negatives. No GO was manufactured.

**Verdict: NO-GO.** Following 游资 buys did not merely fail to help — it **significantly
UNDERPERFORMED** the naive "just buy every LHB name" baseline.

---

## 1. Coverage

| Item | Value |
|---|---|
| Window | 2022-01 .. 2024-12 (35 monthly cohorts) |
| LHB events fetched (`stock_lhb_detail_em`, monthly) | **52,337** across 704 trading days |
| 游资-buy flagged events (解读 "实力游资买入") | **8,725** (16.7%) |
| Active branches aggregated (`stock_lhb_hyyyb_em`) | 11,744 (11,741 游资 / 2 股通 / 1 机构) |
| Per-event seat sample (`stock_lhb_stock_detail_em`) | 800 events (seat-level 游资 net buy) |
| qfq price universe fetched (`stock_zh_a_daily`) | **1,500 tickers** (deterministic seed-94 subset of 5,167 unique event tickers), 1.3M+ bars |
| Events with a joined forward return | **12,502 (23.9%)** across 35 months |

**Coverage caveat (honest):** price fetch was capped at a **1,500-ticker random subset** (the
full 5,167-ticker fetch ran ~3.5 h; capped for a bounded first-look). Combined with the fact
that many small-cap LHB names sit outside the subset, forward-return coverage is **23.9%** of
events. The **sign and significance of the result are robust** across 12,502 events / 35 months,
but the magnitude is a first-look estimate on a partial universe, not a full-coverage number.

## 2. 游资 seat identification method (a documented judgment call)

Two complementary, honestly-imperfect methods; both point the same way:

**(a) Seat-name classification** (`classify_branch`, unit-tested): 机构 seats carry the
exchange label **"机构专用"**; 沪/深股通 carry **"股通"**; everything else is a **named 营业部
(branch office) = 游资 candidate**. This is the standard, documented convention.

**(b) Buy-side frequency heuristic** (the well-known active hot-money seats): rank the named
branches by how many monthly windows they appear on the LHB **buy** side. The top of the list
is unambiguously the canonical **打板天团**:

| buy-windows | branch |
|---|---|
| 643 | 东方财富证券·拉萨东环路第二营业部 |
| 643 | 东方财富证券·拉萨团结路第一营业部 |
| 643 | 东方财富证券·拉萨团结路第二营业部 |
| 642 | 东方财富证券·拉萨东环路第一营业部 |
| 590 | 东方财富证券·山南香曲东路营业部 |
| 475 | 华鑫证券·上海分公司 |
| 463 | 财通证券·杭州上塘路营业部 |
| 570 | 中国银河证券·北京中关村大街营业部 |

The **拉萨天团** (东方财富拉萨营业部群) topping the list is a textbook validation of the
heuristic — these are THE famous retail hot-money seats. *Limitation:* a few high-frequency
**总部/分公司** rows (华泰总部, 中金上海, 国君总部) also classify as 游资 by name but are really
mixed 大户/institutional-adjacent order-routing seats — pure name-based classification cannot
separate them. This is disclosed, not hidden.

**(c) Tag cross-validation** (解读 vs raw seats, on the 800-event seat sample): the EastMoney
**解读 "实力游资买入"** editorial tag agrees with the raw seat classification — **141/141 (100%)**
tagged events have a **positive 游资-seat net buy** with the top 游资 seat's net ≥ the
institutional net, and tagged events carry ~2× the 游资 net of untagged (¥141M vs ¥74M). So the
cheap full-coverage **游资-buy flag** is a sound proxy for "a 游资 seat is a top net buyer."

## 3. Signal + no look-ahead

For each LHB date **T** where a 游资 seat is a net buyer, the follow signal is **known at close
of T**. Entry is **T+1** (first trading bar *strictly after* T, `bisect_right`); forward return
is measured over **T+1 .. T+1+N**, strictly > T. This no-lookahead property is **unit-tested**
(`test_forward_return_enters_strictly_after_event_date`, `test_event_exactly_on_a_bar_uses_next_bar_not_same_bar`).
Sampling is by **monthly cohort** (one cross-section per calendar month) to avoid overlap inflation.

## 4. Rank-IC (游资-buy flag signal), monthly cohorts, t-stat over 35 months

| Horizon | mean monthly rank-IC | t-stat | n pairs |
|---|---|---|---|
| N=1  | **-0.0084** | -0.80 | 12,502 |
| N=5  | **-0.0434** | **-4.10** | 12,502 |
| N=10 | **-0.0426** | **-3.16** | 12,502 |

The 游资-buy flag has a **significantly NEGATIVE** rank-IC at N=5 and N=10. Being bought by
游资 predicts **lower**, not higher, forward returns.

**Seat-level 游资 net-buy signal** (thin, 800-event sample → ~232 usable pairs): same negative
direction, insignificant — N1 -0.028 (t=-0.25), N5 **-0.188** (t=-1.83), N10 -0.134 (t=-1.29).

**Baseline signal — total LHB net buy** (all seats): essentially zero — N1 +0.016 (t=1.07),
N5 -0.013 (t=-0.88), N10 -0.020 (t=-1.25). Confirms there is no low-hanging LHB-net-buy edge either.

## 5. Long-only follow backtest vs baseline

Each month: **FOLLOW** = equal-weight the 游资-bought names, hold N days. **BASELINE** =
equal-weight **all** LHB names that month (the "just buy the LHB" null). Edge = follow − baseline,
paired t-stat over 35 months.

| Horizon | follow mean | baseline mean | edge (follow−base) | edge t-stat | months follow beats base |
|---|---|---|---|---|---|
| N=1  | -0.55% | -0.52% | **-0.04%** | -0.24 | 17 / 35 |
| N=5  | -3.03% | -2.02% | **-1.00%** | **-2.92** | 12 / 35 |
| N=10 | -3.99% | -3.22% | **-0.77%** | -1.47 | 13 / 35 |

Following 游资 buys **underperforms** the naive all-LHB basket at every horizon, **significantly so
at N=5** (-1.00%, t=-2.92), and beats the baseline in only **12/35 months** at N=5.

> Note: *all* forward returns are negative on average — LHB events are **异动-conditioned** (a big
> move already happened), so subsequent mean-reversion drags the whole cross-section down. The
> load-bearing comparison is **follow vs baseline**, and 游资-bought names are the *worse* subset.

## 6. Verdict: **NO-GO**

No horizon shows a positive IC ≥ 0.03 with |t| ≥ 2, and the best 游资-follow edge over the all-LHB
baseline is **-0.04% (≤ 0)**. In fact **2 IC horizons and 1 follow-edge horizon are significantly
NEGATIVE** (|t| ≥ 2) — **following 游资 buys actively hurt** relative to just buying every LHB name.

This is the honest **劝退** for the crowded, loss-prone 打板 game and the **expected outcome** for
this FREE secondary sleeve. It is consistent with the prior data research (匿名 / 可马甲 / 异动 /
滞后 / 拥挤) and with B077's weak institutional-seat IC.

**The PRIMARY institutional-following goal is untouched and still open** — it needs the paid
**Tushare ¥200** full-coverage LHB *institutional* seats + full-market delisted-inclusive prices,
which this free first-look deliberately did not buy.

### Caveats (welded on)
1. First-look, **not** a tradeable/deployable claim; research-state / no broker / no real money.
2. **23.9% forward-return coverage** (1,500-ticker price cap + small-cap names outside it) — sign
   and significance robust across 12,502 events/35 months, magnitude is partial-universe.
3. **Selection bias:** 异动-conditioned events; the negative mean is partly mechanical mean-reversion.
   The follow-vs-baseline edge controls for this and is still negative.
4. Seat-name 游资 classification cannot separate a few 总部/分公司 mixed seats (disclosed in §2).
5. No survivorship-free universe here (unlike B070/B077) — a delisted name inside the horizon
   yields `None` for the longer N (position couldn't be held), which is correct but not a full
   survivorship treatment.

## 7. Files

| File | Role |
|---|---|
| `scripts/research/b094_youzi_fetch.py` | fetch events + active branches + seat sample + qfq prices; 游资 classification |
| `scripts/research/b094_youzi_ic.py` | no-lookahead forward returns, monthly rank-IC + t-stat, follow backtest vs baseline, verdict |
| `tests/unit/test_b094_youzi.py` | 22 deterministic tests: no-lookahead, seat classification, IC, verdict logic |
| `data/research/b094_youzi/{events,branches,seats_sample,prices}.csv` | cached data (gitignored) |

### Reproduce
```bash
# fetch (slow, one-time; prices capped at 1500 tickers ~1h)
workbench/backend/.venv/bin/python scripts/research/b094_youzi_fetch.py \
  --from 2022-01 --to 2024-12 --stages events,branches,seats,prices \
  --sample-size 800 --max-tickers 1500 --seed 94
# analyse (fast, deterministic)
workbench/backend/.venv/bin/python scripts/research/b094_youzi_ic.py
# gates
./.venv/bin/python -m ruff check scripts/research/b094_youzi_fetch.py scripts/research/b094_youzi_ic.py tests/unit/test_b094_youzi.py
./.venv/bin/python -m pytest tests/unit/test_b094_youzi.py -q
```
