# B010 Risk Parity Backtest MVP Spec

## Background

B006 delivered the first Global ETF Momentum backtest MVP. B007 hardened backtest quality. B008 improved the research universe, fixtures, data quality labels, and research limitations. B009 added a manual public data import and local snapshot workflow so research runs can reference auditable data snapshots without weakening offline CI and safety guards.

The MVP PRD milestone after Global ETF Momentum is a risk parity / volatility target strategy. The master allocation document also identifies risk parity as the core stabilizer sleeve, initially planned around 30% of the portfolio. B010 should implement the first safe, fixture-first risk parity backtest MVP while reusing the data, quality, reporting, and safety boundaries established in B006-B009.

## Goal

Implement a minimal, testable Risk Parity / Volatility Target backtest MVP using ETF daily data, inverse volatility weighting, no leverage, monthly rebalancing, explicit T-day signal / T+1 execution assumptions, quality limitations, and deterministic JSON/Markdown reports.

This batch should create the second core strategy research path, not a broker, paper trading, live execution, optimizer platform, or investment recommendation.

## Hard Decisions

- First version uses inverse volatility weighting only. ERC, minimum variance, and constrained optimizers are out of scope unless explicitly added later.
- No leverage. Exposure scaling must be capped at `<= 1.0`; unused exposure goes to defensive cash-like allocation such as `SGOV` or an equivalent cash placeholder.
- Default CI and L1 tests remain fixture/mock-first and offline.
- Risk parity may reuse B009 local snapshots only through explicit configuration. Missing snapshots fail closed and must not trigger implicit download.
- No broker, paper/live trading, real account data, secrets, paid data, AI execution, cloud deployment, or frontend dashboard.
- Reports must label research limitations and data quality conditions; public-best-effort/non-PIT data remains research-only.

## Reference Documents

- `docs/prd/mvp-prd.md`
- `docs/strategy/00-master-portfolio-allocation.md`
- `docs/strategy/02-risk-parity-vol-target.md`
- `docs/specs/B009-public-data-snapshot-mvp-spec.md`
- `docs/specs/B008-research-grade-data-expansion-spec.md`
- `docs/specs/B007-backtest-quality-hardening-spec.md`
- `docs/specs/B006-global-etf-backtest-mvp-spec.md`
- `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`
- `docs/engineering/testing-and-fixture-policy.md`
- `docs/engineering/config-and-environment-policy.md`
- `docs/engineering/no-live-safety-guards.md`
- `docs/engineering/backtest-report-schema.md`
- `docs/engineering/pit-data-degradation-policy.md`

## Proposed Implementation Shape

### Strategy Configuration

Add a risk parity strategy configuration with explicit defaults:

- strategy id / name
- universe or ticker list
- volatility lookback window, supporting at least 60/120/252 trading days
- default lookback of 120 or 252 trading days
- target volatility, such as 8%-10%, as a research parameter
- defensive asset or cash placeholder, such as `SGOV`
- monthly rebalance frequency
- per-asset and asset-class caps where practical
- no leverage / max exposure scale `1.0`

### Return And Volatility Estimation

Compute daily returns from adjusted close when available. Estimate annualized volatility from rolling daily returns using `sqrt(252)`. Missing or insufficient lookback data must be explicit in results or warnings rather than silently ignored.

### Inverse Volatility Weighting

Implement the initial weight algorithm:

```text
raw_weight_i = 1 / volatility_i
weight_i = raw_weight_i / sum(raw_weight)
```

Then apply guardrails:

- exclude assets with missing or invalid volatility
- cap weights where configured
- normalize remaining weights
- apply `exposure_scale = min(target_vol / estimated_portfolio_vol, 1.0)` when target vol is used
- allocate unused exposure to defensive asset / cash placeholder

### Backtest Workflow

Provide a monthly risk parity backtest workflow using the existing data and reporting architecture where practical:

- T-day close data estimates returns/volatility and target weights
- T+1 open or existing execution-price assumption applies execution
- transaction cost and slippage assumptions are explicit
- equity curve, rebalance trace, target weights, turnover, and costs are recorded
- data snapshot / manifest references and quality limitations are preserved

### Reporting And Comparison

JSON/Markdown reports should expose:

- strategy id and config reference
- snapshot id / manifest reference when present
- annualized return
- annualized volatility
- Sharpe
- maximum drawdown
- turnover
- transaction costs
- weight history
- realized volatility vs target volatility when practical
- basic comparison against available baseline(s), such as static multi-asset, SPY, 60/40, or Global ETF Momentum fixture output if already available without overbuilding
- research limitations and data quality flags

### Safety And Regression

All existing safety boundaries remain mandatory:

- no live trading
- no paper broker
- no broker export/import
- no secret lookup
- no default network dependency
- no AI-driven trade action or parameter change
- no generated market data committed
- deterministic fixture-based CI tests

## Feature Requirements

### F001 Risk Parity Strategy Configuration

Executor: generator.

Add a minimal risk parity configuration and strategy boundary based on `docs/strategy/02-risk-parity-vol-target.md`. The first version must use inverse volatility weighting only, no leverage, and explicit defensive asset/cash allocation semantics.

### F002 Volatility And Return Estimation

Executor: generator.

Implement daily return and annualized volatility estimation from adjusted close or equivalent fixture data. Support at least 60/120/252 day lookback windows, and fail or warn explicitly for insufficient or invalid data.

### F003 Inverse Volatility Weighting And Exposure Scaling

Executor: generator.

Implement inverse volatility weights with deterministic guardrails: invalid vol exclusion, optional weight caps where practical, normalization, target volatility exposure scaling capped at `1.0`, and leftover allocation to defensive asset/cash placeholder.

### F004 Risk Parity Backtest Workflow

Executor: generator.

Add a monthly risk parity backtest workflow that uses T-day close signal calculation and T+1 execution assumptions, records rebalance trace, equity curve, turnover, costs, target weights, snapshot references, and quality limitations.

### F005 Risk Parity Reports And Baseline Comparison

Executor: generator.

Extend or add JSON/Markdown reports for risk parity outputs, including core performance metrics, weight history, realized vs target volatility where practical, transaction costs, research limitations, and at least one simple baseline comparison without adding live or external dependencies.

### F006 Safety Guard And Workflow Regression

Executor: generator.

Add regression coverage proving risk parity remains fixture/mock-first by default and does not introduce network, secret, broker, paper/live, AI-trading, generated-data-commit, or frontend/dashboard dependencies. Required local checks must pass: pytest, ruff, compileall, mypy.

### F007 Independent Evaluation

Executor: codex.

Evaluator runs local/CI-safe L1 verification. It must confirm B010 implements a minimal risk parity backtest MVP, reports explicit research limitations, preserves snapshot/data-quality semantics, and keeps all no-live/no-secret/no-network-by-default/no-broker/no-paper/no-AI safety guards.

## Acceptance Summary

B010 is complete only when:

- Required checks pass locally: pytest, ruff, compileall, mypy.
- Risk parity configuration exists and is separate from Global ETF Momentum.
- Daily return and volatility estimation are covered by tests.
- Inverse volatility weighting is deterministic, no-leverage, and handles invalid/insufficient data explicitly.
- Monthly backtest records T-day signal and T+1 execution assumptions.
- Reports include risk parity metrics, weight history, costs, snapshot/data quality references, and research limitations.
- Default CI remains fixture/mock-first and offline.
- No broker, paper/live execution, secret lookup, AI trading, frontend dashboard, or generated market data commit path is introduced.
- Evaluator signs off F007 with reports under `docs/test-reports/`.
