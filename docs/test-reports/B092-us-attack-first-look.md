# B092 — US Attack (concentrated momentum + quality) FIRST-LOOK

**Type:** research-only, low-commitment feasibility probe (the US sibling of B055 /
the P1 attack strategy). **Question:** does US concentrated momentum+quality
selection have a real edge over the right baseline (equal-weight of the same
universe), out-of-sample, net of costs — *before* committing to the full
4-feature P1 build?

**Honest prior:** the A-share version of this strategy (`cn_attack`
momentum+quality) came back **OOS-negative / survivorship-biased** (B070). The
default expectation here is therefore skeptical. A NO-GO / INCONCLUSIVE is a
perfectly valid answer; the cardinal sin would be an over-fit in-sample winner.

---

## 1. Data coverage & quality source

| Item | Result |
|---|---|
| Universe | 100-name S&P-100-style liquid mega/large-cap list (hand-constructed from well-known OEX members; dotted tickers like BRK.B avoided) |
| Prices | **100/100** fetched + SPY, via `akshare.stock_us_daily(adjust='qfq')` (free, no key) |
| Quality source | **SEC EDGAR `companyfacts`** (real fundamentals) — **94/100** names with annual ROE + debt/equity. Missing 6 (PNC, PG, CAT, ITW, VZ, T) report equity under non-standard XBRL tags → simply not qualified those months |
| Quality metric | Point-in-time annual ROE = NetIncome/Equity, leverage = Liabilities/Equity, keyed by SEC **`filed` date** (a rebalance on `t` may only use filings with `filed ≤ t` — no look-ahead) |

**No fallback proxy was needed** — SEC EDGAR was fast enough (~3 s/name) and
covered 94/100. This is *better* than the task's price-proxy contingency.

### ⚠️ Data-quality finding that shaped the whole test

akshare's **free qfq US series is corrupted before ~2017**: pervasive
back-adjustment step-discontinuities produce impossible monthly moves (e.g. UNH
`+2800%` in a single 2013 month, MSFT swinging wildly, BLK `+2740%` Mar-2012).
Counting monthly moves outside `[0.6x, 1.6x]`: **200+ in 2010–2014 vs ≈0/yr from
2017 on.** Two honest guards were applied and are documented in code:

1. `clean_price_spikes` — removes isolated round-trip glitches (462 rows).
2. A **2017-01-01 scored-window floor** — the free data only becomes trustworthy
   here. *This is a data-availability floor, not a tuned parameter.* A paid
   vendor (Tiingo/Norgate) would extend the window.
3. A per-name single-month **data-integrity guard** `[0.40x, 2.50x]` — no
   legitimate megacap monthly move (worst real COVID/2022 months ≈ −40%) is
   excluded, but residual glitches cannot dominate.

**Consequence:** the clean test window is **2017-02 .. 2026-07 (114 monthly
rebalances, ~9.5y)** — a single, largely bull-dominated regime. This is a real
limitation of the free data, called out honestly.

---

## 2. Strategy (priors fixed once — NO parameter tuning to the backtest)

- **Quality filter:** using the latest SEC annual filing available as-of `t`,
  drop non-positive-earnings names AND the bottom quartile by composite
  `z(ROE) − z(debt/equity)`. Names without an available filing are not qualified.
  (median qualified pool ≈ 63 of 100.)
- **Momentum:** 6-month return skipping the most recent 1 month — window `t−7mo →
  t−1mo` (standard 12-1-style, 6m variant).
- **Construction:** rank the qualified pool by momentum, take **top-15,
  equal-weight, monthly** rebalance. (median & min selected = 15.)
- **Costs:** turnover-based, 10 bps per unit one-way turnover (a full 15-name
  swap = turnover 2.0 = 20 bps).
- **Baselines:** (a) equal-weight the full ~100 universe, monthly; (b) buy-hold SPY.

---

## 3. Results — full period + ★walk-forward (in-sample 60% / out-of-sample 40%)

Window 2017-02 .. 2026-07. In-sample = first 68 mo (…2022-09); OOS = last 46 mo
(2022-10…2026-07).

| Series | Segment | CAGR | Sharpe | MaxDD |
|---|---|---:|---:|---:|
| **STRATEGY** | full | **26.53%** | **1.36** | −19.2% |
|  | in-sample | 26.75% | 1.30 | −19.2% |
|  | **out-of-sample** | **26.87%** | **1.45** | −9.7% |
| EqualWeight (full univ.) | full | 21.44% | 1.14 | −22.4% |
|  | in-sample | 20.02% | 0.97 | −22.4% |
|  | **out-of-sample** | **24.20%** | **1.54** | −9.1% |
| SPY (buy-hold) | full | 17.08% | 0.98 | −25.5% |
|  | in-sample | 12.56% | 0.70 | −25.5% |
|  | out-of-sample | 24.77% | 1.60 | −8.7% |

---

## 4. ★Overfitting assessment

**Is the Sharpe plausible?** Yes — 1.30–1.45 for a concentrated 15-name US
momentum book in a strong 2017–2026 megacap bull is believable, **not** an
implausible over-fit signature (we'd have been suspicious of a >2.5). The EW and
SPY baselines (Sharpe ~1.0–1.6) also sit in a sane range, which is a good sign
the plumbing is honest. Earlier degenerate runs (EW "CAGR" of 56–820% from the
pre-2017 data glitches) were caught and fixed — that debugging is itself evidence
the pipeline is now behaving.

**Is the OOS edge real or in-sample-only?**
- **vs SPY:** the strategy beats SPY in every segment on both CAGR and Sharpe.
  But most of that gap is the **equal-weight / de-mega-cap tilt**, not the
  selection — EW alone already beats SPY by a similar margin.
- **vs the RIGHT baseline (equal-weight of the same universe):** the strategy
  beats EW on CAGR in-sample (26.75 vs 20.02) and marginally OOS (26.87 vs
  24.20, **+2.7 pts**). **But risk-adjusted, the OOS edge disappears:** strategy
  OOS Sharpe **1.45 < EW 1.54.** The extra return comes with extra concentration
  risk, and on a Sharpe basis the top-15 selection does **not** beat simply
  owning the whole universe out of sample.

**Survivorship bias (the A-share failure mode):** the 100 names are *today's*
S&P-100 survivors — an upward bias inflating **both** the strategy and the EW
baseline. The strategy-vs-EW comparison partially controls for it (shared
universe), which is exactly why the thin/negative OOS Sharpe delta vs EW is the
number that matters — and it is not convincing.

**Regime caveat:** the clean window is one ~9.5y bull-dominated regime (free-data
limit). No 2000/2008-style stress is in-sample. Edge robustness across regimes is
untested.

---

## 5. Verdict — **INCONCLUSIVE** (do NOT green-light the full P1 on this basis)

The strategy clearly beats **SPY**, but that is almost entirely the equal-weight
tilt, not the momentum+quality *selection*. Against the honest benchmark —
**equal-weight of the same 100 names** — the selection adds a few CAGR points
in-sample and a marginal amount OOS, **but its out-of-sample Sharpe is below
equal-weight's.** So the concentrated selection buys extra return with extra risk
and no risk-adjusted OOS advantage over just owning the universe.

Combined with (a) the **survivorship-biased** universe, (b) a **single
bull-regime** clean window forced by free-data quality, and (c) the **A-share
sibling's OOS-negative result (B070)**, the evidence does not support committing
to the full 4-feature P1 attack build. This is a weak/ambiguous edge, not a GO.

**If pursued despite this**, the pre-conditions would be: a paid survivorship-free
US price+fundamentals vendor (extend the window pre-2017 and include delisted
names), and a re-test that must show a **Sharpe** edge over equal-weight that
holds **out-of-sample** — not just a CAGR edge.

---

## Files

- `scripts/research/b092_us_universe_fetch.py` — 100-name universe + qfq prices (akshare) + SEC EDGAR PIT annual fundamentals → `data/research/b092_us/` (gitignored)
- `scripts/research/b092_us_attack_backtest.py` — momentum+quality top-15 backtest + walk-forward vs EW & SPY
- `tests/unit/test_b092_us_attack.py` — 18 deterministic unit tests (momentum window, no-look-ahead, top-15, equal-weight, monthly dates, PIT quality gate, spike/return guards, SEC extractor)
- `docs/test-reports/B092-us-attack-first-look.md` — this report

**Gates:** `ruff check` on all three scripts → clean; `pytest tests/unit/test_b092_us_attack.py` → 18 passed. No git commit; no production/Master/data_root touched.
