# AI Quant Trading System

AI-driven quantitative trading research and execution system for global securities markets.

## Project Scope

- Initial capital assumption: USD 100k-500k personal account.
- Initial markets: US equities, Hong Kong equities, and global ETFs.
- Strategy preference: low-frequency, robust, risk-controlled strategies.
- Deployment target: cloud server.
- Collaboration framework: Harness / Triad Workflow with Planner, Generator, and Evaluator roles.

## First-Phase Strategy Focus

- Global ETF momentum rotation.
- Risk parity and volatility targeting.
- US quality momentum and multi-factor stock selection.
- Hong Kong / China ETF small-allocation strategy.
- AI-assisted news and filing risk filter.

## Safety Principles

- Strategy documentation must exist before implementation.
- Backtests must define data source, cost model, slippage, rebalance timing, and anti-lookahead rules.
- Live trading features must support paper trading first.
- AI output must not directly trigger unrestricted live orders.
- All broker orders must pass through unified risk checks.
- API keys, market data files, database files, and secrets must not be committed.

## Harness Workflow

This repository uses the Triad Workflow state machine:

```text
new -> planning -> building -> verifying -> fixing <-> reverifying -> done
```

Core files:

- `progress.json`: current batch state.
- `features.json`: current batch feature list.
- `backlog.json`: deferred requirements.
- `docs/specs/`: Planner-authored specifications.
- `docs/test-cases/`: Evaluator test cases.
- `docs/test-reports/`: Evaluator reports and signoff.
- `.auto-memory/`: shared project memory.

## Current Batch

`B001-strategy-research-roadmap` defines the initial strategy research documentation scope.
