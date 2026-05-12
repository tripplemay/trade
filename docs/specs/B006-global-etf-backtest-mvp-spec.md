# B006 Global ETF Backtest MVP Spec

## Background

B001-B005 established the strategy roadmap, data/broker/environment architecture, MVP PRD, engineering foundation, and pre-backtest architecture adjudications. B006 is the first implementation batch. It must create a minimal, executable Global ETF Momentum backtest MVP while preserving all safety, data, and architecture constraints.

## Goal

Implement a fixture/mock-first, reproducible Global ETF Momentum backtest MVP that runs locally and in CI without secrets, network, data-vendor APIs, broker APIs, paper broker, live broker, frontend, deployment, or database dependencies.

## Hard Decisions

- B006 introduces CI, not CD.
- B006 does not introduce Vitest.
- B006 does not introduce Playwright, Cypress, or browser E2E.
- B006 must include Python unit tests, integration tests, workflow E2E tests, and guard tests.
- B006 default execution assumption is T-day close signal generation and T+1 open execution.
- B006 must output JSON and Markdown reports.
- B006 must remain compatible with future Portfolio Manager consumption but must not implement real PM rebalancing, OMS, broker execution, tax optimization, AI trading, or frontend dashboard.

## Reference Documents

- `docs/prd/mvp-prd.md`
- `docs/specs/B004-core-engineering-foundation-spec.md`
- `docs/specs/B005-pre-backtest-architecture-adjudication-spec.md`
- `docs/engineering/python-package-boundary.md`
- `docs/engineering/config-and-environment-policy.md`
- `docs/engineering/testing-and-fixture-policy.md`
- `docs/engineering/no-live-safety-guards.md`
- `docs/engineering/backtest-report-schema.md`
- `docs/engineering/portfolio-allocation-boundary.md`
- `docs/engineering/pit-data-degradation-policy.md`
- `docs/engineering/oms-tax-lot-boundary.md`
- `docs/engineering/ai-filing-prefilter-policy.md`
- `docs/strategy/00-master-portfolio-allocation.md`
- `docs/strategy/01-global-etf-momentum-rotation.md`

## Proposed Implementation Shape

### Package And Directories

The implementation should use a minimal Python package layout:

```text
trade/
  config/
  data/
  strategies/
  backtest/
  risk/
  reporting/
  portfolio/
  brokers/
  ai/
tests/
  fixtures/
  unit/
  integration/
  workflow/
```

`portfolio`, `brokers`, and `ai` may be stubs or boundary modules only when needed for guard tests. They must not expose paper/live execution paths.

### Tooling

B006 should create `pyproject.toml` and use:

- `pytest`
- `ruff`
- `python -m compileall trade`
- `mypy` enabled or explicitly staged with a documented reason and non-silent CI behavior

### CI

Create minimal GitHub Actions CI that runs on push / pull request and executes required Python checks. The CI must not require secrets or network access beyond dependency installation.

CD is out of scope.

### Fixtures

Fixtures must be small, committed, deterministic, and safe to redistribute. They should include enough data to test:

- 3-5 ETF-like instruments plus one defensive asset.
- 8-15 months of daily or representative trading data.
- At least one T+1 open price different from T close.
- Calendar gaps.
- Missing-value or invalid-data handling.
- At least one defensive-asset switch.

CSV or JSON is preferred for reviewability. Parquet, DuckDB, and external data downloads are out of required scope.

### Config

Use a committed safe fixture config. JSON is preferred unless the implementation already justifies a YAML dependency. Required tests must pass without `.env`.

### Reports

Reports should be written to a deterministic artifact path for workflow tests. Runtime artifacts should not require committing generated reports except small expected/golden files used by tests.

## Feature Requirements

### F001 Python Package Scaffold And CI

Executor: generator.

Create the package, test directories, `pyproject.toml`, and CI. Do not create frontend, database, deployment, broker, or external API infrastructure.

### F002 Fixture Data Loader And Snapshot Metadata

Executor: generator.

Implement fixture/local data loading, schema validation, checksum or snapshot ID calculation, and tests for deterministic loading.

### F003 Global ETF Momentum Signal Generation

Executor: generator.

Implement the minimum global ETF momentum strategy: momentum windows, Top N, defensive asset, trend filter, and parameter recording.

### F004 Monthly Backtest Engine With T+1 Open Execution

Executor: generator.

Implement low-frequency monthly rebalancing. Generate signals from T-day close data and execute at T+1 open by default. Record fallback risk flags if T+1 open data is missing.

### F005 Risk Checks And PM-Compatible Output

Executor: generator.

Implement basic weight limits, drawdown metrics, defensive switch flags, and Portfolio Manager-compatible output fields.

### F006 JSON/Markdown Backtest Reports

Executor: generator.

Generate JSON and Markdown reports following `docs/engineering/backtest-report-schema.md`.

### F007 Workflow E2E And Guard Tests

Executor: generator.

Add a Python workflow E2E test that runs fixture config through data loading, signal generation, backtest, risk checks, and report generation. Add guard tests proving no `.env`, no API key, no required network, no broker call, no paper/live entrypoint, and no AI trade/parameter authority.

### F008 Independent Evaluation

Executor: codex.

Evaluator runs L1 verification on port-free/local/CI-safe paths, reviews code and reports, and signs off only if B006 satisfies B001-B005 constraints.

## Out Of Scope

- Vitest.
- Playwright / Cypress / browser E2E.
- Frontend dashboard.
- CD / deployment.
- External data provider dependency for required tests.
- Broker, paper broker, live broker, OMS, or order placement.
- Risk parity, US multi-factor, Hong Kong / China ETF strategy implementation.
- AI news/filing analysis implementation.
- Tax optimization or tax advice.
- Production database or migrations.

## Acceptance Summary

B006 is complete only when:

- Required checks pass locally and in CI.
- Fixture workflow E2E generates JSON/Markdown reports.
- T+1 open execution is verified by tests.
- Reports include snapshot, parameter, signal, execution, metric, and risk metadata.
- No-live/no-secret/no-network/no-broker/no-AI-trade guards pass.
- Evaluator signs off F008.
