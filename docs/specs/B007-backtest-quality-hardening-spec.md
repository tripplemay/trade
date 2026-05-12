# B007 Backtest Quality Hardening Spec

## Background

B006 delivered the first fixture/mock-first Global ETF Momentum backtest MVP and passed independent L1 verification. Manual user validation also confirmed T-day close signal generation, T+1 open execution, and safety guard behavior.

B006 intentionally remained minimal. The signoff soft-watch items should now be addressed before adding more strategies or broker/paper execution surfaces.

## Goal

Harden the existing backtest MVP so fixture workflows provide more meaningful multi-rebalance evidence, clearer execution fallback behavior, stronger report invariants, and regression coverage that prevents future loss of the B006 safety and timing guarantees.

## Hard Decisions

- B007 improves the existing fixture/local backtest path; it does not introduce live data, external APIs, broker APIs, paper broker, live broker, OMS, database, deployment, frontend dashboard, or AI trading.
- Required tests must continue to run locally and in CI without secrets, `.env`, network access, data-vendor credentials, or broker credentials.
- T-day close signal generation and T+1 open execution remain the default execution model.
- Missing T+1 open handling must become explicit and configurable. Silent fallback is not acceptable.
- B007 should deepen Global ETF Momentum backtest quality, not implement risk parity, multi-factor, Hong Kong / China ETF strategies, or tax optimization.

## Reference Documents

- `docs/specs/B006-global-etf-backtest-mvp-spec.md`
- `docs/test-reports/B006-global-etf-backtest-mvp-signoff-2026-05-12.md`
- `docs/engineering/python-package-boundary.md`
- `docs/engineering/config-and-environment-policy.md`
- `docs/engineering/testing-and-fixture-policy.md`
- `docs/engineering/no-live-safety-guards.md`
- `docs/engineering/backtest-report-schema.md`
- `docs/engineering/portfolio-allocation-boundary.md`
- `docs/strategy/00-master-portfolio-allocation.md`
- `docs/strategy/01-global-etf-momentum-rotation.md`

## Proposed Implementation Shape

### Fixtures

Extend committed fixture coverage while keeping files small and reviewable. The fixture set should cover multiple month-end signal dates and multiple T+1 execution dates so report metrics are not based on a single rebalance.

At minimum, fixtures should include:

- A normal path with multiple rebalance cycles and available T+1 open prices.
- A missing T+1 open scenario that exercises the configurable fallback behavior.
- A clean risk path with no position-limit warning, in addition to the existing warning-producing scenario.
- Deterministic snapshot IDs/checksums after fixture changes.

### Execution Fallback Policy

Introduce an explicit missing-execution-price policy for T+1 open gaps. The supported behavior should be narrow and testable, for example:

- `flag_and_fallback_to_signal_close` for current B006-compatible behavior.
- `skip_trade` or `fail_closed` if the implementation chooses a safer default.

The chosen default must be documented in code/config/report fields and covered by tests. Reports must surface both the configured policy and any triggered fallback/skip/fail flags.

### Metrics And Reports

Improve report usefulness without turning the MVP into a research platform. Metrics should be deterministic and derived from fixture data only.

Reports should preserve B006 fields and strengthen these invariants:

- Multi-period monthly returns are populated when the fixture supports them.
- Yearly returns aggregate from monthly returns.
- Volatility and Sharpe are no longer trivially zero in the normal multi-rebalance fixture unless mathematically justified by the fixture.
- Max drawdown is traceable to the equity curve.
- Turnover reflects rebalance changes.
- Risk flags distinguish warning-producing fixtures from clean fixtures.
- `execution_assumption`, missing-price policy, signal price field, and execution price field remain explicit.

## Feature Requirements

### F001 Extend Multi-Rebalance Fixtures

Executor: generator.

Extend committed fixture data and loader tests so the default workflow can exercise multiple monthly rebalance cycles with deterministic snapshot metadata. Keep fixture data synthetic, local, small, and reviewable.

### F002 Configure Missing T+1 Open Handling

Executor: generator.

Add explicit configuration for missing T+1 open execution prices. Tests must cover at least the default behavior and one missing-price scenario. Reports must include the configured policy and triggered risk flags.

### F003 Add Clean And Warning Risk Scenarios

Executor: generator.

Provide fixture/test coverage for both a clean no-warning path and a warning-producing path. Risk output must make it easy to distinguish expected warnings from unexpected regressions.

### F004 Harden Metrics And Equity-Curve Reporting

Executor: generator.

Improve performance metric calculation and report fields around monthly returns, yearly returns, volatility, Sharpe, max drawdown, turnover, and equity curve traceability. Tests must validate these fields on deterministic fixture data.

### F005 Preserve Safety And Workflow Regression Guards

Executor: generator.

Update workflow E2E and guard tests so B006 invariants remain protected after fixture/report changes: no secrets, no required network, no broker/paper/live entrypoint, no AI trade authority, T close signal, T+1 open default execution, and deterministic JSON/Markdown report generation.

### F006 Independent Evaluation

Executor: codex.

Evaluator runs L1 verification on local/CI-safe paths, reviews generated reports, checks B006 soft-watch closure evidence, and signs off only if B007 preserves all B001-B006 safety boundaries while improving backtest quality.

## Out Of Scope

- Real market data ingestion or external data provider integration.
- Broker, paper broker, live broker, OMS, order placement, or account operations.
- Frontend dashboard, browser E2E, Vitest, Playwright, or Cypress.
- Deployment, CD, production database, or migrations.
- Risk parity, US multi-factor, Hong Kong / China ETF strategy implementation.
- AI news/filing analysis, AI trading, or AI parameter mutation.
- Tax optimization or tax advice.

## Acceptance Summary

B007 is complete only when:

- Required checks pass locally: pytest, ruff, compileall, and mypy.
- Default fixture workflow generates deterministic JSON/Markdown reports with multiple rebalance evidence.
- Missing T+1 open handling is explicit, configurable, tested, and visible in reports.
- Clean and warning risk scenarios are both covered.
- Metrics/report invariants are tested and analytically more meaningful than B006's one-rebalance path.
- No-live/no-secret/no-network/no-broker/no-AI-trade guards still pass.
- Evaluator signs off F006 with a report under `docs/test-reports/`.
