# A-share Multiscale Price-Volume Trend First-look Audit (2026-07-11)

> **Formal verdict: `DATA_NO_GO`; degraded proxy verdict: `PROXY_SIGNAL_NO_GO`.**
>
> Boundary: research-only / advisory-only / no broker / no real money. This is a
> user-directed independent study and does not change any production strategy or Harness state.

## 1. Decision summary

1. **The planned residual-momentum direction was stopped before retesting.** Repository memory
   marks B085/B100 residual momentum as a completed negative trial: its full engine trailed raw
   momentum by 1.33 percentage points of CAGR and 0.032 Sharpe. Repeating it would violate the
   Strategy Scout no-repeat rule. The replacement candidate is the previously untested
   Liu-Zhou-Zhu multiscale price-volume trend measure.
2. **The exact paper input is absent.** The paper uses daily RMB traded value. B070 stores qfq
   OHLC and share volume, not actual traded amount. The preregistered primary proxy is
   `qfq close * share volume`, with share volume alone as a fixed sensitivity. This is useful as a
   degraded screen but cannot validate or reject the published factor itself.
3. **The degraded signal also fails.** Primary N20 monthly rank-IC is **+0.0153**, HAC t=0.97,
   with a six-month block-bootstrap 95% interval **[-0.0162,+0.0455]**. Only the first of three
   time folds is positive. N60 IC is +0.0160, t=0.93, with an interval crossing zero.
4. **There is no usable long-only top leg.** At N20, the highest trend quintile trails the equal-
   weighted PIT universe by **5.72bp per month**; at N60 it trails by **36.93bp per holding
   period**. N20 quintiles are non-monotonic and N60 is negatively ordered. Therefore a paper
   long-short spread cannot be presented as a portfolio that an A-share cash account can buy.
5. **Stop before the CNY 1 million portfolio stage.** Both the exact-data gate and the proxy
   signal gate fail. No Top-25 construction, cost simulation, lot-size calculation, or parameter
   tuning is authorized by this result.

## 2. Frozen hypothesis and construction

The primary hypothesis was frozen before the real-data run:

> In the current B070 PIT investable cross-section, the published multiscale price-volume trend
> score should positively rank returns from the first tradeable open after month-end through N20,
> remain positive at N60, beat classic 12-1 momentum on paired monthly IC, and produce a positive
> highest-quintile excess return in a long-only implementation.

The signal follows Liu, Zhou, and Zhu's published construction:

```text
price_feature(L,t)  = mean(adjusted_close over L sessions) / close_t
volume_feature(L,t) = mean(RMB traded value over L sessions) / traded_value_t
L = 3, 5, 10, 20, 50, 100, 200, 300, 400

return(i,t) = intercept + sum(beta_price(t) * price_feature(i,t-1))
                        + sum(beta_volume(t) * volume_feature(i,t-1))

expected_beta(t+1) = 0.98 * expected_beta(t) + 0.02 * beta(t)
trend_score(i,t)   = features(i,t) dot expected_beta(t+1)
```

- The first 400 sessions warm the features; 38 valid coefficient months warm the EMA.
- A month-t return is regressed only on month-(t-1) features. The resulting update is applied to
  month-t features after that month's close, then traded no earlier than the next open.
- Signal-date quintiles are frozen before entry. A name that opens limit-up keeps its intended
  weight in cash and is not replaced by the next-ranked name. IC is also reported on all signal
  candidates, with an executable-only sensitivity alongside it.
- There is one frozen formula, no lag/EMA/burn-in scan, and no result-driven limit-up or February
  overlay.
- Classic 12-1 is `close[t-1] / close[t-13] - 1` on the identical PIT/event sample.
- Inference uses monthly cross-sectional Spearman IC, Newey-West lag 3, and a deterministic
  circular six-month block bootstrap with 5,000 draws.

Primary literature: Yang Liu, Guofu Zhou, and Yingzi Zhu, *Trend Factor in China: The Role of
Large Individual Trading*, Review of Asset Pricing Studies 14(2), 348-380,
[published DOI](https://doi.org/10.1093/rapstu/raae003) and
[public working paper](https://acfr.aut.ac.nz/__data/assets/pdf_file/0014/324113/Y-Liu-New-TrendChina_12_1_WithAppendix.pdf).

## 3. Data and execution reality

| Item | Result |
|---|---:|
| B070 price rows / tickers | 2,467,137 / 1,310 |
| Price window | 2018-01-02 to 2026-06-18 |
| PIT universe snapshots | 29 quarterly blocks, normally 800 names |
| Suspended rows | 16,779 |
| Valid coefficient months | 81; all OLS designs full rank 19/19 |
| Test signal window | 2022-10-31 to 2026-05-29, 44 signal months |
| PIT signal coverage | min 98.00%, P10 98.54%, median 99.38% |
| Signal rows / priced events | 34,928 / 34,925 |
| Executable after open-limit filter | 34,614 |
| N20 / N60 valid events | 34,123 / 32,525 |

Execution labels use the first later `tradestatus=1` open and roll a suspended target exit forward
to the first tradeable close. N1 uses the earliest legally sellable T+1 close. N20 had 32 delayed
exits (maximum 14 sessions); N60 had 25
(maximum 13). Missing N20 labels are 796 right-censored and 6 path-ended/missing; N60 is
2,385 right-censored and 15 path-ended/missing.

The entry-limit screen flagged 311 unfillable events. Primary IC retains these candidates; the
executable-only IC sensitivity excludes them, while frozen long-only quintiles leave their intended
weights in cash. Of the 311, **268 follow the 2024-09-30 signal** and enter after the National Day
holiday/rally. This is an economically real executability event, not a sample-cleaning accident.
Historical ST flags and exact exchange limit prices are unavailable, so the normal-board 10%/20%
filter remains an incomplete approximation.

## 4. Signal results

### 4.1 Primary proxy and raw baseline

| Signal / horizon | Months | mean IC | HAC t | block-bootstrap 95% CI | Q5-Q1 | Q5 - universe | monotonicity |
|---|---:|---:|---:|---:|---:|---:|---:|
| **PV trend N20** | **43** | **+0.0153** | **0.97** | **[-0.0162,+0.0455]** | +0.1294% | **-0.0572%** | +0.10 |
| PV trend N60 | 41 | +0.0160 | 0.92 | [-0.0176,+0.0477] | -0.2802% | **-0.3693%** | -0.60 |
| raw 12-1 N20 | 43 | +0.0017 | 0.05 | [-0.0560,+0.0734] | +0.2073% | -0.1256% | +0.30 |
| raw 12-1 N60 | 41 | +0.0410 | 1.03 | [-0.0251,+0.1257] | +2.0414% | +0.5426% | +0.90 |

PV trend N20 fold means are **+0.0536 / -0.0053 / -0.0050**. By year they are +0.0695
(late 2022), +0.0496 (2023), -0.0109 (2024), -0.0023 (2025), and +0.0037 (through
April 2026). The positive result is concentrated at the start of the already short test window and
does not persist.

PV trend improves paired N20 IC over raw momentum by +0.0136, but the comparison has
t=0.41 and a 95% interval of **[-0.0616,+0.0802]**. The three paired folds are
+0.0613 / -0.0511 / +0.0272. Passing a point-estimate threshold while failing its uncertainty
and stability gates is not evidence of an upgrade.

The earliest legally sellable T+1 close has a positive IC of +0.0535 (t=2.73, bootstrap interval
[+0.0090,+0.0936]), but its Q5 excess interval still crosses zero and the effect collapses by N20.
Turning that control into a two-day high-turnover strategy after seeing the result would be a new,
post hoc trial with a different execution/cost problem. It is not evidence for the frozen monthly
holding hypothesis.

Using all signal candidates gives the primary N20 IC of +0.0153; dropping next-open limit-up
events gives +0.0157. The small difference confirms that the execution filter does not create the
NO-GO. Under the separate worst-case assumption that the 6 N20 and 15 N60 path-ended/missing
labels lose 100%, N20 IC is +0.0152 (t=0.96) and N60 IC is +0.0160 (t=0.92). The verdict is
unchanged rather than relying on silent delist deletion.

### 4.2 Price/volume attribution and fixed sensitivity

| Diagnostic / N20 | mean IC | HAC t | 95% CI | Q5 - universe | fold means |
|---|---:|---:|---:|---:|---:|
| Joint-model price contribution | +0.0077 | 0.45 | [-0.0262,+0.0422] | +0.1024% | +0.0521/-0.0211/-0.0110 |
| Joint-model amount-proxy contribution | +0.0267 | 1.27 | [-0.0113,+0.0606] | -0.1226% | +0.0289/+0.0499/+0.0011 |
| Share-volume PV sensitivity | +0.0111 | 0.73 | [-0.0197,+0.0405] | -0.2271% | +0.0482/-0.0094/-0.0082 |

The amount-proxy contribution has an interesting N60 IC of +0.0515 (t=2.19, bootstrap interval
[+0.0104,+0.0907]), but this is not a tradable long-only result: its highest quintile still trails
the universe by 17.05bp and the five quintiles have only +0.10 monotonicity. The joint signal and
the exact preregistered N20 target both fail. Promoting this post hoc N60 component would be a new
trial and would rely most heavily on the missing exact RMB-amount field.

## 5. Exposure diagnostics

- PIT circulating market-cap coverage is 100%. Top/bottom trend deciles have similar median
  market cap (about CNY 28.9bn / CNY 31.8bn), so the failure is not a simple small-cap tilt.
- Liquidity and volatility are U-shaped across signal deciles. Median amount proxy is about
  CNY 361m in the highest decile versus CNY 225m-271m in middle deciles; annualized recent
  volatility is 38.8% in the top decile versus about 29.5% in the middle.
- The highest decile's median preceding-20-session return is +1.64%, versus negative values in
  most middle deciles. The signal therefore retains a recent-price/trading-intensity exposure, but
  that exposure does not convert into a stable forward top-leg premium.
- Historical PIT industry labels do not exist. No industry-neutrality claim is made.

## 6. Gates

| Gate | Result |
|---|---|
| PIT snapshots, 38-month coefficient warmup, feature coverage | PASS |
| N20 and N60 each at least 36 valid months | PASS (43 / 41) |
| Exact daily RMB traded value available | **FAIL** |
| N20 mean IC >= +0.03 and HAC t >= 2 | **FAIL (+0.0153 / 0.97)** |
| N20 bootstrap lower bound > 0 | **FAIL** |
| N20 at least 2/3 folds positive | **FAIL (1/3)** |
| N20 positive, monotonic Q5-Q1 | **FAIL (non-monotonic)** |
| Long-only Q5 excess bootstrap lower bound > 0 | **FAIL (point estimate negative)** |
| Paired improvement over raw >= +0.01 | PASS point estimate only |
| Paired-improvement bootstrap lower bound > 0 | **FAIL** |
| N60 same positive IC sign | PASS, but statistically weak and top leg negative |
| Share-volume sensitivity same positive IC sign | PASS, but weak and top leg negative |

Final machine state: `data_pass=false`, `signal_pass=false`,
`million_cny_portfolio_backtest_allowed=false`.

## 7. Findings

### PVT-001 - HIGH - Exact paper volume input and portfolio execution fields are absent

- **Finding:** B070 lacks daily RMB traded amount, unadjusted nominal OHLC for lot sizing, exact
  historical limit prices, and ST state.
- **Evidence:** B070 schema is qfq OHLC, share volume, and trade status. The primary amount value
  is explicitly a proxy. Qfq prices cannot determine whether CNY 1 million can buy 100-share lots.
- **Required action:** A future exact replication must acquire daily `amount`, unadjusted OHLC,
  historical board/ST metadata, and preserve PIT/delist coverage before any capital simulation.

### PVT-002 - HIGH - The proxy signal does not produce a long-only alpha

- **Finding:** N20 is statistically weak and unstable; N20/N60 highest quintiles do not beat the
  investable universe.
- **Evidence:** N20 IC +0.0153, t=0.97, CI crosses zero, 1/3 positive folds; Q5-universe -5.72bp.
  N60 Q5-universe is -36.93bp.
- **Required action:** Stop this proxy after first-look. Do not tune EMA, lags, quintile cutoffs,
  February rules, or limit-up definitions against the observed sample.

### PVT-003 - MEDIUM - Published 1.43% cannot be mapped to this account

- **Finding:** The paper's headline is a value-weighted long-short factor after Size x EP x Trend
  triple sorts and exclusion of the smallest 30%; it is not a buyable long-only return forecast.
- **Evidence:** The current test uses a liquid PIT 800 subset, no reliable PIT EP/industry labels,
  equal-weight IC/quintiles, and no short leg.
- **Required action:** Keep the external result as theoretical prior only. Judge this project on its
  own long-only top-leg evidence.

### PVT-004 - MEDIUM - Post-warmup test history is short

- **Finding:** A 2018 data start plus 400 sessions and 38 coefficient months leaves only 44 signal
  months, beginning October 2022.
- **Evidence:** N20/N60 have 43/41 valid months; the first fold is positive and the later two N20
  folds are negative.
- **Required action:** No positive result from this window could receive a definitive GO without
  older exact amount data and genuinely untouched forward evidence. The current negative decision
  remains appropriate.

### PVT-005 - MEDIUM - Historical industry neutrality is untestable

- **Finding:** The available PIT universe has membership but no historical industry labels.
- **Evidence:** Market-cap/liquidity/volatility exposures are measured; industry exposure is not.
- **Required action:** Do not describe the signal as industry-neutral. Acquire PIT industry history
  before any future positive candidate advances.

### PVT-006 - LOW - Limit-up inference is approximate

- **Finding:** The 10%/20% open-gap screen uses qfq prices and has no historical ST 5% state.
- **Evidence:** It identifies the economically plausible 2024-10 reopening limit-up cluster, but
  cannot reproduce official daily limit prices exactly.
- **Required action:** Replace inferred bands with official historical limit-price/status fields if an
  exact-data rerun is ever justified.

## 8. Decision and next direction

1. Do not create a multiscale PV-trend portfolio and do not modify `cn_attack`.
2. Do not return to residual momentum; B085/B100 already closed that route.
3. Exact RMB amount acquisition is technically possible, but the proxy's weak N20 result and
   negative long-only top leg lower its expected research value. It is a data-foundation option,
   not the recommended immediate next alpha test.
4. The next research round should prefer an already implementable long-only hypothesis with an
   unambiguous payoff. The strongest surviving repository candidate is a strict follow-up of the
   B084 A-share ETF time-series trend `INCONCLUSIVE/LEAN-GO`, using adjusted ETF prices, more
   broad/sector ETFs, multiple frozen OOS windows, turnover, and realistic ETF costs. This is more
   promising than opening another individual-stock momentum variant.

## 9. Reproduction

- Runner: `scripts/test/ashare_multiscale_pv_trend_first_look.py`
- Structured result: `docs/test-reports/ashare-multiscale-pv-trend-first-look-2026-07-11.json`
- Tests: `tests/unit/test_ashare_multiscale_pv_trend_first_look.py`
- Local data inputs are gitignored research caches; the JSON records their SHA256 hashes.

```bash
.venv/bin/python scripts/test/ashare_multiscale_pv_trend_first_look.py
.venv/bin/python -m pytest tests/unit/test_ashare_multiscale_pv_trend_first_look.py -q
.venv/bin/python -m ruff check .
```

The 14-test unit suite locks PIT membership, strict as-of feature construction, the online OLS/EMA
timeline, 12-1 anchors, suspension-aware entry/exit, historical ChiNext limit bands, deterministic
bootstrap, frozen pre-entry quintiles/cash handling, constant-signal IC filtering, the exact-amount
hard gate, and JSON non-finite handling.
