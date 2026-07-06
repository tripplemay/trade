# B099 — 机构建仓 (institutional-building) first-look

**Type:** research-only first-look (no production code, no broker, no paid data, no commit)
**Date:** 2026-07-06
**Verdict:** **NO-GO / INCONCLUSIVE** (no reliable edge in the FREE quarterly version)

---

## Honest frame

This is the **FREE, QUARTERLY** sleeve of the user's REAL goal — 跟踪机构建仓动向跟随获利
(track institutions building positions and follow). Unlike 游资 (B094, retail hot-money,
NO-GO), it uses **genuine institutional holdings** sourced from the quarterly reports'
十大流通股东 (top-float holders) via `akshare.stock_institute_hold`.

The paid **¥200 Tushare** version of this idea is **DAILY** (LHB institutional seats). This
free version is **QUARTERLY** and, critically, disclosed with a **1–4 month LAG**. So this
test answers: *does following institutional accumulation help when the only signal you can
see for free is the stale, quarterly, disclosure-lagged holdings snapshot?*

- If quarterly-lagged institutional-building had shown an edge → it would **motivate** paying
  for the ¥200 daily version (daily removes most of the lag).
- It shows **no reliable edge** → this **weakens** expectations that the free-data path works,
  but does **not** condemn the ¥200 daily version: the daily LHB feed is a genuinely different,
  much-lower-latency signal. The failure here is largely attributable to the **disclosure lag**,
  which the paid daily version specifically shortens — so this is a reason to be *skeptical and
  test cheaply first*, not a reason to abandon the institutional-following thesis.

A NO-GO / INCONCLUSIVE is a valid, valuable outcome (cf. B092 / B093 / B094).

---

## Coverage

**Institutional panel** (`stock_institute_hold`, 2020Q1..2024Q4, 20 quarters):

| metric | value |
|---|---|
| quarters fetched | 20 / 20 |
| panel rows | 49,193 |
| unique stocks | 4,995 |
| stocks / quarter | ~1,676 (2020Q2) → ~3,317 (2023Q4); 2024Q4 only 346 scored (partial disclosure) |

**Prices** — reused from the **B070/B081 survivorship-free PIT qfq cache**
(`data/research/b070/b081_prices_cache.pkl`, 2018–2026, `adj_close`). That ~1,310-name
universe was selected by B070 on **size/liquidity/quality — independent of the
institutional-building signal**, so it does not bias the signal. It is the documented
**deterministic liquid-subset cap** (the same one B083-PEAD used); re-fetching qfq for all
4,995 names was avoided.

| metric | value |
|---|---|
| price universe (intersection) | **1,267 tickers = 25.4%** of institutional universe |
| price rows | 1,961,474 |
| price date range | 2019-10-08 → 2026-06-18 |
| scored stocks / quarter | ~770 → ~1,076 |

> **Coverage bias (stated honestly):** the price universe is a **large/liquid tilt**
> (25% of names). Institutional-building on small caps is under-sampled. A different
> universe could shift the numbers, but the near-zero IC is unlikely to be a coverage
> artifact given how symmetrically it flips sign across quarters.

---

## Disclosure-lag handling (the cardinal risk)

A-share quarterly reports disclose with a **lag** after quarter-end. The 机构持股 for
quarter Q is **NOT public at Q-end**. Entry is placed **conservatively**, on the first
trading day on/after the **first day of the month AFTER the legal disclosure deadline**
(a full extra month past the deadline):

| quarter | ends | legal deadline | conservative entry floor |
|---|---|---|---|
| Q1 | Mar 31 | Apr 30 | **May 1** |
| Q2 | Jun 30 | Aug 31 | **Sep 1** |
| Q3 | Sep 30 | Oct 31 | **Nov 1** |
| Q4 / annual | Dec 31 | **Apr 30 next year** | **May 1 next year** |

Forward returns are measured **strictly after** that entry (`price[entry+H] / price[entry] − 1`,
future bars only). **Audited:** all 20 quarterly entries fall strictly after their disclosure
deadline (0 violations — verified in `ic_result.json` `entry_after_deadline` and pinned by
`test_b099_inst.py`). Using Q-end as entry would be look-ahead and invalidate the result.

> Note the **Q4/Q1 collision**: a year's Q4 (annual) and the next year's Q1 both disclose by
> Apr 30, so both enter ~May 1 (e.g. 2020Q4 & 2021Q1 → 2021-05-06). Each still contributes its
> own cross-section; IC is averaged across quarters, so the collision does not corrupt it.

---

## Results

Signal = cross-sectional **rank of 持股比例增幅** (institutional holding-% increase; PRIMARY)
and **机构数变化** (institutions joined; SECONDARY). **Prior stated once, not tuned:** weak
positive next-quarter IC (~**+0.03**). Rank-IC computed per quarter (Spearman), then averaged
over the 20 cross-sections; `t = IC_IR · √N`.

| run | mean IC | IC_IR | t-stat | hit rate | long cum | base cum | excess cum |
|---|---|---|---|---|---|---|---|
| primary 持股比例增幅, 1mo (21td) | +0.0064 | 0.16 | **0.70** | 0.55 | +80.4% | +72.1% | +8.3% |
| primary 持股比例增幅, 1q (63td) | **−0.0072** | −0.13 | **−0.59** | 0.45 | +218% | +169% | +49% |
| secondary 机构数变化, 1mo (21td) | +0.0056 | 0.11 | **0.51** | 0.50 | +79.9% | +72.1% | +7.7% |
| secondary 机构数变化, 1q (63td) | +0.0069 | 0.11 | **0.50** | 0.65 | +233% | +169% | +64% |

Baseline = equal-weight the **entire covered universe** that quarter. Long = equal-weight the
**top-quintile** by signal, rebalanced quarterly at the disclosure-lagged entry.

**Per-quarter IC is pure noise:** it swings from **−0.087 to +0.148** with no persistence,
averaging ≈ 0. Every |t-stat| < 1 — **not statistically distinguishable from zero** at any
horizon or on either signal.

### Why the backtest "excess" is a mirage

The 1-quarter long-only book shows a positive **cumulative** excess (+49% to +64%), which
looks tempting — but it is **not supported by the IC**:

- The primary 1q signal has a **slightly negative** mean IC (−0.007) yet a **+49%** cumulative
  excess. A monotone signal cannot do that; the "excess" is driven by a **handful of bull-phase
  quarters** (2020Q4/2021Q1/2021Q4 each ~+10% excess) and is a **beta/size tilt** of the
  top-quintile in a rising market, not a persistent cross-sectional edge.
- Quarterly excess **hit rate is coin-flip** (0.45–0.65); quarterly excess flips sign
  constantly. This is a long-only, non-market-neutral book, so its cumulative number mostly
  reflects the universe's raw drift, not signal skill.

---

## Verdict: NO-GO / INCONCLUSIVE

Following institutional accumulation **as visible in the free, quarterly, disclosure-lagged
holdings data has no reliable edge**: rank-IC ≈ 0, every t < 1, hit rate ~coin-flip, and the
only positive backtest number is an unhedged beta/size artifact unsupported by the IC.

**Most likely cause = the disclosure lag itself.** By the conservative entry (1–4 months after
quarter-end), the accumulation is months stale and — for a signal built on *last quarter's*
top-float-holder snapshot — largely priced in. This is exactly the latency that the paid
**¥200 daily** LHB-seat feed is designed to cut.

**Implication for the ¥200 daily version:** this result **lowers the prior** that a cheap
free-data path can capture institutional-following alpha, but does **not** refute the daily
version — daily latency is a materially different (and testable) regime. Recommended next step
before spending: a **latency-sensitivity probe** — if IC stays ≈ 0 even at the *shortest* free
horizon reachable here, daily is less likely to help; if IC is only killed by the lag, the
daily feed becomes worth a bounded paid trial.

---

## Files

- `scripts/research/b099_inst_fetch.py` — panel + price-subset fetch (ran; 20 quarters)
- `scripts/research/b099_inst_ic.py` — disclosure-lagged IC + backtest (ran)
- `tests/unit/test_b099_inst.py` — 12 deterministic tests (no-look-ahead, signal, IC)
- `docs/test-reports/B099-inst-building-first-look.md` — this report
- `data/research/b099_inst/{inst_panel.csv, prices.pkl, coverage.json, ic_result.json}` — gitignored cache

## Gates

- `ruff check` (3 files) → **All checks passed**
- `pytest tests/unit/test_b099_inst.py -q` → **12 passed**
