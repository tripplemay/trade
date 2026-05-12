# B005 Pre-Backtest Architecture Adjudication Spec

## Background

B004 established the core engineering foundation and was independently signed off. After that signoff, a second independent report, `docs/research/prd-architecture-audit-2026-05-12.md`, reviewed the MVP PRD, architecture documents, and strategy documents. It found that the existing architecture is strong, but several decisions should be adjudicated before the Global ETF Backtest MVP implementation begins.

## Goal

Absorb the PRD/architecture audit findings into explicit pre-implementation constraints for the next implementation batch.

B005 is a pure documentation/specification adjudication batch. It does not implement product code, package scaffolding, broker adapters, data providers, OMS, AI pipelines, frontend, deployment, migrations, or live/paper trading.

The Global ETF Backtest MVP implementation is deferred to B006.

## Reference Documents

- `docs/prd/mvp-prd.md`
- `docs/specs/B004-core-engineering-foundation-spec.md`
- `docs/architecture/01-broker-adapter-spec.md`
- `docs/architecture/02-data-model-point-in-time-policy.md`
- `docs/architecture/03-environment-isolation-and-live-authorization.md`
- `docs/research/strategy-audit-report-2026-05-12.md`
- `docs/research/prd-architecture-audit-2026-05-12.md`

## Architecture Decisions

### AD-001 Portfolio Manager Layer

The system must explicitly include a Portfolio Manager layer between strategy outputs and OMS/broker execution:

```text
Strategy signals/targets -> Portfolio Manager -> Risk -> OMS -> Broker Adapter
```

Portfolio Manager is responsible for strategy budget allocation, buying-power limits, account-level target weights, and account-level risk state. Child strategies must not independently assume full account buying power.

### AD-002 B006 Execution Price Assumption

B006 Global ETF Backtest MVP must use T-day close data for signal generation and T+1 open price as the default execution price assumption.

`T Close` must not be used as the default execution price for a signal generated after the T-day close. Reports must record signal price, execution price, execution timing, and slippage/cost assumptions.

### AD-003 PIT Data Degradation

High-quality point-in-time fundamentals are not assumed available in MVP. Before such data is licensed or verified, the US quality/momentum multi-factor strategy must degrade to price/volume-derived factors only.

Any non-PIT fundamental data used for research must be marked as degraded, delayed by a conservative availability lag, and excluded from serious performance claims.

### AD-004 Tax-Lot And OMS Boundary

Future broker/OMS design must not rely only on average cost. It must preserve space for tax lots, lot IDs, acquisition dates, quantities, and cost basis.

B006 does not implement tax optimization or provide tax advice. It only preserves interface boundaries so future taxable-account workflows do not require model rewrites.

### AD-005 AI Filing Prefilter

Future AI filing/news risk analysis must use a deterministic prefilter before LLM calls. Acceptable prefilters include keyword rules, traditional NLP, or Bloom-filter-like membership checks.

LLM calls must be reserved for documents that match risk criteria. AI must not buy, sell, place orders, change strategy parameters, allocate capital, or override risk controls.

## Feature Requirements

### F001 Portfolio Manager Boundary

Executor: generator.

Update B004 engineering documents to name Portfolio Manager explicitly and define the Strategy -> PM -> OMS -> Broker Adapter chain.

### F002 T+1 Open Execution Assumption

Executor: generator.

Update report schema and B006 handoff language to require T+1 Open as default execution price and to record signal/execution price fields.

### F003 PIT Data Degradation Policy

Executor: generator.

Create `docs/engineering/pit-data-degradation-policy.md`.

### F004 Tax-Lot / OMS Boundary

Executor: generator.

Create `docs/engineering/oms-tax-lot-boundary.md` and add cross-references from portfolio/broker boundaries.

### F005 AI Filing Prefilter Policy

Executor: generator.

Create `docs/engineering/ai-filing-prefilter-policy.md`.

### F006 Independent Review

Executor: codex.

Evaluator reviews B005 documents against B001-B004 and both independent reports. The review must verify B005 stays documentation-only and does not authorize live trading, real broker calls, external API hard dependency, hidden secret dependency, formal frontend implementation, or tax advice.

## B006 Handoff

B006 should implement Global ETF Backtest MVP with these hard constraints:

- Fixture/mock-first required tests.
- No live broker, no paper broker, no hidden secrets, no required network.
- T-day close signal generation.
- T+1 open default execution assumption.
- JSON/Markdown report records signal/execution timing and price assumptions.
- Output is compatible with Portfolio Manager fields.
- No fundamental multi-factor implementation unless PIT constraints are satisfied or degraded mode is explicit.
- AI modules, if stubbed, cannot make trading or parameter decisions.
