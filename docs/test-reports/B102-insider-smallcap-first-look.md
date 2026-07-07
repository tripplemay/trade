# B102 — Insider-Buying on the SMALL-CAP Sleeve: First Look

**Status:** research-only (no broker / no real money / no production change / no paid data)
**Signal:** major-shareholder / executive NET-BUYING (大股东/高管增持), announcement-lagged,
same as B101 — re-tested on the SMALL-CAP (non-liquid) names B101 could not price.
**Verdict:** **NO-GO** — the 800-name qfq fetch completed at **530 currently-listed names
(66.2%)**, covering **4,017 / 12,290 (32.7%)** of the small-cap insider events in the price
window and **1,017,815 price bars (2018-01-02 → 2026-07-06)** — enough to score **13 monthly
cohorts** (the small-cap sleeve is thin: most months fall below the 20-name minimum
cross-section). On this completed, **survivorship-inflated (upper-bound)** panel the insider-
buying signal shows **no deployable edge**: the only positive is a 5d rank-IC of **+0.086 that
is NOT significant (t=1.18 < 2)**; the event long book **underperforms the passive small-cap
baseline even GROSS at 20d (−7.0%) and 60d (−31.8%)**, and is **NET-negative at every horizon
after a realistic 50bp round-trip (−4.0% / −15.2% / −42.7%)**. Because survivorship makes this
an optimistic UPPER BOUND, even this best case is a NO-GO. The free smart-money exploration
(游资 / 机构建仓 / insider-liquid / insider-smallcap) is now **exhausted** — the paid ¥200/day
LHB institutional-seat data remains the clean decisive test.

---

## 0. Why this batch exists (the gap B101 left open)

B101 tested the insider-buying signal but priced it only on the **998 / 3233 (30.9%)**
insider names that happened to sit in the **liquid, liquidity-tilted B070 cache**. On that
liquid large-cap sleeve the signal showed **no edge** (rank-IC ≈ 0, t-stats insignificant,
60d event excess negative). Codex F002 flagged the honest boundary: the B070 cache is
*liquid-biased*, so the conclusion was only valid for liquid large-caps — the
**small-cap / illiquid sleeve, exactly where A-share insider / smart-money signals
plausibly CONCENTRATE, was never tested.** B102 closes that gap.

Outcome logic:
- If a free signal shows **real small-cap edge that survives realistic costs + the
  survivorship caveat** → a rare, valuable free-signal finding (genuine progress toward
  the institutional-following goal).
- If the raw edge is **absent, or eaten by survivorship / liquidity cost** → NO-GO, and
  the free signal space (liquid + small-cap) is **exhausted**; only the paid ¥200/day LHB
  institutional-seat data remains.

---

## 1. ★★ TWO SMALL-CAP-SPECIFIC HONEST CAVEATS (read first)

### Caveat 1 — SURVIVORSHIP (upward bias)
`ak.stock_zh_a_daily` returns price history **only for names that are CURRENTLY LISTED.**
Small-caps that have since **delisted** (bankruptcy, forced delisting, absorption) are
simply **absent** — they can never enter the sample. Small-caps delist far more often than
large-caps, and delisting is precisely the worst-return tail. So the surviving names are
**upward-selected**: any edge measured here is an **OPTIMISTIC UPPER BOUND**, not a
deployable estimate. This is **unfixable with free data** (a survivorship-free small-cap
PIT panel needs paid history). **We saw it LIVE in the fetch:** of the 800 sampled small-cap
names, **270 (33.8%) returned zero price rows and were dropped** — the feed simply has no
history for names that have delisted/been-suspended. That 34% hole is the survivorship bias
made visible; the 530 that priced are the up-selected survivors on which every number below
is computed (see coverage `fetch_success_pct = 66.2%`).

### Caveat 2 — LIQUIDITY COST (small-caps are expensive to trade)
Small-caps have wide spreads and thin depth. We charge a **realistic round-trip cost** and
report the edge **BOTH gross and net**. Cost build-up (A-share small-cap, round-trip):

| Component | bps (round-trip) |
|---|---|
| Commission (~2.5bp/side) | ~5 |
| Stamp duty 印花税 (sell only, post-2023-08 halving 0.05%) | ~5 |
| Transfer 过户费 | ~0.1 (negligible) |
| Bid-ask half-spread (~15–20bp/side on a thin small-cap) | ~30–40 |
| Residual market impact on low-ADV names | a few |
| **Central estimate** | **~40–50** |

We use **50bp round-trip as the base**, charged **each monthly rebalance on the ACTIVE
(insider-following) long book**, which turns over ~fully every month as the buyer cohort
changes. The **passive small-cap baseline** (equal-weight the covered universe) is a
low-turnover buy-and-hold and is left **gross**, so **NET excess = active-net-cum −
baseline-gross-cum** is the honest deployable comparison (the active book pays its high
turnover; the passive benchmark barely trades). A **30 / 50 / 80bp** sensitivity is
reported.

---

## 2. No-look-ahead handling (identical to B101, unit-tested)

The `增持` feed carries BOTH the **变动截止日 (transaction date)** and the later **公告日
(announcement date)** — 公告 ≥ 变动 (disclosure lag). Entering on the transaction date =
look-ahead = fake edge. We key everything off the **announcement date**:

- Events are bucketed by **announcement month M**.
- The cohort **ENTERS on the first trading day of month M+1** — strictly AFTER *every*
  announcement in the cohort (effective lag ~1 trading day for an end-of-month
  announcement, up to ~1 month for a start-of-month one — conservative on purpose).
- Forward returns (5/20/60 td) are measured **strictly after entry**.
- A `_MAX_ENTRY_GAP_DAYS=15` guard drops cohorts whose M+1 floor has no nearby trading day
  in the price panel (e.g. a pre-2018 announcement snapping onto the cache start) so stale
  cohorts are never scored against unrelated later prices.

This is the **exact machinery imported verbatim** from `b101_insider_ic.py`
(`cohort_entry`, `forward_return`, `monthly_signal`, `run`). Unit tests assert the entry
is strictly after the announcement month and forward returns use only post-entry bars.

---

## 3. Coverage & sampling (signal-independent, deterministic)

_(from `coverage.json` / `sample.json`, completed fetch)_

- Small-cap universe (insider codes NOT in the liquid B070 panel): **2,235** codes.
- Sampling frame (small-cap codes with ≥1 announcement in the price window ≥ 2017-06-01):
  **1,739** codes. Frame is defined by the **existence** of an in-window event — **not by
  any return/outcome** — so it is signal-independent (unit-tested: order-invariant, seed-
  reproducible).
- **Deterministic seed-102 sample: 800 names** (`random.Random(102).sample` over the
  SORTED frame → fully reproducible; documented cap in the requested 600–1000 band; random,
  not outcome-selected).
- **Fetched OK: 530 names** (`fetch_success_pct = 66.2%`). The 270-name (33.8%) shortfall
  from 800 is the **survivorship drop-out** — delisted / suspended names return zero rows
  and are simply absent. This is the upward survivorship bias, observed live.
- Small-cap events covered by the fetched names (in window): **4,017 / 12,290 (32.7%)** of
  the small-cap insider sleeve.
- Price panel: **1,017,815 bars, 2018-01-02 → 2026-07-06**, qfq, B092/B094 floor+spike
  guard applied.
- **Months scored: 13** (of ~101 announcement months). The small-cap cross-section is thin:
  most months carry fewer than the **20-name minimum** required to compute a cohort IC, so
  they are dropped (IC = None). This is a real statistical-power limit — 13 monthly
  observations is a small sample, which is itself a reason the lone +0.086 5d IC cannot be
  trusted.

---

## 4. Results — rank-IC + backtest, GROSS and NET

_(from `ic_result.json`; re-run reproduces byte-identical. 13 months scored, N=530 survivors.)_

### 4.1 Rank-IC (announcement-lagged, small-cap sleeve)

| signal | horizon | mean IC | t-stat | months | significant? |
|---|---|---|---|---|---|
| primary buy_pct | 5 | **+0.0863** | 1.184 | 13 | **NO** (\|t\| < 2) |
| primary buy_pct | 20 | +0.0345 | 0.630 | 13 | no |
| primary buy_pct | 60 | −0.0020 | −0.038 | 13 | no |
| secondary n_events | 5 | +0.0246 | 0.499 | 13 | no |
| secondary n_events | 20 | −0.0225 | −0.439 | 13 | no |
| secondary n_events | 60 | −0.0176 | −0.311 | 13 | no |

The **single positive** result in the whole panel is the primary 5d rank-IC of **+0.086**,
and even that is **statistically insignificant (t = 1.18, well below the |t| ≥ 2 bar)** on
only 13 monthly observations. IC decays to zero by 20d and is nil/negative by 60d. The
secondary event-count signal is near-zero at every horizon.

### 4.2 Event long backtest vs small-cap equal-weight baseline (primary event book)

| horizon | event cum (gross) | baseline cum (gross) | excess (gross) | event NET@50bp | NET excess@50bp | excess hit |
|---|---|---|---|---|---|---|
| 5 | −2.97% | −5.13% | **+2.16%** | −9.11% | **−3.98%** | 0.462 |
| 20 | +31.33% | +38.35% | **−7.01%** | +23.19% | **−15.16%** | 0.462 |
| 60 | +79.67% | +111.43% | **−31.76%** | +68.71% | **−42.72%** | 0.385 |

Read this carefully: the insider-following event book only beats the passive small-cap
baseline **gross at the 5d horizon (+2.16%)** — and that thin edge is **more than erased by
a single 50bp round-trip (net excess −3.98%)**. At 20d and 60d the event book **loses to a
buy-and-hold of the same universe even before costs** (−7.0%, −31.8% gross), and the excess
hit-rate is below 0.5 (the cohort beats baseline in a minority of months). Following insider
buys, net of realistic cost, **destroys value at every horizon**.

### 4.3 Cost sensitivity — event NET excess vs baseline (negative across the whole grid)

| horizon | @30bp | @50bp | @80bp |
|---|---|---|---|
| 5 | −1.57% | −3.98% | −7.48% |
| 20 | −11.96% | −15.16% | −19.82% |
| 60 | −38.41% | −42.72% | −48.99% |

Every cell is negative — there is **no cost assumption in the plausible 30–80bp band** at
which the small-cap insider event book delivers a positive net excess over the passive
baseline. Even the most generous 30bp / 5d corner is −1.57%.

---

## 5. Small-cap vs B101 liquid (side-by-side)

| | B101 LIQUID (998 names, 82–83 mo) | B102 SMALL-CAP (530 names, 13 mo) |
|---|---|---|
| mean IC (primary, 5d) | −0.019 (t=−0.86) | +0.086 (t=1.18) |
| mean IC (primary, 20d) | −0.036 (t=−1.58) | +0.035 (t=0.63) |
| mean IC (primary, 60d) | +0.003 (t=0.12) | −0.002 (t=−0.04) |
| event excess cum (5d) | +0.12 (gross) | +0.02 (gross) |
| event excess cum (20d) | +0.14 (gross) | −0.07 (gross) |
| event excess cum (60d) | −1.20 (gross) | −0.32 (gross) |
| net-of-cost edge | none | negative at every horizon |
| survivorship | B070 cache is survivorship-free | **upward-biased (33.8% delisted dropped)** |
| verdict | NO-GO (no liquid edge) | **NO-GO (no small-cap edge)** |

Neither sleeve shows a significant, deployable insider-buying edge. The small-cap 5d IC
(+0.086) is the largest single positive across both batches, but it is insignificant (t=1.18),
rests on only 13 monthly cohorts, is net-negative after cost, and sits on an **upward
survivorship-biased** panel — the B102 numbers are an optimistic UPPER BOUND, unlike the
survivorship-free B101 liquid panel. That the best-case, upper-bound sleeve still fails is the
strongest possible NO-GO.

---

## 6. Verdict — **NO-GO**

**Insider buying (大股东/高管增持) has no deployable edge on the small-cap sleeve either.**

1. **Signal is insignificant.** The only positive is a 5d rank-IC of +0.086 (t=1.18 < 2), on
   just 13 scoreable months; it decays to ~0 by 20d and turns negative by 60d. The secondary
   event-count signal is near-zero throughout.
2. **The event book underperforms even GROSS** at 20d (−7.0%) and 60d (−31.8%) vs a passive
   equal-weight small-cap baseline, and only edges it at 5d (+2.2%).
3. **Net-negative at every horizon after realistic cost** (−4.0% / −15.2% / −42.7% @50bp;
   negative across the entire 30–80bp grid). The tiny 5d gross edge does not survive one
   round-trip.
4. **And this is an optimistic UPPER BOUND** — the 33.8% of sampled names that delisted are
   silently missing (worst-return tail removed), so a survivorship-free panel would look
   *worse*, not better. A best-case that already fails is a decisive NO-GO.

### What this closes

This result **exhausts the FREE smart-money exploration.** Every free-data avenue toward the
"follow institutional / smart-money accumulation" goal has now returned NO-GO:

- 游资 (hot-money / LHB-derived free proxies) — NO-GO
- 机构建仓 (institutional-accumulation free proxies) — NO-GO
- insider buying, **liquid** large-cap sleeve (B101) — NO-GO
- insider buying, **small-cap** sleeve (B102, this batch) — NO-GO

There is no remaining free signal to test in this family. The **paid ¥200/day LHB
institutional-seat data (Tushare)** remains the one clean, decisive test: it is
survivorship-clean (point-in-time seat records), bulk-fast (no per-name akshare throttling
or delisting holes), and latency-cutting (T+1 seat disclosure rather than the ~1-month
announcement lag this free study had to absorb). If the institutional-following thesis is to
be settled, that is the experiment to run — the free space is done.

### Caveats to carry forward (do not drop)

- **Survivorship (upward):** B102 prices only currently-listed survivors; 33.8% of the
  sample was delisted-and-absent. All B102 edges are optimistic upper bounds.
- **Liquidity cost (real):** small-caps are expensive to trade; the 50bp round-trip base is
  conservative-but-not-extreme, and even 30bp leaves every horizon net-negative.
- **Thin cross-section / small sample:** only 13 of ~101 months cleared the 20-name minimum,
  so all small-cap IC t-stats rest on few observations — another reason the lone +0.086 is
  not evidence of an edge.

**Recommendation:** close the free insider/smart-money line as NO-GO; if the goal is pursued
further, fund the paid LHB institutional-seat test as the next batch.
