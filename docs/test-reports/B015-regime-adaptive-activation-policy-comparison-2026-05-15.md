# B015-regime-adaptive-activation-policy-comparison-2026-05-15

## Summary
- Batch: B015
- Report date: 2026-05-15
- Description: Comparative backtest of B013 regime-adaptive strategy under three regime_activation_policy values: always_on (baseline), only_non_normal, only_crisis. B013 strategy code is unchanged; only the activation policy config knob varies between rows.

## Real-Data Status
- Status: ran
- Snapshot manifest id: regime-adaptive:b69883b08eedea7d
- Snapshot date range: {'start': '2018-01-02', 'end': '2025-12-31'}

## Per-Policy Metrics (B013 regime-adaptive)
| policy | annualized_return | annualized_volatility | sharpe | max_drawdown | turnover | L1 firing rate | ending_value |
|---|---|---|---|---|---|---|---|
| always_on | 0.096022 | 0.150636 | 0.637444 | -0.022476 | 6.954428 | 1.000000 | 126726.16 |
| only_non_normal | 0.085401 | 0.152326 | 0.560642 | -0.040614 | 6.172417 | 0.290323 | 123577.94 |
| only_crisis | 0.096881 | 0.202306 | 0.478882 | -0.088095 | 2.563698 | 0.000000 | 126982.93 |

## Stress Window Verdict Per Policy
| policy | 2020_q1_q4 status / max_dd | 2022_full_year status / max_dd |
|---|---|---|
| always_on | pass / -0.016194 | pass / -0.005053 |
| only_non_normal | pass / -0.015346 | pass / -0.031491 |
| only_crisis | pass / -0.015346 | pass / -0.077209 |

## Cross-Strategy Baselines (reused from B014 sidecar where available)
- global_etf_momentum: ending_value=100963.18779949828, max_drawdown=-0.030626564701251136
- risk_parity: ending_value=103869.16382166126, max_drawdown=-0.008360811544914304
- static_60_40: ending_value=158978.38353347202, max_drawdown=-0.19663574281239315

## Narrative — Activation Policy vs 60/40 Absolute-Return Gap
- Status: real_data_ran
- always_on absolute-return gap vs static_60_40: 32252.22049454972
- only_non_normal: verdict=widened, gap_vs_60_40=35400.44531004774, delta_from_always_on=-3148.224815498019
- only_crisis: verdict=shrunk, gap_vs_60_40=31995.45314017801, delta_from_always_on=256.7673543717101

## Research Limitations
- research-only B015 activation-policy comparison; never authorizes paper or production order flow.
- no_paper_or_production_order_flow_authorized
- fixture_or_research_snapshot_only
- stress_gates_require_real_historical_snapshot_to_meaningfully_compare
- B013 strategy code unchanged in B015; activation policy is an opt-in config knob

_Disclaimer: research-only B015 activation-policy comparison; never authorizes paper or production order flow._
