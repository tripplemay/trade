# B004 Core Engineering Foundation Spec

## Background

B001 defined the strategy roadmap. B002 defined data-source, broker-adapter, point-in-time, and environment-isolation constraints. B003 signed off the MVP PRD. An independent strategy audit then highlighted a portfolio-level gap: the system should not proceed from a single global ETF backtest directly into implementation without account-level allocation, drawdown, slippage, tax, macro-filter, and AI prefilter boundaries.

## Goal

Produce the documentation/specification baseline for the MVP engineering foundation.

B004 is a pure documentation/spec batch. It does not create product implementation code, package scaffolding, CI configuration, migrations, frontend app, broker integration, data downloader, or deployment configuration.

## User Decisions

- B004 is a pure documentation specification batch.
- `docs/strategy/00-master-portfolio-allocation.md` is required.
- Python technical-stack decisions are required in B004.
- B005 may include an optional real public-data download script, but default CI and L1 tests must remain fixture/mock-only and not depend on external API availability.
- Initial portfolio allocation uses a static baseline plus quarterly rebalancing.

## Scope

B004 creates the following planning artifacts:

- `docs/engineering/python-package-boundary.md`
- `docs/engineering/config-and-environment-policy.md`
- `docs/engineering/no-live-safety-guards.md`
- `docs/engineering/testing-and-fixture-policy.md`
- `docs/engineering/portfolio-allocation-boundary.md`
- `docs/engineering/backtest-report-schema.md`
- `docs/strategy/00-master-portfolio-allocation.md`

## Out Of Scope

- Product source code.
- Python package scaffold creation.
- Real data provider integration.
- Broker or paper broker API calls.
- Live trading.
- Cloud deployment.
- Formal frontend dashboard or React/Next.js app.
- Database schema or migrations.

## Feature Requirements

### F001 Engineering Foundation Spec

Executor: generator.

Create this B004 spec and define B004 as a documentation-only planning batch. The spec must preserve B003 MVP boundaries and the BL-001 independent strategy-audit recommendations.

### F002 Python Package Boundary

Executor: generator.

Create `docs/engineering/python-package-boundary.md` defining package/module responsibilities for data, strategies, backtest, portfolio, risk, reporting, brokers, and AI. The broker module is interface/mock-only in MVP.

### F003 Config, Environment, and No-Live Guards

Executor: generator.

Create config/environment and no-live guard documents. Defaults must be safe for local and CI. Paper/live requires explicit authorization and cannot be reachable by default flags, environment discovery, or accidental secrets.

### F004 Testing and Fixture Policy

Executor: generator.

Create the test policy. B005 must be runnable without external APIs, secrets, paid data, broker credentials, or network availability. The Python baseline should use pytest, ruff, compileall, and mypy.

### F005 Portfolio Allocation and Account-Level Risk Boundary

Executor: generator.

Create `docs/strategy/00-master-portfolio-allocation.md` and `docs/engineering/portfolio-allocation-boundary.md`. Include static baseline allocation, quarterly rebalancing, account-level drawdown kill switch, child-strategy budgets, slippage/tax/macro-filter boundaries, and AI prefilter constraints.

### F006 Backtest Report Schema and B005 Handoff

Executor: generator.

Create `docs/engineering/backtest-report-schema.md` defining JSON/Markdown output requirements for B005, including assumptions, parameters, universe, data snapshot ID, metrics, risk flags, and reproducibility fields.

### F007 Independent Consistency Review

Executor: codex.

Evaluator reviews all B004 documents against B001, B002, B003, and `docs/research/strategy-audit-report-2026-05-12.md`. The review must verify that B004 remains documentation-only and does not authorize live trading, real broker calls, external API hard dependency, hidden secret dependency, or formal frontend implementation.

## Safety Rules

- No real broker calls.
- No real-money or live-money operation.
- No submitted API keys, `.env`, paid datasets, or real account exports.
- No hidden dependency on network availability for default CI/L1 tests.
- AI cannot buy, sell, place orders, change parameters, bypass risk controls, or generate executable trade decisions.
- Optional real public-data scripts, if later implemented in B005, must be manual, disabled by default, and excluded from required CI.

## B005 Handoff Requirements

B005 should implement only the global ETF backtest MVP unless a later Planner changes scope. It should consume these B004 documents and preserve the following defaults:

- Fixture/mock-first data path.
- Local/CI-safe execution.
- No live broker or paper broker API by default.
- Reproducible data snapshot and parameter recording.
- Report outputs in JSON and Markdown.
- Guard tests for no-live, no-secret, no-broker-call, and AI no-buy/no-autoparameter behavior.
