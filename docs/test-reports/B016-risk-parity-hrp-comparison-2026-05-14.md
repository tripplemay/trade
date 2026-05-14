# B016-risk-parity-hrp-comparison-2026-05-14

## Summary
- Batch: B016
- Report date: 2026-05-14
- Description: Comparative backtest of B010 risk parity under two weighting_method values: inverse_volatility (B010 default) and hrp (B016 De Prado HRP). B011/B012/B013/B014/B015 strategy code is unchanged; only RiskParityParameters.weighting_method varies.

## Real-Data Status
- Status: skipped
- Reason: B014 yfinance manifest not found at data/public-cache/regime-adaptive-prices-manifest.json; ran on a synthetic 9-asset fixture as a smoke check only. Re-run after `scripts/fetch_yfinance_regime_adaptive_csvs.py` populates the manifest to obtain real-data findings.

## Per-Method Metrics (B010 risk parity)
| method | annualized_return | annualized_volatility | sharpe | max_drawdown | turnover | rebalances | ending_value |
|---|---|---|---|---|---|---|---|
| inverse_volatility | 0.024988 | 0.010339 | 2.416838 | -0.005596 | 1.094521 | 24 | 105059.97 |
| hrp | 0.025143 | 0.010235 | 2.456626 | -0.005494 | 1.182079 | 24 | 105091.89 |

## Stress Window Verdict Per Method
| method | 2020_q1_q4 status / max_dd | 2022_full_year status / max_dd |
|---|---|---|
| inverse_volatility | skipped / 0.000000 | pass / -0.003424 |
| hrp | skipped / 0.000000 | pass / -0.003396 |

## Static 60/40 Baseline (reused from B014 sidecar when available)
- ending_value=158978.38353347202 | CAGR=0.19656782313500476 | annualized_volatility=0.3694704509063286 | Sharpe=0.6268265576820613 | max_drawdown=-0.19663574281239315

## Narrative — Does HRP shrink the gap vs static 60/40?
- Status: real_data_skipped
- Note: Narrative is only emitted when the real-data harness ran end-to-end. The synthetic-fixture branch is a schema smoke check only.

## Research Limitations
- research-only B016 risk-parity HRP comparison; never authorizes paper or production order flow.
- no_paper_or_production_order_flow_authorized
- fixture_or_research_snapshot_only
- 60_40_baseline_sourced_from_B014_sidecar_when_available
- HRP vs inverse-vol comparison is empirical research finding, not pass/fail

_Disclaimer: research-only B016 risk-parity HRP comparison; never authorizes paper or production order flow._
