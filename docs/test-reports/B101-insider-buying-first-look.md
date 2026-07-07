# B101 — Insider / Major-Holder BUYING (大股东/高管增持) First-Look

**Date:** 2026-07-06 · **Type:** research-only signal probe (no production, no broker, no paid data)
**Verdict:** **INCONCLUSIVE, leaning NO-GO** — no deployable edge in the liquid tradeable
universe; the magnitude signal is outright dead; only a faint, non-robust short-horizon
event tilt (~55% monthly hit at 5d) that does not survive to 60d or into the buy-size
ranking. Honest frame: insider buying is a known *mild*-alpha signal, so a positive
result was plausible here — but even this most-promising free angle shows no reliable
edge once the announcement lag is respected on A-share liquid names.

---

## 1. Data source

| item | value |
|---|---|
| akshare function | **`ak.stock_ggcg_em(symbol='股东增持')`** (东方财富 高管持股, buys only) |
| raw rows | 33,405 (paginated ~67 pages, ~3 min; buys-only filter ~2× faster than `'全部'`) |
| clean events (after normalize) | **33,400** across **3,233** unique stocks |
| announcement history | **1996-11-21 → 2026-07-07** |
| **announcement date available?** | **YES** — feed carries BOTH `变动截止日` (transaction) AND `公告日` (announcement) |
| prices | reused B070/B081 survivorship-free PIT qfq cache (`b081_prices_cache.pkl`), 2018-01-02 → 2026-06-18, adj_close |
| tradeable overlap | **998 of 3,233 stocks (30.9%)** — the B070 liquid subset ∩ insider universe |

The `'全部'` variant timed out earlier (~196s for 33k rows including sells); the
`'股东增持'` buys-only filter is the same feed pre-filtered. A transient
`ChunkedEncodingError` mid-pagination is handled with a whole-call retry (succeeds on
attempt 2). Prices are **reused**, not re-fetched — the B070 liquid subset is selected on
size/liquidity/quality **independently** of the insider signal, so it does not bias it.

## 2. The cardinal risk — announcement lag (NO LOOK-AHEAD)

A 增持 transaction occurs on `变动截止日` but is only PUBLIC on the later `公告日`.
Entering on the transaction date would be look-ahead = fake edge. Measured lag (公告日 −
变动截止日) in this feed:

| lag statistic | days |
|---|---|
| median | **3** |
| mean | **60.1** |
| p90 | **183** |

The lag is **real and heavy-tailed** — while most 增持 are disclosed within days
(regulatory window), a long tail is only revealed via periodic reports months later. This
alone justifies keying entry off the announcement date.

**Handling (unambiguously look-ahead-free):** events are bucketed by **announcement
month M**; a single cohort **entry = first trading day of month M+1** — strictly AFTER
every announcement in the cohort. Effective lag ranges from ~1 trading day (end-of-month
announcement) up to ~1 month (start-of-month), conservative on purpose. Forward returns
are measured **strictly after** entry. A cohort whose next-month floor predates the price
panel (e.g. a 2007 announcement) is **skipped**, not snapped onto the 2018 cache start
(guard: entry within 15 days of the floor) — this prevents scoring stale events against
unrelated later prices. After the guard: **83 genuine monthly cohorts, 2017-12 → 2026-04,
median 30 stocks/cohort** (12,249 events in the liquid universe).

## 3. Signal & prior (stated once, NOT tuned)

- **PRIMARY** `buy_pct` = per-stock **sum of 占总股本比例** (% of total share capital the
  insiders bought) across that stock's events in the announcement month — size/conviction
  of the buying. Cross-sectional rank per cohort.
- **SECONDARY** `n_events` = count of distinct buys that month (degenerate — nearly every
  stock has exactly 1 event/month → zero variance → IC undefined; reported as N/A).
- **Prior:** weak positive forward rank-IC ~+0.02..+0.05 at 20-60d; a near-zero result is
  fully plausible given the disclosure lag and A-share noise.

## 4. Results (announcement-lagged, 83 cohorts)

### Cross-sectional rank-IC (does a BIGGER buy predict a higher forward return, among buyers?)

| horizon | mean IC | t-stat | IC-IR | read |
|---|---|---|---|---|
| 5d  | −0.019 | −0.86 | −0.09 | ≈ 0 |
| 20d | −0.036 | −1.58 | −0.17 | ≈ 0 (if anything mildly negative) |
| 60d | +0.003 | +0.12 | +0.01 | ≈ 0 |

All |t| < 2 — **no significant cross-sectional information in buy magnitude.**

### Event long backtest — long ALL insider-buyers vs equal-weight WHOLE universe baseline

| horizon | event mean/cohort | baseline mean | excess/cohort | monthly hit rate |
|---|---|---|---|---|
| 5d  | 0.53% | 0.43% | **+0.10%** | 55.4% |
| 20d | 1.03% | 0.95% | **+0.08%** | 51.8% |
| 60d | 2.47% | 2.74% | **−0.27%** | 46.3% |

### Magnitude book — top-quintile by buy size vs baseline

| horizon | excess/cohort |
|---|---|
| 5d | **−0.31%** |
| 20d | **−0.75%** |
| 60d | **−0.61%** |

## 5. Interpretation

1. **Buy magnitude carries no cross-sectional edge** — IC ≈ 0 at every horizon (|t| < 2),
   and the top-quintile-by-size book *underperforms* the baseline at all horizons. Bigger
   insider buys did **not** lead to better returns in this universe.
2. **The raw event tilt is faint and not robust** — being an insider-buy name beat the
   broad universe by a trivial +0.10%/+0.08% per cohort at 5d/20d with ~52-55% hit, but
   this **flips to −0.27% (46% hit) at 60d**. A real edge should not invert with horizon;
   this looks like short-horizon noise, and it would not survive transaction costs.
3. **Honest limitation — liquid tilt:** the tradeable universe is B070's *liquid* subset
   (998 of 3,233 = 30.9%). If insider-buying alpha concentrates in **small, illiquid
   names** (plausible — that is where insiders have the biggest informational edge), this
   liquid-only test could be washing it out. The small-cap sleeve is **untested** here
   (the reused price cache does not cover it).

## 6. Verdict — INCONCLUSIVE, leaning NO-GO

Following major-holder / executive buying, entered correctly **after** the announcement
date, shows **no deployable edge** on liquid A-shares (2018-2026): magnitude IC ≈ 0, the
size-ranked book loses, and the binary event tilt is economically trivial and
horizon-inconsistent. This is a **NO-GO for the free, liquid version** of the signal as
tested. It is *not* proof the whole angle is dead — two honest open doors remain:

- the **small-cap sleeve** (where insider signals plausibly live) is untested by this
  liquid price cache;
- the separate **paid ¥200/day LHB institutional** feed is a different (daily, seat-level)
  dataset and a separate decision.

Within the honest frame requested: even the most promising *free* angle (insider buying)
**fails to show a reliable edge** in the tradeable liquid universe — consistent with 游资
(B094 NO-GO) and quarterly fund holdings (B099 NO-GO). The free "smart-money" sleeves
tested so far do not yield a robust follow-and-profit signal.

## 7. Reproduce

```bash
# fetch events + slice prices  (~3-4 min; cache is gitignored)
workbench/backend/.venv/bin/python scripts/research/b101_insider_fetch.py
# IC + backtest
workbench/backend/.venv/bin/python scripts/research/b101_insider_ic.py
# gates
./.venv/bin/python -m ruff check scripts/research/b101_insider_fetch.py scripts/research/b101_insider_ic.py tests/unit/test_b101_insider.py
./.venv/bin/python -m pytest tests/unit/test_b101_insider.py -q
```

**Files**
- `scripts/research/b101_insider_fetch.py` — event + price fetch, retry, coverage
- `scripts/research/b101_insider_ic.py` — announcement-lagged IC + event/magnitude backtest
- `tests/unit/test_b101_insider.py` — 14 deterministic tests (no-look-ahead, lag,
  cohort-entry guard, signal aggregation, IC sign, sanity guard)
- `data/research/b101_insider/{insider_events.csv,prices.pkl,coverage.json,ic_result.json}` (gitignored)
