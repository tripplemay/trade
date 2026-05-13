# B011 Portfolio Allocation And Risk MVP Test Cases 2026-05-13

## Scope

Local/CI-safe L1 verification for B011 Master Portfolio Allocation MVP.

No L2 staging, broker, paper/live, paid data, external network, DB, or frontend verification was authorized or required for this batch.

## Test Matrix

| ID | Area | Procedure | Expected Result | Evidence |
|---|---|---|---|---|
| TC-01 | Tooling baseline | Run full pytest suite. | All tests pass locally. | Reverification: `./.venv/bin/python -m pytest` -> 159 passed. |
| TC-02 | Lint | Run ruff over repository. | No lint findings. | `./.venv/bin/ruff check .` -> All checks passed. |
| TC-03 | Syntax/import | Compile `trade` and `tests`. | Compileall completes. | `./.venv/bin/python -m compileall trade tests` -> PASS. |
| TC-04 | Types | Run mypy package check. | No type errors. | `./.venv/bin/mypy trade` -> no issues in 28 source files. |
| TC-05 | Clean env safety | Run B011 Master Portfolio tests with an empty environment. | Master tests pass without env vars/secrets. | Reverification: 68 B011 tests passed under `env -i`. |
| TC-06 | Config boundary | Review and test `MasterPortfolioParameters`. | Two implemented core sleeves, two satellite stubs, 0.40/0.30/0.20/0.10 weights, no leverage, quarterly declaration, 15% drawdown threshold. | `tests/unit/test_master_portfolio_config.py`. |
| TC-07 | Portfolio workflow | Exercise Master rebalance, contributions, T close / T+1 open, costs, turnover, equity curve. | Full trace is recorded and weights sum to 1.0. | `tests/unit/test_master_portfolio_backtest.py`. |
| TC-08 | Quarterly cadence | Pass multiple signal dates from the same calendar quarter; then pass confirmed quarter-end dates. | Master should consume only quarter-end weights or reject/filter intra-quarter dates. | PASS after fix: same-quarter non-quarter-end dates fail closed; `2024-03-31/06-30/09-30` produce exactly three rebalances. |
| TC-09 | Kill-switch | Exercise drawdown helper, non-defensive caps, trigger, clearance event, report visibility. | Trigger/cap/report behavior deterministic; clearance behavior recorded. | `tests/unit/test_master_portfolio_kill_switch.py`, targeted smoke. |
| TC-10 | Reports | Generate JSON/Markdown portfolio reports. | Aggregated metrics, contributions, planning vs effective weights, account risk, limitations, snapshot refs, calculated baseline with `BL-B010-S2`. | `tests/unit/test_master_portfolio_report.py`, explicit snapshot smoke. |
| TC-11 | B009-style snapshot | Generate explicit local `data/public-cache` snapshot in temp cwd and run Master end-to-end. | Report references `snapshot:*` ID and manifest; limitations include public-best-effort/non-PIT/research-only; baseline is calculated and absorbs `BL-B010-S2`. | PASS. |
| TC-12 | Safety guards | Static import review and runtime guard tests. | No broker, paper/live, secret, network, AI, public-import auto invocation, frontend/dashboard, or generated fixture write path in Master modules. | `tests/unit/test_master_portfolio_safety_guards.py` plus evaluator AST import scan. |

## Result

PASS after reverification. TC-08 was blocking in the first review and is fixed.

## Required Fix Focus

Generator added an objective quarterly cadence boundary. `identify_quarter_end_signal_dates()` identifies confirmed complete quarter-ends, and `run_master_portfolio_quarterly_backtest()` fails closed for non-quarter-end or duplicate quarter-end signal dates.
