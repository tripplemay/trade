# B104 — inst_buy_net seat-sample EXPANSION: does B103's +0.20 hold or decay?

**Research-only pre-check. No broker, no real money, no production touched.**
Date: 2026-07-06. Free akshare LHB, 2022–2024, all A-share stocks.

## The question

B103 found the exact per-event institutional net-buy ¥ (`inst_buy_net`, summed over
"机构专用" LHB seats) has a **5-day forward-return rank-IC of +0.205 (t=2.22)** — but on
only **232 price-covered pairs / 26 months**, because B094 fetched per-event seat detail
for just 800 of the 52k LHB events. Is that +0.20 a **real signal** (survives a larger
free sample) or **thin-sample noise** (decays)?

B104 expands the seat sample: reuse B094's 800 seats verbatim + fetch seats for a
**deterministic seed-104 sample drawn from the PRICE-COVERED event universe** (so every
new pair is usable), then rerun **B103's exact no-look-ahead IC machinery** (imported
verbatim: bisect_right entry T+1, forward returns strictly > T, monthly cross-sectional
rank-IC + t-stat, follow backtest) on the enlarged file.

## Achieved sample (honest — partial expansion)

The per-event seat fetch (`ak.stock_lhb_stock_detail_em`) is **slow** (this is exactly why
B094 capped at 800). The full seed-104 target was ~2,700 new price-covered events (→ ~3,500
total). **The current on-disk sample is 1,000 total seat events (800 existing + 200 new,
all price-covered)** — a **partial expansion (1,000 of the ~3,500 target)**. The fetcher is
**checkpointed every 100 rows and fully resumable** — re-running `b104_seat_expand_fetch.py`
continues toward the full target from where it stopped.

These are the **reproducible current numbers**: re-running `b104_inst_net_ic.py` on the
on-disk `seats_expanded.csv` regenerates `data/research/b104_seats/ic_result.json`, which
this report matches exactly.

| metric | B103 baseline | B104 (current on-disk) |
|---|---|---|
| seat events fetched | 800 | 1,000 (800 + 200 new, price-covered) |
| `inst_buy_net` pairs (pooled, N5) | **232** | **485** (2.09×) |
| months with signal (N5) | 26 | **35** |

The pair count more than doubled (485 vs 232) and the month span widened (35 vs 26), so
this is a **materially-more-powerful-than-B103** test — but it is **still short of** the
~3,500 target, so a fuller expansion can only sharpen (not overturn) the read below.

## Result — inst_buy_net rank-IC, expanded vs B103

| horizon | B103 IC (t) / 232 pairs | B104 IC (t) / 485 pairs | read |
|---|---|---|---|
| N1  | +0.137 (1.69) | **−0.0105 (−0.18)** | collapsed to ~0 (slightly negative, insignificant) |
| **N5**  | **+0.205 (2.22)** | **+0.148 (2.92)** | **HOLDS: significance strengthens, magnitude attenuates** |
| N10 | +0.170 (2.10) | **+0.1615 (2.84)** | **HOLDS: still significant on 2.1× the pairs** |

Follow backtest (binary `inst_buy_flag`, all events) N5 edge = −0.004 (t=−1.03) — the
"just follow institution-tagged names" null still has **no positive edge** (unchanged from
B103; the tradeable-follow story was never the strong part — the graded `inst_buy_net`
cross-section is).

## Holds or decays? — **HOLDS on the headline horizon**

On the headline 5-day horizon the signal **HOLDS**: the t-stat **rises to 2.92** on **2.1×
the pairs** (485 vs 232) and **more months** (35 vs 26), and the IC stays clearly positive
at **+0.148 (≈72% of B103's +0.205)**. The point-estimate coming down from 0.205 → 0.148 is
**expected mean-reversion** of an upward-biased thin-sample estimate — the true 5-day IC
likely sits in the **~0.10–0.15** band, which is still economically meaningful and now
clears significance more comfortably than B103 did (t **2.92 vs 2.22**). This is the **first
promising free result this session**.

**Horizon read (honest):** the effect is **horizon-dependent, not horizon-fragile**. N1
(1-day) collapses to ~0 (**−0.0105, t −0.18**) — the effect is **not instantaneous** — but
**both** the N5 (t 2.92) and N10 (t 2.84) multi-day horizons hold significance. Two adjacent
multi-day horizons both holding is **more reassuring than a lone-horizon spike** (the earlier
first-checkpoint had N10 at only t≈1.63; on the current 485-pair sample N10 firms up to
**+0.1615, t 2.84**). Caveat: N1's slight flip to negative is a reminder the sample is still
thin and 2022–2024-bound — do not over-read the exact per-horizon magnitudes.

## Verdict — **GO-LEAN (HOLDS, partial sample)**

The +0.20 does **not evaporate** — its 5-day (and 10-day) significance survives sample
expansion and in fact **firms up**, which **strengthens (does not settle)** the case for the
paid test. Not a NO-GO (the signal held), not a clean GO (partial sample, N1 null, no
follow-edge). Recommended next steps, in order:
1. **Finish the free expansion** — resume `b104_seat_expand_fetch.py` from the current 200
   new events toward the full ~2,700 new (~3,500 total) to confirm the 5-day t-stat stays
   ≥2 at ~2,000+ pairs.
2. **Then the paid Tushare ¥200** — the decisive clean test.

## Honest frame — why this is only a pre-check

Even a fully expanded **free** sample is still: **2022–2024 only**; **survivorship-limited**
(akshare's free feed omits delisted names); and **LHB-selection-conditioned** (already-moved
names). A HOLDS here is a *stronger free signal*, **not** a tradeable claim and **not**
survivorship-clean. The **paid Tushare ¥200** full-history LHB (2005+, delisted survivors,
~50× the sample, cleaner seat identification) remains the **decisive clean test**. B104 is
the free pre-check that says: *the signal is worth the ¥200 — it held (and firmed up) on
2.1× the free data.*

## No-look-ahead

Reused verbatim from B103/B094 and unit-tested: the LHB list for day T is public only
**after close of T**; entry is the first trading day **strictly after T** (`bisect_right`,
so the entry index has date > T); forward returns are measured strictly **> T**.
`tests/unit/test_b104_inst_net.py` asserts entry-strictly-after-T, seed-104 sample
determinism/independence, price-coverage filtering, `机构专用` net aggregation, and the
holds/decays verdict logic (**17 tests, all passing**).

## Files

- `scripts/research/b104_seat_expand_fetch.py` — seed-104 price-covered seat expansion
  (checkpointed every 100 rows, resumable, socket-timeout + skip-on-error).
- `scripts/research/b104_inst_net_ic.py` — B103-machinery IC rerun + holds/decays verdict.
- `tests/unit/test_b104_inst_net.py` — 17 deterministic offline tests (all passing).
- `data/research/b104_seats/seats_expanded.csv` — accumulating seat sample, 1,000 events
  (gitignored).
- `data/research/b104_seats/ic_result.json` — reproducible IC output this report matches
  exactly (N5 IC +0.148 / t 2.92 / 485 pairs / 35 months).
