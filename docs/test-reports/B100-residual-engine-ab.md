# B100 — residual-momentum ENGINE A/B (frozen cn_attack construction)
Runs the **frozen** cn_attack engine construction (`build_cn_portfolio`: rank → top-N → equal-weight → cap) TWICE on the B070 survivorship-free PIT adj_close panel, differing **only** in the momentum input — BASELINE = raw momentum (what cn_attack uses), VARIANT = B085 residual momentum. Same universe / rebalance dates / skip-window / `top_n` / cap / equal-capital / cost model both arms.
- Window: 2019-04-30 → 2026-06-18 (rebalanced monthly; signals warmed on the full panel incl. 2018)
- Universe: 1310 panel columns, eligible = names with a valid price at each rebalance date (research scope — the B070 panel's large/liquid tilt is inherited, same honest caveat as B085)
- Engine params: pure_momentum + equal weight, top_n=25, hash `e526fb4948e4…`
- Cost model (BOTH arms identical): commission 2.5bp + slippage 5.0bp (two-side) + stamp 5.0bp (sell)

## Full-period headline
| metric | BASELINE (raw) | VARIANT (residual) | Δ (variant − baseline) |
|---|---|---|---|
| CAGR | 17.2% | 15.9% | -1.3% |
| Sharpe | 0.64 | 0.608 | -0.032 |
| MaxDD | -62.1% | -61.1% | 1.0% |
| ending (×start) | 3.1007 | 2.8586 | — |
| ann. turnover | 10.61 | 10.73 | +0.12 |
| total cost (frac) | 0.1551 | 0.1548 | — |
| rebalances | 87 | 87 | — |

## Year-by-year total return (★no annual-aggregation masking)
| year | BASELINE | VARIANT | Δ |
|---|---|---|---|
| 2019 | 22.8% | 16.9% | -5.9% |
| 2020 | 49.0% | 59.8% | 10.8% |
| 2021 | 46.0% | 39.6% | -6.5% |
| 2022 | -23.0% | -22.5% | 0.6% |
| 2023 | -18.3% | -17.5% | 0.8% |
| 2024 | 6.2% | 6.9% | 0.7% |
| 2025 | 36.4% | 33.3% | -3.1% |
| 2026 | 22.6% | 12.7% | -9.8% |

## Worst sub-windows (★B084 whipsaw check)
| rolling window | BASELINE worst | VARIANT worst |
|---|---|---|
| 1-month | -28.6% | -28.4% |
| quarter | -33.3% | -34.2% |
| half-year | -43.1% | -44.4% |

## Verdict
**INCONCLUSIVE.** Residual momentum does NOT materially beat (in fact marginally trails) raw momentum in the frozen engine, net of turnover (Δ CAGR -1.3%, Δ Sharpe -0.032, identical turnover), and it does not hide a worse sub-window loss.

**Honest frame (per B085):** the residual edge was already marginal in the IC pre-screen (residual IC 0.0108 t=0.45; residual-minus-raw +0.0118 t=1.98 borderline), so an INCONCLUSIVE engine result is the *expected, valid* outcome — like B083/B084. This is research-only: the cn_attack flagship stays frozen (OOS red-card), and **whether to adopt residual into it is the user's decision**, not this batch's. GO here would require a real, robust improvement; a small / whipsaw-prone / turnover-eaten delta = INCONCLUSIVE (valid).

> research-only / advisory-only. No cn_attack product code modified (`build_cn_portfolio` imported read-only); no data_root written; nothing marked validated.
