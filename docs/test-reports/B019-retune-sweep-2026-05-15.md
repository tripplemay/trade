# B019-retune-sweep-2026-05-15

## 1. 背景
- 本批次承接 [B018 签收报告](./B018-gap-attribution-signoff-2026-05-15.md)，复用 `BL-B018-S1` 所示的 B010 cadence / vol-target 联合 retune 候选。
- `framework v0.9.21 #1` 要求任何收益 / 回撤 / turnover 对比都必须在 B014 真实 snapshot 上复验。
- 本批次目标是细网格 `(cadence, vol_target)` sweep，并据 4 条 gate 裁决是否进入 default mutation。

## 2. Sweep Matrix
### B010
| cadence | vol_target | calm ending | calm gap vs 60/40 | 2020 max DD | 2022 max DD | calm turnover | verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| monthly | 0.09 | 104761.70 | -54216.68 | 0.000000 | -0.011968 | 3.0352 | fail |
| monthly | 0.10 | 105300.08 | -53678.30 | 0.000000 | -0.013329 | 3.2613 | fail |
| monthly | 0.11 | 105840.09 | -53138.29 | 0.000000 | -0.014690 | 3.4875 | fail |
| monthly | 0.12 | 106381.66 | -52596.72 | 0.000000 | -0.016050 | 3.6693 | fail |
| monthly | 0.13 | 106962.07 | -52016.32 | 0.000000 | -0.017411 | 3.5449 | fail |
| quarterly | 0.09 | 103679.80 | -55298.59 | 0.000000 | -0.014107 | 2.6193 | fail |
| quarterly | 0.10 | 104098.70 | -54879.68 | 0.000000 | -0.015697 | 2.7992 | fail |
| quarterly | 0.11 | 104518.67 | -54459.72 | 0.000000 | -0.017287 | 2.9791 | fail |
| quarterly | 0.12 | 104939.69 | -54038.70 | 0.000000 | -0.018875 | 3.1590 | fail |
| quarterly | 0.13 | 105363.89 | -53614.50 | 0.000000 | -0.020463 | 3.1283 | fail |

Default baseline:
| window | ending | gap vs 60/40 | max DD | turnover |
|---|---:|---:|---:|---:|
| calm | 104224.96 | -54753.43 | -0.010606 | 2.8091 |
| stress_2020 | 0.00 | — | 0.000000 | 0.0000 |
| stress_2022 | 102083.59 | — | -0.010606 | 1.6330 |

### B013
| cadence | vol_target | calm ending | calm gap vs 60/40 | 2020 max DD | 2022 max DD | calm turnover | verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| monthly | 0.09 | 128234.25 | -30744.13 | -0.999670 | -0.005934 | 7.6682 | fail |
| monthly | 0.10 | 129700.51 | -29277.88 | -0.999497 | -0.006814 | 8.3994 | fail |
| monthly | 0.11 | 131058.25 | -27920.13 | -0.999265 | -0.007694 | 9.2839 | fail |
| monthly | 0.12 | 132512.87 | -26465.51 | -0.999046 | -0.008574 | 9.7699 | fail |
| monthly | 0.13 | 134077.01 | -24901.37 | -0.998787 | -0.009609 | 10.0646 | fail |
| quarterly | 0.09 | 133332.96 | -25645.43 | -0.901287 | -0.003747 | 5.0868 | pass |
| quarterly | 0.10 | 135425.62 | -23552.77 | -0.878222 | -0.004363 | 5.4032 | pass |
| quarterly | 0.11 | 136717.64 | -22260.75 | -0.853068 | -0.004980 | 5.9851 | pass |
| quarterly | 0.12 | 139302.82 | -19675.57 | -0.839824 | -0.005596 | 6.4013 | fail |
| quarterly | 0.13 | 141907.72 | -17070.66 | -0.826602 | -0.006212 | 6.5980 | fail |

Default baseline:
| window | ending | gap vs 60/40 | max DD | turnover |
|---|---:|---:|---:|---:|
| calm | 126726.16 | -32252.22 | -0.022476 | 6.9544 |
| stress_2020 | 24.37 | — | -0.999794 | 1.5656 |
| stress_2022 | 124839.13 | — | -0.005053 | 1.8617 |

## 3. Per-cell Gate Verdicts
### B010
| cadence | vol_target | calm uplift % | gap narrowing pp | stress do-no-harm | turnover % | all pass |
|---|---:|---:|---:|---|---:|---|
| monthly | 0.09 | 0.515 | 0.537 | no | 8.050 | no |
| monthly | 0.10 | 1.032 | 1.075 | no | 16.100 | no |
| monthly | 0.11 | 1.550 | 1.615 | no | 24.150 | no |
| monthly | 0.12 | 2.069 | 2.157 | no | 30.625 | no |
| monthly | 0.13 | 2.626 | 2.737 | no | 26.196 | no |
| quarterly | 0.09 | -0.523 | -0.545 | no | -6.756 | no |
| quarterly | 0.10 | -0.121 | -0.126 | no | -0.352 | no |
| quarterly | 0.11 | 0.282 | 0.294 | no | 6.053 | no |
| quarterly | 0.12 | 0.686 | 0.715 | no | 12.458 | no |
| quarterly | 0.13 | 1.093 | 1.139 | no | 11.366 | no |

### B013
| cadence | vol_target | calm uplift % | gap narrowing pp | stress do-no-harm | turnover % | all pass |
|---|---:|---:|---:|---|---:|---|
| monthly | 0.09 | 1.190 | 1.508 | no | 10.264 | no |
| monthly | 0.10 | 2.347 | 2.974 | no | 20.778 | no |
| monthly | 0.11 | 3.418 | 4.332 | no | 33.496 | no |
| monthly | 0.12 | 4.566 | 5.787 | no | 40.484 | no |
| monthly | 0.13 | 5.801 | 7.351 | no | 44.723 | no |
| quarterly | 0.09 | 5.213 | 6.607 | yes | -26.856 | yes |
| quarterly | 0.10 | 6.865 | 8.699 | yes | -22.305 | yes |
| quarterly | 0.11 | 7.884 | 9.991 | yes | -13.938 | yes |
| quarterly | 0.12 | 9.924 | 12.577 | no | -7.954 | no |
| quarterly | 0.13 | 11.980 | 15.182 | no | -5.125 | no |

## 4. Pareto Recommendations
### B010 — low_dd — quarterly / 0.13
- Calm ending value: 105363.89
- Calm gap vs 60/40: -53614.50
- 2020 max DD: 0.000000
- 2022 max DD: -0.020463
- Turnover: 3.1283

### B010 — balanced — quarterly / 0.13
- Calm ending value: 105363.89
- Calm gap vs 60/40: -53614.50
- 2020 max DD: 0.000000
- 2022 max DD: -0.020463
- Turnover: 3.1283

### B010 — high_return — monthly / 0.13
- Calm ending value: 106962.07
- Calm gap vs 60/40: -52016.32
- 2020 max DD: 0.000000
- 2022 max DD: -0.017411
- Turnover: 3.5449

### B013 — low_dd — monthly / 0.13
- Calm ending value: 134077.01
- Calm gap vs 60/40: -24901.37
- 2020 max DD: -0.998787
- 2022 max DD: -0.009609
- Turnover: 10.0646

### B013 — balanced — quarterly / 0.11
- Calm ending value: 136717.64
- Calm gap vs 60/40: -22260.75
- 2020 max DD: -0.853068
- 2022 max DD: -0.004980
- Turnover: 5.9851

### B013 — high_return — quarterly / 0.13
- Calm ending value: 141907.72
- Calm gap vs 60/40: -17070.66
- 2020 max DD: -0.826602
- 2022 max DD: -0.006212
- Turnover: 6.5980

## 5. Top-level Verdict
- B010: gate_met=False, winning_cell=None
- B013: gate_met=True, winning_cell=('quarterly', 0.11)
- 结论：B013 已有 `(cadence, vol_target)=('quarterly', 0.11)` cell 同时满足四条 acceptance gate，因此 Stage 2 触发；B010 未达标，保持不变。

## 6. Snapshot Recap
- Snapshot id: `regime-adaptive:b69883b08eedea7d`
- Manifest: `data/public-cache/regime-adaptive-prices-manifest.json`
- Coverage: 2018-01-02..2025-12-31, 9 assets, real-data status = ran
- Research-only disclaimer: 本报告仅用于研究验证，不授权 paper / live / broker / AI 执行。
