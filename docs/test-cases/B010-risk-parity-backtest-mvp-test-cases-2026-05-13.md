# B010 Risk Parity Backtest MVP Test Cases 2026-05-13

## Scope

Local/CI-safe L1 verification for B010 Risk Parity / Volatility Target Backtest MVP.

No L2 staging, broker, paper/live, paid data, external network, DB, or frontend verification was authorized or required for this batch.

## Test Matrix

| ID | Area | Procedure | Expected Result | Evidence |
|---|---|---|---|---|
| TC-01 | Tooling baseline | Run full pytest suite. | All tests pass locally. | `./.venv/bin/python -m pytest` -> 91 passed. |
| TC-02 | Lint | Run ruff over repository. | No lint findings. | `./.venv/bin/ruff check .` -> All checks passed. |
| TC-03 | Syntax/import | Compile `trade` and `tests`. | Compileall completes. | `./.venv/bin/python -m compileall trade tests` -> PASS. |
| TC-04 | Types | Run mypy strict package check. | No type errors. | `./.venv/bin/mypy trade` -> no issues in 25 source files. |
| TC-05 | Clean env safety | Run B010 risk parity tests with an empty environment. | Risk parity tests pass without env vars/secrets. | 29 B010 tests passed under `env -i`. |
| TC-06 | Config boundary | Review and test `RiskParityParameters`. | Inverse volatility only, monthly only, no leverage, supported 60/120/252 lookbacks, defensive asset declared. | `tests/unit/test_risk_parity_config.py`. |
| TC-07 | Returns/volatility | Exercise adjusted-close daily returns and annualized volatility. | Required lookbacks work; insufficient/invalid data fails explicitly. | `tests/unit/test_risk_parity_config.py`. |
| TC-08 | Weighting/exposure | Exercise inverse-volatility weights, caps, invalid vol exclusion, target vol scaling. | Deterministic weights sum to 1.0; exposure scale capped at 1.0; unused exposure goes to defensive allocation. | `tests/unit/test_risk_parity_config.py`. |
| TC-09 | Monthly backtest | Run risk parity monthly backtest over synthetic daily ETF records. | Rebalance trace, T close signal, T+1 open fills, equity curve, turnover, costs, and defensive allocation are recorded. | `tests/unit/test_risk_parity_backtest.py`. |
| TC-10 | Reports | Generate JSON/Markdown risk parity reports. | Metrics, weights, transaction costs, baseline comparison, snapshot reference, quality flags, and research limitations are present. | `tests/unit/test_risk_parity_reports.py`. |
| TC-11 | B009-style snapshot | Generate an explicit local `data/public-cache` snapshot in a temp cwd and run risk parity end-to-end. | Report references `snapshot:*` ID and manifest path/snapshot_id; public-best-effort/non-PIT/research-only labels are preserved. | Manual evaluator smoke script in review report. |
| TC-12 | Safety guards | Static import review and runtime guard tests. | No broker, paper/live, secret, network, AI, public-import auto invocation, frontend/dashboard, or generated fixture write path in risk parity modules. | `tests/unit/test_risk_parity_safety_guards.py` plus evaluator AST import scan. |

## Result

All test cases PASS.

## Non-Blocking Observation

The existing committed default fixture is a B006/B009 momentum fixture with limited monthly-like history and symbols `AGG/EEM/SPY/VEA`; it is not sufficient for the default B010 risk parity universe (`SPY/VEA/AGG/GLD/SGOV`) and 120-day volatility lookback. B010 nevertheless satisfies the current acceptance through fixture-first unit tests and explicit local B009-style snapshot execution. A future user-facing risk parity workflow should add a first-class config or committed research fixture sized for default risk parity parameters.
