# Testing and Fixture Policy

## Purpose

This document defines the default test and fixture policy for B005 and later implementation batches.

## Test Layers

| Layer | Environment | Required For B005 | Covers | Excludes |
|---|---|---:|---|---|
| L1 local/CI | `local`, `ci` | Yes | schema, fixture loading, strategy signals, backtest math, reports, no-live guards | real broker, paid data, external API availability |
| L2 manual research | `research` | Optional later | optional public data sanity checks | required CI, paper/live execution |
| L3 paper/live | `paper`, `live` | No | future broker flows after authorization | MVP |

## Fixture Requirements

Fixtures should be small, committed, deterministic, and safe to redistribute. They may be synthetic or public sample data if licensing allows. They must include enough variation to test:

- Trading calendar gaps.
- Missing values.
- Adjusted close behavior.
- Monthly rebalance boundaries.
- Defensive asset switching.
- Risk-limit violations.
- Report reproducibility.

## Required Tooling

- `pytest` for unit and integration-style L1 tests.
- `ruff` for lint and formatting policy.
- `compileall` for basic syntax/import validation.
- `mypy` as the intended type-checking baseline. If not enabled in the first implementation batch, B005 must explicitly document the staged adoption plan.

## Guard Tests

Implementation acceptance should include tests that prove:

- Required tests pass without `.env`.
- Required tests pass without network.
- Broker calls are not reachable from default backtest paths.
- AI modules cannot place orders or change strategy parameters.
- Backtest outputs record data snapshot ID and parameter hash or equivalent metadata.
- Risk violations are surfaced in JSON/Markdown reports.

## Optional Public Data Scripts

Optional public data download scripts may be useful for manual research, but they must not become required CI dependencies. They should write to ignored local paths unless a later spec explicitly approves committed sample data.
