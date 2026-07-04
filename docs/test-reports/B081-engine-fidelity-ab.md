# B081 engine-fidelity A/B — B070 de-biased PIT (pure_momentum + equal)

Window 2019-04-01..snapshot-end. All fixes are **更保守/数字变差=诚实** (印花税 10→5bp is the lone 口径更正, numbers-better). The **old_all_off** group bit-level reproduces the B070 signoff — proof the fixes never polluted the old path.

| group | full CAGR | full Sharpe | MaxDD | ending | turnover | cost | OOS CAGR | OOS Sharpe | OOS DD | rebs |
|---|---|---|---|---|---|---|---|---|---|---|
| old_all_off | 13.1% | 0.559 | -58.3% | 243406 | 194.0 | 35802 | 28.4% | 0.93 | -27.8% | 639 |
| only_lot_rounding | -8.6% | -0.653 | -50.7% | 52147 | 1160.3 | 74041 | -16.0% | -2.162 | -31.4% | 1749 |
| only_partial_rebalance | 20.7% | 0.769 | -50.2% | 387740 | 236.0 | 58147 | 32.7% | 1.04 | -24.8% | 1517 |
| only_suspension_halt | 13.1% | 0.559 | -58.3% | 243406 | 194.0 | 35802 | 28.4% | 0.93 | -27.8% | 639 |
| only_delist_liquidation | 13.1% | 0.559 | -58.3% | 243406 | 194.0 | 35802 | 28.4% | 0.93 | -27.8% | 639 |
| only_price_limit_gating | 13.1% | 0.559 | -58.2% | 243331 | 194.8 | 35694 | 28.9% | 0.939 | -27.4% | 642 |
| new_all_on | -6.6% | -0.409 | -46.9% | 61360 | 1069.7 | 72566 | -14.7% | -1.671 | -29.4% | 1749 |
| new_all_on_recovery_0p5 | -6.6% | -0.409 | -46.9% | 61360 | 1069.7 | 72566 | -14.7% | -1.671 | -29.4% | 1749 |

> research-only / advisory-only. Each fix has an independent switch; off = bit-level pre-B081口径. Delist recovery 0.5 is the haircut sensitivity.
