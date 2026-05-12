# B007 Backtest Quality Hardening Review 2026-05-12

## Scope

This is the independent Evaluator review for B007 F006.

Reviewed implementation and test areas:

- `docs/specs/B007-backtest-quality-hardening-spec.md`
- `trade/backtest/monthly.py`
- `trade/reporting/reports.py`
- `trade/workflow.py`
- `trade/config/defaults.py`
- `tests/unit/`
- `tests/workflow/`
- Generated evaluator workflow artifacts under `/tmp/opencode/b007-f006/`

## Result

PASS.

No blocking defects were found. B007 closes the B006 soft-watch items by adding multi-rebalance fixture evidence, explicit missing T+1 open policy handling, clean and warning risk scenarios, stronger equity-curve/metrics/report invariants, deterministic workflow reports, and preserved no-live/no-secret/no-network/no-broker/no-AI safety guards.

## L1 Verification Commands

| Command | Result | Evidence |
|---|---|---|
| `.venv/bin/python -m pytest` | PASS | 37 tests passed. |
| `.venv/bin/python -m ruff check .` | PASS | `All checks passed!` |
| `.venv/bin/python -m compileall trade tests` | PASS | Completed compilation for `trade` and `tests`. |
| `.venv/bin/python -m mypy --install-types --non-interactive trade` | PASS | `Success: no issues found in 19 source files` |

## Functional Evidence

| Area | Evidence | Result |
|---|---|---|
| Multi-rebalance fixture workflow | `trade/workflow.py` runs `run_multi_monthly_backtest` over three signal dates. Workflow tests assert `rebalance_count == 3`, three rebalance trace items, signal dates `2024-09-30`, `2024-10-31`, `2024-11-29`, and execution dates `2024-10-31`, `2024-11-29`, `2024-12-31`. | PASS |
| Missing T+1 open policy | `BacktestParameters.missing_t_plus_1_open_policy` supports `flag_and_fallback_to_signal_close`, `skip_trade`, and `fail_closed`. Unit tests cover fallback flags, skip-trade behavior, and fail-closed exception. Reports expose `missing_t_plus_1_open_policy` and `missing_t_plus_1_open_flags`. | PASS |
| Clean and warning risk scenarios | Risk tests cover clean no-warning path, warning-producing position-limit path, and expected-vs-unexpected warning classification. Independent workflow report has no warning flags while still preserving `defensive_asset_active:AGG` as a risk flag. | PASS |
| Metrics and equity curve | Reports include equity curve, monthly returns, yearly returns, annualized volatility, Sharpe, max drawdown, and turnover. Unit tests verify nonzero volatility and Sharpe for multi-rebalance fixture reports and trace equality between metrics and execution equity curves. | PASS |
| Report determinism | Workflow test compares stable report payloads across two runs after removing timestamp. Independent evaluator report includes deterministic snapshot/checksum and parameter hash. | PASS |
| T close / T+1 open invariant | Backtest and workflow tests preserve T close signal generation and T+1 open execution. Independent report shows `signal_price_field: close`, `execution_price_field: open`, and `execution_assumption: t_plus_1_open`. | PASS |
| Safety guards | Guard tests prove no `.env` / API key dependency, no network modules, no broker/live exports, no AI trade or parameter authority, no paper/live report claims, and no strategy/reporting imports from brokers or AI. | PASS |
| B001-B006 constraints | B007 remains fixture/mock-first and does not introduce real data, broker/paper/live execution, OMS, frontend, database, deployment, risk parity, multi-factor, Hong Kong / China ETF, tax optimization, or AI trading. | PASS |

## Independent Workflow Artifact Summary

Evaluator generated reports with:

- JSON: `/tmp/opencode/b007-f006/b007-f006-evaluator.json`
- Markdown: `/tmp/opencode/b007-f006/b007-f006-evaluator.md`
- `execution.rebalance_count`: `3`
- `execution.missing_t_plus_1_open_policy`: `flag_and_fallback_to_signal_close`
- `execution.missing_t_plus_1_open_flags`: `[]`
- `execution.execution_assumption`: `t_plus_1_open`
- `execution.execution_price_field`: `open`
- `metrics.annualized_volatility`: `0.06370213997333728`
- `metrics.Sharpe`: `3.5161020871449797`
- `metrics.turnover`: `3.0`
- `risk.warning_flags`: `[]`
- `risk.unexpected_warning_flags`: `[]`

## Non-Blocking Risks

| ID | Risk | Impact | Recommendation |
|---|---|---|---|
| R1 | Metrics are now nonzero and traceable, but fixture data is synthetic and intentionally small. | Results validate mechanics, not investable research quality. | Future research-grade batches should use broader historical data while preserving fixture/mock CI defaults. |
| R2 | Max drawdown is still `0.0` in the default clean workflow because the synthetic equity curve is monotonic. | Drawdown calculation is tested elsewhere, but default workflow does not demonstrate drawdown warnings. | Add a deterministic drawdown scenario when risk-hardening beyond MVP. |
| R3 | Missing T+1 open policies are unit-tested but default workflow does not trigger missing open flags. | Default report validates clean path; missing-open report behavior relies on unit coverage. | Consider a separate expected warning workflow/golden report if future evaluator workflows require all warning modes end-to-end. |

## Conclusion

B007 F006 passes independent L1 evaluation. The hardening work improves report quality and regression coverage while preserving all B001-B006 safety boundaries.
