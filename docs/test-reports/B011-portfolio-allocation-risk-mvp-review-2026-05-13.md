# B011 Portfolio Allocation And Risk MVP Review 2026-05-13

## Scope

Evaluator performed F006 independent L1 verification for B011 Master Portfolio Allocation MVP.

Reviewed areas:
- B011 spec and feature acceptance.
- Master Portfolio configuration boundary.
- Quarterly portfolio combiner and rebalance workflow.
- Account-level 15% drawdown kill-switch.
- Portfolio JSON/Markdown reports and calculated baseline.
- B009/B010 snapshot, data-quality, and research-only semantics.
- Fixture-first and no-live/no-secret/no-network-by-default/no-broker/no-paper/no-AI safety guards.

## Result

FAIL. One blocking acceptance gap remains.

## Findings

| ID | Severity | Finding | Evidence | Required Fix |
|---|---|---|---|---|
| B011-F006-1 | high | Master Portfolio does not enforce quarterly rebalance cadence. The workflow accepts and executes every supplied `signal_date`, including multiple dates inside the same calendar quarter. This violates B011 F002 and Acceptance Summary: Master must consume child target weights at quarter-ends and must not act on intra-quarter child signals. | `trade/backtest/master_portfolio.py` iterates directly over `signal_dates` without deriving, filtering, or validating quarter-end dates. Targeted smoke with `2024-03-10`, `2024-03-20`, `2024-03-25` produced three rebalances: `['2024-03-10', '2024-03-20', '2024-03-25']`. Existing test `test_master_portfolio_does_not_act_between_supplied_signal_dates` also uses same-quarter dates and asserts they are all executed. | Add an objective quarterly boundary. Acceptable options: derive quarter-end dates from fixture trading dates; filter supplied dates to the last trading day per calendar quarter; or fail closed when non-quarter-end / multiple same-quarter dates are supplied. Add tests proving intra-quarter child signals are ignored or rejected and only quarter-end weights are consumed. |

## Passing Evidence

Commands executed:

```text
./.venv/bin/python -m pytest
155 passed in 0.35s

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
64 passed in 0.15s
```

Explicit B009-style snapshot smoke:

```text
snapshot snapshot:c6bd7b4d7e909147
snapshot_manifest = {
  "path": "data/public-cache/master-prices-manifest.json",
  "snapshot_id": "public:evaluator:master"
}
rebalances = 3
timing = T close / T+1 open
baseline = static_60_40_etf_defensive_quarterly_rebalance
baseline_followups_absorbed = ['BL-B010-S2']
planning_weights = {
  "momentum": 0.4,
  "risk_parity": 0.3,
  "satellite_us_quality": 0.2,
  "satellite_hk_china": 0.1
}
first_effective_weight_sum = 1.0
limitations include imported_snapshot_data, public-best-effort, non-PIT, research-only, not-live-trading-ready
```

Evaluator AST import scan for Master modules:

```text
trade/portfolio/master.py:
  __future__, dataclasses, hashlib, json

trade/backtest/master_portfolio.py:
  __future__, dataclasses, datetime, trade.backtest.monthly, trade.data.loader,
  trade.portfolio.master, trade.strategies.global_etf_momentum,
  trade.strategies.risk_parity

trade/reporting/master_portfolio.py:
  __future__, dataclasses, datetime, json, math, pathlib, trade,
  trade.backtest.master_portfolio, trade.backtest.monthly, trade.data.loader,
  trade.data.quality
```

## Acceptance Assessment

| Feature | Result | Notes |
|---|---|---|
| F001 Master Portfolio configuration | PASS | Separate Master config exists; planning weights are 0.40/0.30/0.20/0.10 and sum to 1.0; satellite stubs fall through to defensive/cash; no leverage and 15% drawdown threshold are declared. |
| F002 Quarterly portfolio combiner and rebalance workflow | FAIL | Portfolio weighting, aggregation, T close / T+1 open fills, costs, contributions, and trace are present. Blocking gap: workflow does not enforce quarter-end-only cadence and can consume intra-quarter child signals. |
| F003 Account-level drawdown kill-switch | PASS | Trigger, non-defensive cap, event trace, human-review-required state, and child-level target preservation are covered. Clearance event is recorded; in still-breached scenarios it may trigger again after the period, which is acceptable risk behavior but should stay visible in reports. |
| F004 Portfolio reports and calculated baseline | PASS | Reports include aggregated metrics, per-child contributions, planning vs effective weights, account-risk payload, snapshot refs, research limitations, and calculated static 60/40 baseline with `BL-B010-S2` absorption. |
| F005 Safety guard and workflow regression | PASS | Safety guard suite and AST scan found no forbidden network/credential/broker/AI/public-import/frontend imports; offline/no-secret/no-generated-fixture-write/report-phrasing guards pass. |
| F006 Independent evaluation | FAIL | This review records one blocking acceptance gap; no signoff issued. |

## Non-Blocking Notes

| ID | Note | Risk | Follow-up |
|---|---|---|---|
| N1 | The committed default fixture remains a Global ETF Momentum fixture and fails closed for default Master/Risk Parity child parameters because it lacks B010 default universe/depth. | low | Existing backlog `BL-B010-S1` covers a future risk-parity/Master-capable fixture or workflow config. |
| N2 | Kill-switch clearance on a still-breached equity path clears pre-rebalance state, then may trigger again after valuation on the same signal date. | low | Keep this visible in report events; clarify semantics in a future spec if user-facing wording matters. |

## Conclusion

B011 should move to fixing. Do not sign off until the Master Portfolio workflow objectively enforces quarterly rebalance cadence and regression tests prove intra-quarter child signals are ignored or rejected.
