# B002 Data Source and Broker Adapter Spec

## Background

B001 defined the strategy research baseline. B002 defines the infrastructure specifications required before any backtest or trading implementation begins.

The project targets a USD 100k-500k personal account, US equities, Hong Kong equities, and global ETFs. The system must support low-frequency strategies first, with strict environment isolation and no real-money testing without explicit user authorization.

## Goals

- Define the first-phase market data, fundamental data, macro data, news/filing data, and institutional-data upgrade path.
- Define a broker adapter abstraction that supports IBKR first while allowing Alpaca, Futu, Tiger, Schwab, Saxo, and other brokers later.
- Define core data entities and point-in-time policies to prevent lookahead bias.
- Define research, paper, and live environment isolation and explicit authorization rules.
- Prepare B003 global ETF backtest MVP implementation.

## User Constraints

- Capital scale: USD 100k-500k.
- Markets: US equities, Hong Kong equities, global ETFs.
- Usage: personal use first, possible external users after maturity.
- Strategy style: low-frequency and robust.
- Deployment: cloud server.
- Real broker and real-money operations require explicit user authorization.

## Scope

This batch is documentation-only. It produces specs under `docs/research/` and `docs/architecture/`.

## Out Of Scope

- Data ingestion implementation.
- Broker API implementation.
- Backtest engine implementation.
- Live trading.
- API key setup.
- Real brokerage account access.
- Real-money test execution.

## Required Documentation Standards

Each document must define:

- Purpose and scope.
- First-phase recommendation.
- Upgrade path.
- Risks and constraints.
- Explicit exclusions.
- Follow-up implementation requirements.

## Features

### F001 Data Source Selection and Procurement

Create `docs/research/01-data-source-selection.md`.

Acceptance: document covers market data, fundamentals, macro, news/filings, Hong Kong / China ETF data, institutional-data upgrade path, budget tiers, licensing risks, and first-phase recommendation.

### F002 Broker Adapter Specification

Create `docs/architecture/01-broker-adapter-spec.md`.

Acceptance: document defines unified adapter interfaces for account, positions, orders, fills, quotes, errors, rate limits, Paper/Live separation, and broker priority for IBKR, Alpaca, Futu, and Tiger.

### F003 Data Model and Point-in-Time Policy

Create `docs/architecture/02-data-model-point-in-time-policy.md`.

Acceptance: document defines core entities, time fields, adjusted prices, corporate actions, index constituents, fundamentals availability, data versioning, and anti-lookahead rules.

### F004 Environment Isolation and Real-Money Authorization

Create `docs/architecture/03-environment-isolation-and-live-authorization.md`.

Acceptance: document defines research/paper/live separation, secrets handling, explicit authorization for real broker and real-money tests, data-file Git exclusions, and audit requirements.

### F005 B002 Consistency Review

Evaluator writes a review report under `docs/test-reports/`.

Acceptance: report checks data source, broker adapter, data model, point-in-time, environment isolation, and live-authorization consistency. It must confirm no document permits unauthorized real-money testing.

## Later Batch Handoff

The next likely batch is B003 global ETF backtest MVP, which should consume:

- ETF universe definition.
- Historical daily adjusted bars.
- Trading calendar.
- Corporate action policy.
- Data quality checks.
- No broker live dependency.

## Safety Rules

- No live trading code in this batch.
- No API keys, credentials, or market data files in Git.
- No real brokerage API calls.
- No real-money testing.
- Any future L2 live-broker or real-money validation requires explicit user authorization.
