# B016-risk-parity-hrp-comparison-2026-05-15

## Summary
- Batch: B016
- Report date: 2026-05-15
- Description: Comparative backtest of B010 risk parity under two weighting_method values: inverse_volatility (B010 default) and hrp (B016 De Prado HRP). B011/B012/B013/B014/B015 strategy code is unchanged; only RiskParityParameters.weighting_method varies.

## Real-Data Status
- Status: ran
- Snapshot manifest id: regime-adaptive:b69883b08eedea7d
- Snapshot date range: 2018-01-02..2025-12-31

## Per-Method Metrics (B010 risk parity)
| method | annualized_return | annualized_volatility | sharpe | max_drawdown | turnover | rebalances | ending_value |
|---|---|---|---|---|---|---|---|
| inverse_volatility | 0.014004 | 0.011876 | 1.179105 | -0.007181 | 3.100410 | 31 | 103657.79 |
| hrp | 0.012121 | 0.012146 | 0.997906 | -0.007860 | 4.376236 | 31 | 103161.35 |

## Stress Window Verdict Per Method
| method | 2020_q1_q4 status / max_dd | 2022_full_year status / max_dd |
|---|---|---|
| inverse_volatility | pass / -0.003269 | pass / -0.007181 |
| hrp | pass / -0.006024 | pass / -0.007860 |

## Static 60/40 Baseline (reused from B014 sidecar when available)
- ending_value=158978.38353347202 | CAGR=0.19656782313500476 | annualized_volatility=0.3694704509063286 | Sharpe=0.6268265576820613 | max_drawdown=-0.19663574281239315

## Narrative — Does HRP shrink the gap vs static 60/40?
- Status: real_data_ran
- inverse_volatility ending: 103657.79
- HRP ending: 103161.35
- static_60_40 ending: 158978.38
- inverse_vol gap vs 60/40: 55320.59
- HRP gap vs 60/40: 55817.03
- delta (inverse_vol_gap - hrp_gap): -496.44
- Verdict: widened
- Tolerance: $100.00

## Research Limitations
- research-only B016 risk-parity HRP comparison; never authorizes paper or production order flow.
- no_paper_or_production_order_flow_authorized
- fixture_or_research_snapshot_only
- 60_40_baseline_sourced_from_B014_sidecar_when_available
- HRP vs inverse-vol comparison is empirical research finding, not pass/fail

_Disclaimer: research-only B016 risk-parity HRP comparison; never authorizes paper or production order flow._
