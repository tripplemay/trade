# B011 Portfolio Allocation And Risk MVP Reverification 2026-05-13

## Scope

Evaluator reverified B011 after Generator fixed `B011-F006-1`, the quarterly cadence blocker from the first review.

Focus areas:
- Quarter-end signal date detection and validation.
- Fail-closed behavior for intra-quarter / non-quarter-end / duplicate dates.
- Regression coverage for Master reports, calculated baseline, account-level risk flags, snapshot/data-quality semantics, and safety guards.

## Result

PASS. The blocking quarterly cadence gap is fixed.

## Fix Verification

Generator added:
- `identify_quarter_end_signal_dates(all_dates)`
- `_validate_quarter_end_signal_dates(signal_dates, all_dates)`
- Regression tests for quarter-end detection, intra-quarter rejection, non-quarter-end rejection, and duplicate quarter-end rejection.

Targeted evaluator smoke:

```text
quarter_ends = ['2024-03-31', '2024-06-30', '2024-09-30']
intra_quarter_result = fail-closed
error = signal_date 2024-03-10 is not a calendar quarter-end in the supplied records
rebalance_dates = ['2024-03-31', '2024-06-30', '2024-09-30']
rebalance_count = 3
weight_sums = [1.0, 1.0, 1.0]
```

## L1 Evidence

```text
./.venv/bin/python -m pytest
159 passed in 0.26s

./.venv/bin/ruff check .
All checks passed!

./.venv/bin/python -m compileall trade tests
PASS

./.venv/bin/mypy trade
Success: no issues found in 28 source files

env -i PATH="/usr/bin:/bin" HOME="$HOME" ./.venv/bin/python -m pytest \
  tests/unit/test_master_portfolio_config.py \
  tests/unit/test_master_portfolio_backtest.py \
  tests/unit/test_master_portfolio_kill_switch.py \
  tests/unit/test_master_portfolio_report.py \
  tests/unit/test_master_portfolio_safety_guards.py
68 passed in 0.11s
```

## Explicit Snapshot Smoke

```text
snapshot = snapshot:0e479b79d0d4248d
snapshot_manifest = {
  "path": "data/public-cache/master-prices-manifest.json",
  "snapshot_id": "public:evaluator:master-reverify"
}
rebalances = 3
rebalance_dates = ['2024-03-31', '2024-06-30', '2024-09-30']
timing = T close / T+1 open
baseline = static_60_40_etf_defensive_quarterly_rebalance
baseline_followups_absorbed = ['BL-B010-S2']
planning_weights = {
  "momentum": 0.4,
  "risk_parity": 0.3,
  "satellite_us_quality": 0.2,
  "satellite_hk_china": 0.1
}
limitations include imported_snapshot_data, public-best-effort, non-PIT, research-only, not-live-trading-ready
```

## Acceptance Assessment

| Feature | Result | Notes |
|---|---|---|
| F001 Master Portfolio configuration | PASS | Separate Master config, static weights, satellite stubs, no leverage, quarterly declaration, and 15% drawdown threshold remain intact. |
| F002 Quarterly portfolio combiner and rebalance workflow | PASS | Quarter-end validation now rejects intra-quarter and duplicate dates; real quarter-end runs record trace, weights, T+1 fills, costs, turnover, contributions, and equity curve. |
| F003 Account-level drawdown kill-switch | PASS | Trigger/cap/clear/report behavior remains covered and deterministic. |
| F004 Portfolio reports and calculated baseline | PASS | Combined reports include account risk, limitations, snapshot refs, and calculated 60/40 baseline with `BL-B010-S2` absorption. |
| F005 Safety guard and workflow regression | PASS | No forbidden network/credential/broker/AI/public-import/frontend imports; empty-env and no-generated-fixture-write guards pass. |
| F006 Independent evaluation | PASS | Reverification and signoff artifacts complete. |

## Conclusion

B011 is ready for signoff.
