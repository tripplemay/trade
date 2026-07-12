# A-share ETF Trend Strict Follow-up Audit (2026-07-12)

> **Formal verdict: `DATA_NO_GO`. Executable diagnostic verdict: `NO_GO`.**
>
> The registered B084 candidate is not promoted to paper or production. The corrected
> fixed-sleeve strategy gives up material return for a small, unstable risk-adjusted
> improvement, while the five-ETF common sample and historical capacity gates fail.

## 1. Decision summary

This round **modifies and strictly retests B084**. It does not introduce a new moving
average, dual-momentum, or parameter-selected strategy.

The old B084 headline is not valid evidence for adoption:

- raw `510500` contains a `+316.4%` monthly move in April 2015, versus `+17.4%` on the
  adjusted series;
- raw `512890` contains a `-54.5%` monthly move in October 2021, versus `-8.9%`
  adjusted;
- the old implementation generated a signal at the month-end close and began its
  return at that same close;
- it renormalized all positive signals to 100% invested, although the stated rule said
  a failed sleeve should go to cash.

After correcting those issues, the primary 2.1 million CNY diagnostic is:

| Metric | Fixed-sleeve trend | Fixed-sleeve hold | Trend minus hold |
|---|---:|---:|---:|
| Net CAGR | 6.93% | 9.03% | **-2.10pp** |
| Monthly Sharpe | 0.555 | 0.506 | +0.050 |
| Daily-path MaxDD | -37.60% | -40.63% | +3.03pp |
| Ending NAV | CNY 5.190m | CNY 6.748m | **-CNY 1.558m** |
| Annual turnover | 1.095x | 0.358x | +0.738x |
| Total trading cost | CNY 35,156 | CNY 14,207 | +CNY 20,949 |

The user preference is return-first. A 2.10pp annual return sacrifice for only 0.05
Sharpe improvement does not meet that objective.

## 2. Frozen hypothesis and theory

The sole signal remains the B084 prior:

```text
at complete month-end t:
    momentum_i = adjusted_close_i,t / adjusted_close_i,t-12m - 1
    target_weight_i = 20% if momentum_i > 0 else 0%
    unused sleeve = cash
execute at the next common trading-session open
```

The five frozen sleeves are `159915`, `510300`, `510500`, `512890`, and `588000`.
No lookback, threshold, ETF, fold boundary, or whipsaw exception was selected from the
corrected result.

The fixed-slot interpretation is supported by Faber's tactical allocation model: each
asset class is independently either held at its equal sleeve weight or its allocation
is kept in cash. The original 12-month sign follows the time-series momentum structure
of Moskowitz, Ooi, and Pedersen. Neither source supports magnifying one remaining
positive ETF from 20% to 100% merely because the other sleeves are negative.

Primary references:

- Faber, *A Quantitative Approach to Tactical Asset Allocation*,
  [public paper](https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf).
- Moskowitz, Ooi, and Pedersen, *Time Series Momentum*,
  [DOI](https://doi.org/10.1016/j.jfineco.2011.11.003),
  [public paper](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf).
- Shi and Zhou, *Time series momentum and contrarian effects in the Chinese stock
  market*, [DOI](https://doi.org/10.1016/j.physa.2017.04.139). Their China-index
  evidence is weaker and window-dependent, so it does not justify a window sweep.
- Zhu et al., *Profitability of simple technical trading rules of Chinese stock
  exchange indexes*, [DOI](https://doi.org/10.1016/j.physa.2015.07.032). Their White
  Reality Check evidence warns that technical-rule excess can disappear after costs.
- Sherrill and Stark, *ETF Liquidation Determinants*,
  [DOI](https://doi.org/10.1016/j.jempfin.2018.07.007). ETF termination is non-random,
  so a current-survivor universe is not a PIT market universe.

This literature supports a cautious fixed-sleeve test. It does **not** establish that
the long/cash adaptation earns a robust A-share ETF premium.

## 3. Data and execution protocol

### 3.1 Adjusted return and nominal execution layers

- Signal and return layer: Tencent daily qfq OHLC, frozen through `2026-07-10`.
- Nominal execution layer: the B084 Sina raw close supplies the raw/qfq scale; nominal
  open is reconstructed as `qfq_open * raw_close / qfq_close` on the same day.
- Exact traded amount: Tencent row 8, whose unit is ten-thousand CNY, is retained before
  the current AkShare wrapper truncates the row.
- Amount cross-check: 1,805 overlapping `512890` observations have 0.999986 correlation
  with `raw close * share volume`; median absolute relative difference is 0.251% and
  P95 is 1.014%.
- All five primary files pass uniqueness, positive-price, OHLC, missing-value, and
  adjusted-discontinuity checks. Evaluation-window nominal-open coverage is 100%.

### 3.2 Trading model

- Signal after the final complete trading close of each month.
- Entry at the next common trading-session open; holding return ends at the next entry
  open. The terminal partial month is excluded.
- Five fixed 20% sleeves. Negative, unavailable, missing, or locked-buy sleeves remain
  cash and are not redistributed.
- Starting capital CNY 2,100,000; target holdings are rounded to nominal-open
  100-share lots; minimum commission is CNY 5.
- Base friction: 2.5bp commission plus 5bp slippage on each traded notional; ETF stamp
  duty is zero. Market ETF returns already contain fund fees, so no fee is double-counted.
- Directional locked-limit checks use adjusted OHLC; no locked primary trades occurred.
- MaxDD uses 3,046 trend and 3,435 hold daily/open path observations, not month-end NAV
  alone.

The lot model is an explicit approximation, not a full share ledger. Existing holdings
carry between rebalances as adjusted total-return notionals, then the next target is
rounded to a 100-share nominal-price lot. Consequently some inferred trade differences
are not exact 100-share multiples. The error is below one lot per target and cannot
explain a 2.10pp CAGR deficit or a 55.88% participation maximum, but cost and capacity
figures must be read as target-lot diagnostics rather than exact broker fills.

This is still research-only. No broker, paper account, product strategy, or production
configuration was touched.

## 4. Data gates

| Gate | Result | Evidence |
|---|---|---|
| Primary qfq/OHLC/amount integrity | PASS | All five normalized files pass |
| Nominal execution coverage | PASS | 100% through the evaluation endpoint |
| Five-sleeve common history >= 60 months | **FAIL** | **55 months**, 2021-11 to 2026-05 |
| Historical PIT ETF master incl. liquidations | **FAIL** | Repository has current survivors only |
| Expanded representative data integrity | **FAIL** | `510050/510880` old qfq histories contain nonpositive/extreme values |

Therefore the formal result is `DATA_NO_GO`. The executable fixed-sleeve diagnostic is
still useful as negative evidence, but a positive result would have been capped at
paper-only because all B084 dates were previously inspected (`C2-DIRECT`).

## 5. Primary results

### 5.1 Return and statistical evidence

- 162 evaluated signal months, `2012-12-31` through `2026-05-29`.
- Trend CAGR is 6.93% versus 9.03% hold; the annualized paired arithmetic excess is
  **-3.06%**.
- Paired HAC t-statistic is **-0.864**.
- Six-month moving-block 95% CI for annualized mean excess is
  **[-10.24%, +2.72%]**.
- Trend beats hold in only 45.1% of paired months.

The result is not merely statistically inconclusive: its point estimate is adverse to
the return objective.

### 5.2 Frozen time folds

| Fold | Trend minus hold CAGR | Trend minus hold Sharpe |
|---|---:|---:|
| 2013-2016 | -4.42pp | -0.202 |
| 2017-2020 | -0.75pp | +0.117 |
| 2021-2023 | +5.21pp | +0.222 |
| 2024-2026 | **-11.78pp** | +0.045 |

Only one of four folds has positive CAGR delta. The old late-sample strength is a
regime-specific defense result, not stable return enhancement.

### 5.3 Whipsaw windows

| Frozen window | Trend | Hold | Trend minus hold |
|---|---:|---:|---:|
| 2022-01 through 2022-04 | -8.61% | -21.74% | +13.13pp |
| 2024-01 through 2024-02 | +1.89% | +0.39% | +1.50pp |

These windows are attributed by actual entry month, not signal month. The rule passes
the pre-registered whipsaw tolerance in both windows, confirming a real defensive
mechanism. That local defense does not offset its full-period return deficit.

### 5.4 Historical capacity

- All-history trade-level participation pass rate at <=1% is 94.57%, below the 95% gate.
- P95 participation is 1.31%; maximum is 55.88%.
- The maximum is a CNY 68,532 `512890` trade on `2021-01-04` against trailing-20-day
  median amount of only CNY 122,650.
- From 2024 onward, pass rate is 100% and maximum participation is 0.0644%.

Current liquidity is sufficient, but it cannot be projected backward. A constant 5bp
slippage model is not credible when the historical order exceeds half of median daily
amount.

## 6. Decision gates

| Gate | Threshold | Observed | Result |
|---|---:|---:|---|
| Net CAGR delta | >= +2.0pp | -2.10pp | FAIL |
| Net Sharpe delta | >= +0.15 | +0.050 | FAIL |
| Daily MaxDD delta | >= 0 | +3.03pp | PASS |
| Paired HAC t | >= 1.65 | -0.864 | FAIL |
| Block-bootstrap mean lower bound | > 0 | -10.24% annualized | FAIL |
| Positive CAGR folds | >= 3/4 | 1/4 | FAIL |
| Worst frozen whipsaw delta | >= -5pp | +1.50pp | PASS |
| Participation pass rate | >= 95% | 94.57% | FAIL |
| Maximum participation | <= 1% | 55.88% | FAIL |

Only the MaxDD and whipsaw gates pass. The diagnostic signal verdict is `NO_GO`
independently of the 55-month data insufficiency.

## 7. Sensitivities

### 7.1 Higher trading friction

| Variable friction per traded notional | Trend CAGR | Hold CAGR | Trend minus hold |
|---|---:|---:|---:|
| 7.5bp base | 6.93% | 9.03% | -2.10pp |
| 10bp | 6.90% | 9.02% | -2.12pp |
| 25bp | 6.73% | 8.96% | -2.23pp |

The trend sleeve has more turnover, so realistic cost pressure weakens it further.

### 7.2 Five-sleeve common-history window

On the only period in which all five ETFs already had 12-month histories (55 months),
trend CAGR is 5.96% versus 7.67% hold. Trend Sharpe is higher (0.474 versus 0.378) and
daily MaxDD is shallower (-26.25% versus -35.68%), but the return objective still fails
and uncertainty is wide (paired HAC t `-0.461`).

### 7.3 Old positive-signal full-investment rule

The legacy rule is not rescued by corrected data:

- trend CAGR 11.97% versus 13.39% hold;
- Sharpe 0.601 versus 0.591;
- daily MaxDD **-66.17%**, worse than hold at -60.32%;
- annual turnover 3.33x and cost CNY 146,112.

It is an additional concentration strategy, not a harmless implementation variant.

### 7.4 Three long-history broad ETFs

The pre-result data sensitivity `159915/510300/510500` also fails: trend CAGR 7.80%
versus 10.95%, Sharpe 0.479 versus 0.504. Promoting it after seeing the five-sleeve
result would be a new universe hypothesis and is not allowed in this round.

### 7.5 Expanded current-survivor basket

The expanded basket is `DATA_NO_GO`. Long qfq histories for `510050` and `510880`
contain nonpositive and extreme adjusted values. Per the frozen data gate, no expanded
return result is reported or used.

## 8. Findings

### F1 - High - B084 raw-price headline is invalid for strategy selection

The raw series contains material fund-unit adjustment events. The old 17.9% CAGR and
related Sharpe/MaxDD figures cannot be compared with total-return results or used as a
GO premise.

### F2 - High - B084 code and stated allocation were different strategies

Renormalizing one positive ETF to 100% creates up to fivefold conditional
concentration. Fixed-slot and legacy-normalized corrected tests both fail, but future
research must not choose between them after seeing results.

### F3 - High - Corrected strategy fails the return-first objective

Net CAGR is 2.10pp below hold, paired excess is negative, and only one of four folds is
positive. Risk reduction is real but too small and unstable to offset return loss.

### F4 - Medium - Historical capacity invalidates constant-slippage claims

Early `512890` trades exceed the 1% participation ceiling. Today's liquidity does not
make the historical backtest executable at fixed 5bp slippage.

### F5 - Medium - No untouched validation or PIT ETF universe exists

All B084 dates were previously examined, five-sleeve common history is only 55 months,
and the repository lacks terminated ETFs. A future positive result would require
prospective paper evidence, not another retrospective split.

### F6 - Low - Lot handling is a target-lot approximation

The runner rounds each new target to 100 shares but does not maintain an integer share
ledger through distributions and fund-unit adjustments. This is adequate negative
evidence here, not execution certification. A future positive candidate would require
raw share balances plus explicit distribution/corporate-action cash flows.

## 9. Decision and next direction

1. Close the B084 12-month ETF trend route as **`DATA_NO_GO + diagnostic NO_GO`**.
2. Do not scan alternative momentum windows, MA lengths, thresholds, Top-N counts,
   February exceptions, ETF deletions, or cash proxies to rescue it.
3. Do not build a production mode or allocate the CNY 2.1m account to this candidate.
4. Retain the corrected runner as a permanent guard against raw-price, same-close, and
   conditional-concentration errors.
5. Reconsideration would require a genuinely new dataset: PIT ETF master including
   liquidations, clean total-return OHLC, and prospective evidence. Given the adverse
   return point estimate, that acquisition is not a current research priority.

## 10. Reproduction

```bash
.venv/bin/python -m pytest tests/unit/test_ashare_etf_trend_strict_followup.py -q
.venv/bin/python scripts/test/ashare_etf_trend_strict_followup.py
```

Artifacts:

- runner: `scripts/test/ashare_etf_trend_strict_followup.py`
- unit tests: `tests/unit/test_ashare_etf_trend_strict_followup.py`
- structured result: `docs/test-reports/ashare-etf-trend-strict-followup-2026-07-12.json`

The JSON records the runner hash, frozen data hashes, exact gate values, period returns,
cost stresses, and all sensitivity diagnostics.
