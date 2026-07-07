# B105 — Does inst_buy_net's +0.15 IC translate to a COST-SURVIVING long-short edge?

**Probe:** `scripts/research/b105_inst_net_longshort.py` (research-only, no broker, no production)
**Question:** B104 (Codex-verified) found the institutional net-buy signal `inst_buy_net`
(¥ summed over "机构专用" seats) has a forward-return **rank-IC of ~0.148 (5d, t=2.92) /
~0.162 (10d, t=2.84)** on 485 pairs / 35 monthly cohorts. B103's *binary* equal-weight
"follow all inst-buyers" backtest was NON-positive — because a binary follow throws the
RANKING away. This probe asks: does a **rank-weighted dollar-neutral long-short** (long
high `inst_buy_net`, short low) capture that IC as a positive **GROSS** return, and does
it **SURVIVE realistic costs NET**?

## Construction (no-look-ahead, machinery reused verbatim from B103/B094)

- Each **monthly cohort**, rank the names with a known `inst_buy_net` by that signal
  (average ranks for ties). Weights = demeaned rank normalized to unit gross:
  `w_i = (rank_i − mean_rank) / Σ|rank_j − mean_rank|` → **dollar-neutral (Σw=0)**, **unit
  gross (Σ|w|=1)**, monotone increasing in `inst_buy_net`. Uses **ALL pairs**, not thin
  quintiles.
- GROSS cohort return = `Σ wᵢ·fwdᵢ`. **Enter T+1** (`bisect_right`, strictly after the LHB
  date T — reused from B094's verified `forward_returns`), hold to horizon (5d primary,
  10d), **rebalance monthly** → per-cohort returns are a monthly P&L series; cumulative =
  `∏(1+r)−1`; annualized Sharpe = `mean/sd·√12`.
- Sample: 35 cohorts, **~13.9 names/cohort** (same 485-pair / 1309-sampled universe as B104).

## Cost model (A-share small/active LHB names)

Round-trip charged **once per monthly cohort** on the unit-gross book (open + close = one
round-trip of 1.0 notional). Central **40bp** justified as:

| Component | bp (round-trip) |
|---|---|
| Commission ~2.5bp/side × 2 | 5 |
| Stamp duty (sell side only, post-2023-08 rate) | 5 |
| Slippage / impact on small, limit-active LHB names ~15bp/side × 2 | 30 |
| **Central total** | **~40** |

Sensitivity: **30bp** optimistic / **40bp** central / **50bp** realistic-high / **80bp**
conservative (hard-to-trade 涨停 names). Annual cost drag ≈ 12 × round-trip ≈ **4.8%/yr at
40bp**.

## Results

### 5-day horizon (primary)

| | GROSS | NET 30bp | NET 40bp | NET 50bp | NET 80bp |
|---|---|---|---|---|---|
| Cumulative (35 mo) | **+68.4%** | +51.8% | +46.7% | +41.7% | +27.7% |
| Annualized ret | +19.6% | +15.4% | **+14.0%** | +12.7% | +8.7% |
| Annualized Sharpe | 1.15 | 0.94 | **0.87** | 0.79 | 0.58 |
| Positive months | 21 / 35 | — | — | — | — |

GROSS monthly t-stat = 1.97. IC→return consistency: mean cohort IC **0.148**, mean L/S
return **+1.61%/mo**, **corr(IC, L/S ret) = 0.88**, same-sign 94% of cohorts.

### 10-day horizon

| | GROSS | NET 30bp | NET 40bp | NET 50bp | NET 80bp |
|---|---|---|---|---|---|
| Cumulative (35 mo) | **+133.2%** | +110.4% | +103.3% | +96.5% | +77.2% |
| Annualized ret | +33.7% | +29.1% | **+27.6%** | +26.1% | +21.7% |
| Annualized Sharpe | 1.61 | 1.43 | **1.36** | 1.30 | 1.12 |
| Positive months | 25 / 35 | — | — | — | — |

GROSS monthly t-stat = 2.75. IC→return consistency: mean cohort IC **0.162**, mean L/S
return **+2.60%/mo**, **corr(IC, L/S ret) = 0.83**, same-sign 91%.

### 1-day horizon (context)

GROSS is **flat** (cum +2.7%, Sharpe 0.16, mean cohort IC −0.01) → NET goes negative at
every cost level. Consistent with B104: the IC lives at **5–10 days**, not 1 day. This is
a useful negative control — the L/S only pays where the IC exists.

## Verdict: **GO** (cost-surviving, survivorship-caveated)

The +0.15 IC **does translate**: the rank-weighted long-short earns a positive GROSS return
at 5d and 10d, and — decisively — the corr(cohort-IC, L/S-return) of **0.83–0.88** confirms
the portfolio is literally monetizing the rank-IC, not some artifact. **NET survives every
cost level tested (30/40/50/80bp) at both 5d and 10d.** At the central 40bp: 5d nets
**+14.0%/yr (Sharpe 0.87)**, 10d nets **+27.6%/yr (Sharpe 1.36)**. Even at the punitive
80bp round-trip both horizons stay net-positive (5d Sharpe 0.58, 10d 1.12).

**This resolves the B103↔B104 paradox:** the signal was never in "which names did
institutions buy" (binary follow = non-positive) — it is in **HOW MUCH** they net-bought,
i.e. the ranking. A rank-weighted book harvests it; an equal-weight follow discards it.

## Honest framing — this is an UPPER BOUND, NOT a tradeable claim

1. **Survivorship-limited.** Free akshare LHB (2022–2024) omits delisted names → the short
   leg in particular is flattered (worst names that later delisted are missing).
2. **Selection-conditioned.** LHB events are 异动-conditioned (already-moved names); the
   universe is not a clean cross-section.
3. **Short-leg is heuristic.** Shorting individual A-shares is heavily restricted (borrow
   scarce/expensive, 融券 limited) — the dollar-neutral construction assumes a frictionless
   short that does not exist for these small names. Real implementation would be long-tilt
   or long-only-vs-index, materially weaker than the paper L/S here.
4. **Short window.** 35 monthly cohorts; 5d GROSS t=1.97 is just under 2 (10d t=2.75 is
   solid). Not a long-horizon, regime-diverse validation.
5. **Cost model is a point estimate**, not fill-simulated; true impact on 涨停 names can
   exceed 80bp on size.

**The paid Tushare ¥200 full-history LHB (2005+, delisted names, ~50× sample, cleaner seat
identification) remains the DECISIVE clean test.** B105 is a strong *free pre-check*: it
turns B104's "the IC is real" into "the IC survives realistic frictions on paper" —
materially **strengthening the ¥200 case**, without itself being tradeable or
survivorship-clean.

## Files

- `scripts/research/b105_inst_net_longshort.py` — probe (portfolio layer only; no-look-ahead
  cohort machinery imported verbatim from B103/B094).
- `tests/unit/test_b105_inst_net_longshort.py` — 21 deterministic tests (no-look-ahead T+1,
  dollar-neutral + unit-gross + monotone weights, cost-below-gross monotone, IC→return
  consistency, verdict gating).
- `data/research/b105_longshort/result.json` — full numeric output.

## Gates

- `./.venv/bin/python -m ruff check` — PASS
- `./.venv/bin/python -m pytest tests/unit/test_b105_inst_net_longshort.py -q` — **21 passed**
