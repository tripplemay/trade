# B016-risk-parity-hrp-upgrade-signoff-2026-05-15

## Summary
- Batch: B016
- Stage: Codex F006 independent evaluation
- Result: PASS
- Scope: L1 local verification only; research-only HRP upgrade for B010 risk parity

## What Was Verified
- `RiskParityParameters.weighting_method` accepts only `inverse_volatility` and `hrp`; invalid values raise a diagnostic `ValueError`.
- `weighting_method="inverse_volatility"` preserves B010 signoff behavior bit-for-bit on the synthetic fixture.
- The pure-stdlib HRP module produces stable, deterministic weights on the canned reference cases.
- The comparative report exists and includes inverse-volatility, HRP, and static 60/40 rows.
- The report correctly marks real-data status as `skipped` when the B014 manifest is absent.
- The B016 strategy modules do not import scipy, numpy, pandas, sklearn, networkx, broker SDKs, or AI SDKs.
- The B016 fixture path does not perform socket I/O or env reads.
- Required local checks passed: `pytest`, `ruff`, `compileall`, `mypy`.

## Verification Evidence
- B016-focused tests: `103 passed`
- Full test suite: `526 passed`
- `ruff check trade tests scripts`: passed
- `mypy trade`: passed
- `compileall -q trade tests scripts`: passed

## Backwards Compatibility
- Default `weighting_method="inverse_volatility"` reproduces B010 signoff behavior on the synthetic fixture.
- Existing B010, B011, B013, and B015 suites passed without modification during the full test run.

## HRP vs Inverse-Vol vs 60/40
- On the synthetic comparative fixture, HRP produced slightly higher ending value and Sharpe than inverse-volatility.
- The report’s real-data branch remains `skipped` because the B014 manifest is not present in-repo by design, so the empirical 2020/2022 gap narrative is not asserted as a pass/fail condition here.

## Report Artifacts
- [docs/test-reports/B016-risk-parity-hrp-comparison-2026-05-14.md](/Users/yixingzhou/project/trade/docs/test-reports/B016-risk-parity-hrp-comparison-2026-05-14.md)
- [docs/test-reports/B016-risk-parity-hrp-comparison-2026-05-14.json](/Users/yixingzhou/project/trade/docs/test-reports/B016-risk-parity-hrp-comparison-2026-05-14.json)

## Conclusion
B016 is signable as implemented. The HRP upgrade is research-only, backwards-compatible by default, and the required local regression and safety checks are green.

