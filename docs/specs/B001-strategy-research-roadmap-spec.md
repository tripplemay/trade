# B001 Strategy Research Roadmap Spec

## Background

The project aims to build an AI-driven quantitative trading system for global securities markets. The initial target user is a personal account with USD 100k-500k capital, focused on US equities, Hong Kong equities, and global ETFs.

The first batch is documentation-only. Its purpose is to define the strategy research baseline before any trading code, broker integration, or live execution feature is implemented.

## Goals

- Establish the first set of strategy research documents.
- Keep the strategy scope aligned with low-frequency, robust, risk-controlled trading.
- Define data, backtest, risk, and live-readiness requirements for each strategy family.
- Prepare a consistent foundation for later implementation batches.

## User Constraints

- Capital scale: USD 100k-500k.
- Markets: US equities, Hong Kong equities, global ETFs.
- Usage: personal use first, possible external users after maturity.
- Strategy style: low-frequency and robust.
- Deployment: cloud server.
- Broker support: must allow multiple broker adapters over time, with IBKR as a likely primary broker and Alpaca/Futu/Tiger as optional adapters.

## Strategy Scope

This batch covers five strategy documents:

- Global ETF momentum rotation.
- Risk parity and volatility targeting.
- US quality momentum / multi-factor stock selection.
- Hong Kong / China ETF small-allocation strategy.
- AI news and filing risk filter.

## Out Of Scope

- Trading engine implementation.
- Backtest engine implementation.
- Broker API implementation.
- Live trading.
- High-frequency strategies.
- Options strategies.
- Leveraged ETF or inverse ETF strategies.
- External customer productization.

## Required Documentation Standards

Every strategy document must include:

- Strategy hypothesis.
- Tradable universe.
- Data requirements.
- Signal definition.
- Portfolio construction.
- Rebalance frequency.
- Risk controls.
- Transaction cost and slippage assumptions.
- Backtest requirements.
- Robustness tests.
- Paper trading criteria.
- Live trading entry criteria.
- Strategy pause conditions.

## Features

### F001 Global ETF Momentum Rotation

Create `docs/strategy/01-global-etf-momentum-rotation.md`.

Acceptance: document includes asset universe, momentum signal, trend filter, rebalance frequency, portfolio construction, risk limits, backtest requirements, and live-readiness criteria.

### F002 Risk Parity / Volatility Targeting

Create `docs/strategy/02-risk-parity-vol-target.md`.

Acceptance: document includes asset classes, volatility estimation, inverse-volatility or risk-parity weighting, target volatility, risk limits, backtest metrics, and live-readiness criteria.

### F003 US Quality Momentum

Create `docs/strategy/03-us-quality-momentum.md`.

Acceptance: document includes stock universe, factor definitions, portfolio construction, industry constraints, data requirements, backtest pitfalls, and live-readiness criteria.

### F004 Hong Kong / China ETF Small Allocation

Create `docs/strategy/04-hk-china-etf-small-allocation.md`.

Acceptance: document explains allocation limits, ETF-first principle, liquidity constraints, policy risk, FX considerations, and backtest requirements.

### F005 AI News / Filing Risk Filter

Create `docs/strategy/05-ai-news-filing-risk-filter.md`.

Acceptance: document states AI is only for research, explanation, and risk filtering; it must not directly trigger live buys. It includes inputs, outputs, confidence, audit, and human-confirmation requirements.

### F006 Strategy Documentation Consistency Review

Evaluator writes a review report under `docs/test-reports/`.

Acceptance: report checks consistency across the five strategy documents for capital allocation, risk limits, data assumptions, paper trading requirements, and live-readiness gates.

## Later Batch Handoff

The next likely batches are:

- B002 data source and broker adapter specification.
- B003 global ETF backtest MVP.
- B004 risk parity and portfolio-level risk controls.
- B005 paper trading and broker adapter integration.

## Safety Rules

- No live trading code in this batch.
- No secrets or API keys in Git.
- No market data files in Git.
- AI outputs may support research and risk filtering only.
- Any future real broker or real-money testing requires explicit user authorization.
