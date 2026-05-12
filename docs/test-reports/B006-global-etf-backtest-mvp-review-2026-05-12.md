# B006 Global ETF Backtest MVP Review 2026-05-12

## Scope

This is the independent Evaluator review for B006 F008.

Reviewed implementation and test areas:

- `docs/specs/B006-global-etf-backtest-mvp-spec.md`
- `pyproject.toml`
- `.github/workflows/python-ci.yml`
- `trade/`
- `tests/`
- Generated evaluator workflow artifacts under `/tmp/opencode/b006-f008/`

## Result

PASS.

No blocking defects were found. The B006 Global ETF Backtest MVP satisfies the fixture/mock-first L1 acceptance criteria and preserves B001-B005 constraints: no live broker, no paper broker, no hidden secrets, no required network, T-day close signal generation, T+1 open default execution, JSON/Markdown reports, PM-compatible output, and safety guard coverage.

## L1 Verification Commands

| Command | Result | Evidence |
|---|---|---|
| `.venv/bin/python -m pytest` | PASS | 28 tests passed. |
| `.venv/bin/python -m ruff check .` | PASS | `All checks passed!` |
| `.venv/bin/python -m compileall trade tests` | PASS | Completed compilation for `trade` and `tests`. |
| `.venv/bin/python -m mypy --install-types --non-interactive trade` | PASS | `Success: no issues found in 19 source files` |

## Functional Evidence

| Area | Evidence | Result |
|---|---|---|
| Python package and CI | `pyproject.toml` defines package metadata, pytest, ruff, compileall-compatible package, and strict mypy config. `.github/workflows/python-ci.yml` runs pytest, ruff, compileall, and mypy on push / pull request. No Vitest, Playwright, Cypress, CD, deployment, database, or frontend workflow is present. | PASS |
| Fixture data and snapshot metadata | `tests/unit/test_fixture_loader.py` validates deterministic fixture loading, safe source label, symbol set, snapshot ID/checksum, calendar gap reporting, adjusted-close preservation, and missing-value rejection. | PASS |
| Global ETF momentum signal | `tests/unit/test_global_etf_momentum.py` covers signal ranking, trend filtering, defensive behavior, and parameter recording. Implementation is scoped to global ETF momentum; risk parity, multi-factor, Hong Kong / China ETF, and AI strategies are not implemented. | PASS |
| T+1 open backtest | `trade/backtest/monthly.py` generates signals from T close and uses the next trading date open by default. `tests/unit/test_monthly_backtest.py` verifies execution price field is `open`, assumption is `t_plus_1_open`, and execution price differs from signal close. Missing T+1 open falls back with explicit risk flag. | PASS |
| Risk and PM-compatible output | `tests/unit/test_risk_and_portfolio_output.py` verifies position-limit violations, defensive-switch flags, drawdown stats, strategy ID, strategy budget, target weights, and risk flags for PM-compatible output. | PASS |
| JSON/Markdown reports | `tests/unit/test_reports.py` verifies required report sections and signal/execution metadata. Independent workflow output contains `data_snapshot_id`, `parameter_hash`, `signal_price`, `execution_price`, `execution_assumption`, `strategy_budget`, `target_weights`, metrics, and risk flags. | PASS |
| Python workflow E2E | `tests/workflow/test_fixture_workflow.py` runs fixture config through workflow and generates JSON/Markdown reports. Independent evaluator run produced `/tmp/opencode/b006-f008/b006-f008-evaluator.json` and `.md`. | PASS |
| No secret / no network / no broker / no live guards | `tests/unit/test_safety_guards.py` proves workflow runs without API keys, statically rejects network imports, exports no broker entrypoints, gives AI no trade/parameter authority, and reports do not claim paper/live execution. | PASS |
| B001-B005 constraints | B006 remains low-frequency, fixture/mock-first, no external API hard dependency, no live/paper broker, no OMS/order placement, no AI trading, no tax optimization/advice, and no formal frontend dashboard. | PASS |

## Independent Workflow Artifact Summary

Evaluator generated reports with:

- JSON: `/tmp/opencode/b006-f008/b006-f008-evaluator.json`
- Markdown: `/tmp/opencode/b006-f008/b006-f008-evaluator.md`
- `execution.execution_assumption`: `t_plus_1_open`
- `execution.execution_price_field`: `open`
- `data.data_snapshot_id`: `fixture:46ab17cbb52f37ab`
- `parameters.parameter_hash`: `cec815db552443dac74c9338887c7943df6feeaa9dc1243f18a34f7bfa23c2ad`

## Non-Blocking Risks

| ID | Risk | Impact | Recommendation |
|---|---|---|---|
| R1 | MVP metrics are intentionally minimal; annualized volatility and Sharpe are currently `0.0` for the one-rebalance fixture workflow. | Reports are structurally correct but not yet analytically rich enough for real strategy evaluation. | Later backtest batches should extend multi-period return series before using metrics for research decisions. |
| R2 | Missing T+1 open fallback uses signal close and emits a risk flag. | Correctly visible, but a real research run may need stricter fallback policy. | Future implementation should allow configurable fail-closed or skip-trade behavior for missing execution prices. |
| R3 | The fixture workflow emits position-limit violation flags because selected weights exceed the default 35% max single ETF constraint. | This confirms risk flags work, but the default fixture result is intentionally not a clean investable portfolio. | Keep as guard evidence; add a clean fixture scenario later if report examples need no-warning output. |

## Conclusion

B006 F008 passes independent L1 evaluation. The implementation is suitable for MVP signoff as a fixture/mock-first Global ETF Momentum backtest baseline.
