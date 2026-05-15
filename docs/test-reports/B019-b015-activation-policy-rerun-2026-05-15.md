# B019-b015-activation-policy-rerun-2026-05-15

## Summary
- Batch: B015
- Report date: 2026-05-15
- Description: Comparative backtest of B013 regime-adaptive strategy under three regime_activation_policy values: always_on (baseline), only_non_normal, only_crisis. B013 strategy code is unchanged; only the activation policy config knob varies between rows.

## Real-Data Status
- Status: skipped
- Reason: B014 yfinance manifest not found at data/public-cache/regime-adaptive-prices-manifest.json; ran on a synthetic 9-asset fixture as a smoke check only. Re-run after `scripts/fetch_yfinance_regime_adaptive_csvs.py` populates the manifest to obtain real-data findings.

## Per-Policy Metrics (B013 regime-adaptive)
| policy | annualized_return | annualized_volatility | sharpe | max_drawdown | turnover | L1 firing rate | ending_value |
|---|---|---|---|---|---|---|---|
| always_on | 0.300717 | 0.034186 | 8.796472 | -0.000300 | 3.000000 | 1.000000 | 169186.50 |
| only_non_normal | 0.300717 | 0.034186 | 8.796472 | -0.000300 | 3.000000 | 0.125000 | 169186.50 |
| only_crisis | 0.370253 | 0.020516 | 18.047186 | 0.000000 | 1.022210 | 0.000000 | 187759.34 |

## Stress Window Verdict Per Policy
| policy | 2020_q1_q4 status / max_dd | 2022_full_year status / max_dd |
|---|---|---|
| always_on | skipped / 0.000000 | pass / -0.000300 |
| only_non_normal | skipped / 0.000000 | pass / -0.000300 |
| only_crisis | skipped / 0.000000 | pass / 0.000000 |

## Cross-Strategy Baselines (reused from B014 sidecar where available)
- global_etf_momentum: ending_value=100963.18779949828, max_drawdown=-0.030626564701251136
- risk_parity: ending_value=103869.16382166126, max_drawdown=-0.008360811544914304
- static_60_40: ending_value=158978.38353347202, max_drawdown=-0.19663574281239315

## Narrative — Activation Policy vs 60/40 Absolute-Return Gap
- Status: real_data_skipped
- Note: Real B014 yfinance snapshot was not present; only the in-memory comparison ran. Re-run with the snapshot manifest available to populate the real-data narrative.

## Research Limitations
- research-only B015 activation-policy comparison; never authorizes paper or production order flow.
- no_paper_or_production_order_flow_authorized
- fixture_or_research_snapshot_only
- stress_gates_require_real_historical_snapshot_to_meaningfully_compare
- B013 strategy code unchanged in B015; activation policy is an opt-in config knob

_Disclaimer: research-only B015 activation-policy comparison; never authorizes paper or production order flow._
