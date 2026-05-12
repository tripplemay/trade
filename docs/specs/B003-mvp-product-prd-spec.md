# B003 MVP Product PRD Spec

## Background

B001 established the strategy research roadmap. B002 established data-source, broker-adapter, point-in-time, and environment-isolation specifications. Before building the core engineering foundation and backtest MVP, the project needs a product-level MVP PRD to anchor engineering decisions to product scope.

## Goal

Produce a clear MVP PRD for the AI-driven quantitative trading system.

The PRD must define what the first usable product is, what it is not, and how later engineering batches should be judged against product outcomes.

## Product Assumptions

- User: primarily the project owner / personal quant user.
- Capital scale: USD 100k-500k.
- Markets: US equities, Hong Kong equities, global ETFs.
- Strategy style: low-frequency, robust, risk-controlled.
- Deployment: cloud server eventually, but MVP can start with local/CI execution and later paper deployment.
- Broker: IBKR primary long-term path; Alpaca/Futu/Tiger optional future adapters.
- AI: research, explanation, and risk filtering only; no direct live buy decisions.

## Scope

Planner creates `docs/prd/mvp-prd.md` as the product specification for later Generator implementation batches.

The document must synthesize B001 and B002, not supersede them. If conflict is found, Planner should preserve B001/B002 constraints and note the ambiguity in the PRD open questions.

## Required PRD Sections

The MVP PRD must include:

- Product background.
- User persona.
- Target capital scale.
- MVP objective.
- MVP scope.
- Non-MVP scope.
- Core user journeys.
- Strategy scope.
- Data scope.
- Backtest scope.
- Paper Trading scope.
- Risk-control scope.
- AI capability boundary.
- Broker boundary.
- Frontend boundary.
- Cloud deployment boundary.
- Security and compliance requirements.
- Success metrics.
- Acceptance criteria.
- Milestones.
- Risks and mitigations.
- Open questions.

## Feature Requirements

### F001 MVP PRD Main Document

Executor: planner.

Create `docs/prd/mvp-prd.md` with product background, user persona, target capital scale, MVP objectives, MVP scope, non-MVP scope, core features, constraints, and success metrics.

### F002 User Journeys and Feature Boundaries

Executor: planner.

Add user journeys covering:

- Data import / data refresh.
- Strategy configuration.
- Backtest execution.
- Report review.
- Risk check review.
- Paper Trading readiness.

The PRD must state that a formal frontend dashboard is not implemented in MVP, but frontend architecture can be planned later.

### F003 Acceptance Criteria and Milestones

Executor: planner.

Add MVP acceptance criteria and milestone mapping. It must make clear that B004 should be core engineering foundation and B005 should be global ETF backtest MVP unless the plan changes.

### F004 Non-MVP Scope and Risk List

Executor: planner.

Explicitly exclude:

- Real-money automated live trading.
- Multi-user productization.
- Complete frontend dashboard.
- High-frequency trading.
- Options strategies.
- Institution-grade data as a hard MVP dependency.
- AI autonomous trading.
- Live broker adapter execution.

Add product, data, compliance, technical, and trading risks.

### F005 Independent PRD Consistency Review

Executor: codex.

Evaluator reviews `docs/prd/mvp-prd.md` against B001 and B002. It must verify that the MVP PRD does not expand scope into unauthorized live trading or premature frontend implementation.

## Out Of Scope

- Implementing code.
- Setting up CI.
- Creating frontend app.
- Creating cloud infrastructure.
- Connecting broker or data vendor APIs.
- Running live or paper broker tests.

## Safety Rules

- The PRD must preserve the rule that real broker/live-money testing requires explicit user authorization.
- The PRD must preserve AI boundaries from B001.
- The PRD must not require paid institutional data before MVP.
- The PRD must not require a formal frontend dashboard before backtest outputs are stable.
