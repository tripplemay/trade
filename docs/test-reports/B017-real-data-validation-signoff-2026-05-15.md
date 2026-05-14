# B017-real-data-validation-signoff-2026-05-15

## Summary
- Batch: B017
- Result: PASS
- Scope: Codex-only real-data validation for B015 + B016
- Data source: B014 yfinance snapshot acquired and registered successfully

## Acquisition
- Snapshot id: `regime-adaptive:b69883b08eedea7d`
- Manifest: `data/public-cache/regime-adaptive-prices-manifest.json`
- Coverage gate: 8 non-SGOV tickers exceeded 95% weekday coverage; SGOV short history accepted
- Acquisition log: [docs/test-reports/B017-real-data-validation-acquisition-log-2026-05-15.md](/Users/yixingzhou/project/trade/docs/test-reports/B017-real-data-validation-acquisition-log-2026-05-15.md)

## Verification
- Full test suite: `526 passed`
- `ruff check trade tests scripts`: passed
- `mypy trade`: passed
- `compileall -q trade tests scripts`: passed

## B015 Real-Data Findings
Window: 2020-06-01..2022-12-31

| policy | ending_value | gap_vs_60_40 | delta_vs_always_on | 2020 max DD | 2022 max DD | L1 firing |
|---|---:|---:|---:|---:|---:|---:|
| always_on | 126726.16 | 32252.22 | baseline | -0.016194 | -0.005053 | 1.000000 |
| only_non_normal | 123577.94 | 35400.45 | -3148.22 | -0.015346 | -0.031491 | 0.290323 |
| only_crisis | 126982.93 | 31995.45 | +256.77 | -0.015346 | -0.077209 | 0.000000 |

- Research answer: `only_crisis` is marginally closer to static 60/40 than `always_on`; `only_non_normal` is worse.
- Stress gate: all three policies stayed above the -15% threshold in both 2020 and 2022 sub-windows.

## B016 Real-Data Findings
Window: 2020-06-01..2022-12-31

| method | ending_value | gap_vs_60_40 | delta_vs_inverse_vol | 2020 max DD | 2022 max DD | turnover |
|---|---:|---:|---:|---:|---:|---:|
| inverse_volatility | 103657.79 | 55320.59 | baseline | -0.003269 | -0.007181 | 3.100410 |
| hrp | 103161.35 | 55817.03 | -496.44 | -0.006024 | -0.007860 | 4.376236 |

- Research answer: HRP does not shrink the gap vs static 60/40 on this snapshot; it is slightly worse than inverse-volatility.
- Stress gate: both weighting methods stayed above the -15% threshold in both 2020 and 2022 sub-windows.
- Operational note: HRP increased turnover relative to inverse-volatility.

## Cross-Analysis
- B015 and B016 are independent variants over the same real snapshot; they do not form a 3x2 matrix.
- Best B015 policy by ending value: `only_crisis`, but the improvement is tiny versus `always_on`.
- Best B016 method by ending value: `inverse_volatility`; HRP underperformed by `496.44` in ending value on the real snapshot.
- None of the evaluated configurations closed the large absolute-return gap versus static 60/40.

## Framework / Backlog
- No `framework/proposed-learnings.md` entry was added: no configuration breached the -15% stress gate.
- No backlog entry was added: no hybrid candidate rose to the level of an obvious follow-up from this run.

## Conclusion
B017 is complete and signable. The real-data snapshot was acquired, both comparison reports were regenerated with `real_data_status = ran`, and the empirical findings answer both research questions with concrete numbers.

_Disclaimer: research-only real-data validation; never authorizes paper or live trading._

