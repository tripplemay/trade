# Python Package Boundary

## Purpose

This document defines the intended Python package boundaries for the MVP engineering foundation. It is a specification only; B004 does not create source code.

## Package Principle

The MVP should be a small, testable Python package rather than a collection of one-off scripts. Modules should make data lineage, assumptions, risk checks, and report output explicit.

## Proposed Top-Level Modules

| Module | Responsibility | MVP Boundary |
|---|---|---|
| `config` | Typed runtime configuration, environment selection, paths, feature flags | Local/CI defaults only; paper/live disabled unless explicitly authorized in later batches |
| `data` | Data schemas, fixture loaders, validation, snapshot IDs | Fixture/local file first; optional real public-data download script can be manual and disabled by default in B005 |
| `strategies` | Strategy signal generation | B005 implements only global ETF momentum; other strategies remain interfaces/docs |
| `backtest` | Event/order simulation, rebalance schedule, cost/slippage assumptions, portfolio NAV | Low-frequency daily/monthly assumptions only; no intraday/HFT engine |
| `portfolio` | Portfolio Manager: strategy budget allocation, buying-power limits, target weights, portfolio-level aggregation | Static baseline plus quarterly rebalance for MVP planning |
| `risk` | Position limits, exposure limits, drawdown checks, kill-switch decisions | Must flag or block violations in reports/tests; cannot be bypassed by AI |
| `reporting` | JSON/Markdown/optional CSV report generation | No formal frontend dashboard in MVP |
| `brokers` | Broker interface contracts and mock adapters | No live adapter execution in MVP; no real broker call by default |
| `ai` | Future risk explanation and news/filing triage boundaries | No buy/sell/order/parameter authority; prefilter before LLM |
| `audit` | Run metadata, parameter snapshots, data snapshot references | Required for reproducibility |

## Dependency Direction

Dependencies should flow inward toward simple data models and outward toward reports:

1. `config` and shared domain schemas are read by all modules.
2. `data` feeds `strategies` and `backtest`.
3. `strategies` produce signals, not orders.
4. `portfolio` / Portfolio Manager converts approved strategy targets into account-level target weights and budget-limited child-strategy inputs.
5. `risk` validates targets and results before reporting or future OMS handoff.
6. Future OMS consumes risk-approved Portfolio Manager output before broker execution.
7. `reporting` serializes outputs and must not call brokers or data vendors.
8. `brokers` cannot be imported by `strategies` in MVP.

The intended future trading chain is:

```text
Strategy signals/targets -> Portfolio Manager -> Risk -> OMS -> Broker Adapter
```

## B006 Minimum Implementation Boundary

B006 should implement only the minimal subset required for global ETF backtest MVP:

- `config` for local/CI-safe paths and parameters.
- `data` fixture/local file loader with validation and snapshot ID.
- `strategies.global_etf_momentum` signal generation.
- `backtest` monthly rebalance with T-day close signal and T+1 open default execution assumption.
- `risk` basic exposure and no-live guards.
- `reporting` JSON/Markdown outputs.

`portfolio`, `brokers`, OMS, and `ai` may be represented by explicit interfaces or stubs only when needed to preserve boundaries.

## Prohibited Couplings

- Strategy modules must not read `.env` or broker credentials.
- Reporting must not mutate data or place orders.
- AI modules must not call broker modules or alter strategy parameters.
- Backtest code must not silently download live data during required tests.
- Broker modules must not be reachable from default local/CI flows.
