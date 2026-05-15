# B019-b015-activation-policy-rerun-2026-05-15

## Summary
- Batch: B015
- Report date: 2026-05-15
- Description: Comparative backtest of B013 regime-adaptive strategy under three regime_activation_policy values: always_on (baseline), only_non_normal, only_crisis. B013 strategy code is unchanged; only the activation policy config knob varies between rows.
- Comparison window: 2022-07-01..2024-06-27 (one-trading-day headroom preserved for T+1 open execution at the snapshot tail).

## Real-Data Status
- Status: ran
- Snapshot manifest id: regime-adaptive:b69883b08eedea7d
- Snapshot date range: {'start': '2018-01-02', 'end': '2025-12-31'}

## Per-Policy Metrics (B013 regime-adaptive)
| policy | annualized_return | annualized_volatility | sharpe | max_drawdown | turnover | L1 firing rate | ending_value |
|---|---|---|---|---|---|---|---|
| always_on | 0.155803 | 0.158989 | 0.979957 | -0.030274 | 7.355998 | 1.000000 | 133587.95 |
| only_non_normal | 0.153194 | 0.164561 | 0.930927 | -0.045700 | 6.795418 | 0.250000 | 132985.65 |
| only_crisis | 0.169331 | 0.171853 | 0.985321 | -0.052519 | 1.900377 | 0.000000 | 136733.42 |

## Stress Window Verdict Per Policy
| policy | 2020_q1_q4 status / max_dd | 2022_full_year status / max_dd |
|---|---|---|
| always_on | skipped / 0.000000 | pass / -0.002234 |
| only_non_normal | skipped / 0.000000 | pass / -0.014263 |
| only_crisis | skipped / 0.000000 | pass / -0.052519 |

## Cross-Strategy Baselines (reused from B014 sidecar where available)
- global_etf_momentum: ending_value=100963.18779949828, max_drawdown=-0.030626564701251136
- risk_parity: ending_value=103869.16382166126, max_drawdown=-0.008360811544914304
- static_60_40: ending_value=158978.38353347202, max_drawdown=-0.19663574281239315

## Narrative — Activation Policy vs 60/40 Absolute-Return Gap
- Status: real_data_ran
- always_on absolute-return gap vs static_60_40: 25390.43068881717
- only_non_normal: verdict=widened, gap_vs_60_40=25992.735476937378, delta_from_always_on=-602.3047881202074
- only_crisis: verdict=shrunk, gap_vs_60_40=22244.967238516052, delta_from_always_on=3145.4634503011184

## Research Limitations
- research-only B015 activation-policy comparison; never authorizes paper or production order flow.
- no_paper_or_production_order_flow_authorized
- fixture_or_research_snapshot_only
- stress_gates_require_real_historical_snapshot_to_meaningfully_compare
- B013 strategy code unchanged in B015; activation policy is an opt-in config knob

_Disclaimer: research-only B015 activation-policy comparison; never authorizes paper or production order flow._
