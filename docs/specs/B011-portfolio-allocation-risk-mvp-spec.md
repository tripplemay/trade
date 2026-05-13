# B011 Portfolio Allocation And Risk MVP Spec

## Background

B006 delivered the Global ETF Momentum backtest MVP. B007 hardened backtest quality. B008 expanded research-grade data. B009 added local public data snapshots. B010 implemented the Risk Parity / Volatility Target backtest MVP. With two core sleeves now signed off, the system needs a Master Portfolio Manager that combines them at the account level, manages allocation budgets, and exposes account-level risk controls.

The MVP PRD §12 milestone after Risk Parity is "Portfolio Allocation and Risk". The master allocation document already defines core-satellite weights, the Portfolio Manager role, an account-level drawdown kill-switch, and the rule that account-level controls must override child-strategy targets. B011 should implement the first safe, fixture-first Portfolio Allocation MVP that combines Global ETF Momentum and Risk Parity under a static planning allocation, exposes a quarterly rebalance workflow, and adds the account-level 15% drawdown kill-switch with explicit human-review semantics.

## Goal

Implement a minimal, testable Master Portfolio Allocation MVP that:

- Combines Global ETF Momentum (B006) and Risk Parity (B010) under a static planning allocation with reserved interface stubs for future satellite sleeves.
- Provides a quarterly rebalance workflow that consumes child target weights at quarter-ends, applies T-day close signal / T+1 open execution assumptions, and records rebalance trace, turnover, costs, child contributions, and portfolio-level metrics.
- Implements an account-level 15% drawdown kill-switch that freezes new non-defensive risk-asset exposure, preserves existing positions, requires explicit human-review-style clearance, and surfaces state in reports.
- Outputs combined JSON/Markdown reports with aggregated metrics, per-child contributions, account-level risk flags, research limitations, and a calculated multi-asset baseline (absorbing backlog item `BL-B010-S2`).
- Adds safety guard regression coverage proving the Master Portfolio path remains fixture/mock-first and introduces no new network, secret, broker, paper/live, AI-trading, generated-data-commit, or frontend/dashboard dependencies.
- Closes with independent Codex L1 verification.

This batch creates the account-level orchestration path, not a broker, paper-trading, live-execution, optimizer platform, or investment-advisory product.

## Hard Decisions

- First implementation combines only B006 momentum and B010 risk parity as core sleeves. US Quality Momentum and HK-China sleeves are interface stubs (reserved configuration entries plus pass-through cash/defensive allocation), not implemented strategies.
- Static planning weights from `docs/strategy/00-master-portfolio-allocation.md`: momentum 40%, risk parity 30%, US quality satellite stub 20%, HK-China satellite stub 10%. Unimplemented stub sleeves' weights are held as defensive/cash placeholder.
- Rebalance frequency at Master level is quarterly. Spec records monthly cadence as a future option. Quarter-end is the last business day of the calendar quarter in the fixture; T-day close / T+1 open execution assumptions are reused from B006/B010.
- Child strategies retain their independent monthly cadences and independent reports. Master consumes only their quarter-end target weights.
- Account-level 15% drawdown kill-switch (from high-water mark) freezes new non-defensive risk-asset exposure. Existing non-defensive positions are retained. Subsequent quarter-ends may not increase any non-defensive target weight while triggered. Clearance requires an explicit config or runtime parameter that simulates human-review acknowledgment. Backtest reports must show triggered state, breach high-water mark, and a `human_review_required` flag in the report payload.
- Account-level risk controls override child-strategy targets at the Master layer only; child strategies' internal risk rules remain intact and unmodified.
- Default CI and L1 tests remain fixture/mock-first and offline.
- Master Portfolio path may reuse B009 local snapshots only through explicit configuration. Missing snapshots fail closed and must not trigger implicit download.
- No broker, paper/live trading, real account data, secrets, paid data, AI execution, cloud deployment, or frontend dashboard.
- Reports must label research limitations and data quality conditions; public-best-effort/non-PIT data remains research-only and explicitly never claims paper or live execution.
- BL-B010-S2 (risk parity baseline 替换为可计算 baseline) is absorbed here as the portfolio-level calculated baseline (e.g. static 60/40 multi-asset quarterly rebalance) and is also referenced as B010 baseline followup in reports.

## Reference Documents

- `docs/prd/mvp-prd.md`
- `docs/strategy/00-master-portfolio-allocation.md`
- `docs/strategy/01-global-etf-momentum-rotation.md`
- `docs/strategy/02-risk-parity-vol-target.md`
- `docs/specs/B010-risk-parity-backtest-mvp-spec.md`
- `docs/specs/B009-public-data-snapshot-mvp-spec.md`
- `docs/specs/B008-research-grade-data-expansion-spec.md`
- `docs/specs/B007-backtest-quality-hardening-spec.md`
- `docs/specs/B006-global-etf-backtest-mvp-spec.md`
- `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`
- `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`
- `docs/engineering/testing-and-fixture-policy.md`
- `docs/engineering/config-and-environment-policy.md`
- `docs/engineering/no-live-safety-guards.md`
- `docs/engineering/backtest-report-schema.md`
- `docs/engineering/pit-data-degradation-policy.md`

## Proposed Implementation Shape

### Master Portfolio Configuration

Add a master portfolio configuration with explicit defaults:

- portfolio id / name
- child sleeves list with: id, type (`implemented_strategy` | `satellite_stub`), strategy reference, planning weight, role label
- planning weights summing to `1.0` (momentum 0.40, risk_parity 0.30, satellite_us_quality 0.20, satellite_hk_china 0.10)
- defensive asset / cash placeholder reused from B010 semantics
- rebalance frequency `quarterly` (monthly recorded as future option, not implemented)
- account-level drawdown threshold `0.15` from rolling high-water mark
- account-level controls section: kill-switch behavior, clearance flag, report disclosure requirements
- no leverage / portfolio max exposure scale `<= 1.0`

### Portfolio Combiner And Rebalance Workflow

Provide a quarterly Master rebalance workflow:

- At each calendar quarter end (last business day in fixture), consume each implemented child's then-current target weights.
- For satellite stubs and any unimplemented-but-reserved sleeves, allocate to defensive / cash placeholder.
- Apply child planning weight: `portfolio_weight_i = child_planning_weight * child_target_weight_i_normalized`.
- Aggregate per-asset weights across children (defensive placeholder absorbs unused exposure).
- Execute at T+1 open using existing execution-price assumption.
- Record portfolio rebalance trace, equity curve, turnover, transaction costs, per-child contributions, and snapshot references.
- Between rebalances, no portfolio-level action; child-level monthly cadence is preserved but ignored by the Master between quarter-ends.

### Account-Level Drawdown Kill-Switch

- Maintain rolling high-water mark of portfolio equity in the backtest.
- When `equity / hwm - 1 <= -0.15`, set `kill_switch_active = true`.
- While active:
  - At the next quarter rebalance, do not increase any non-defensive sleeve's target weight relative to the prior rebalance.
  - Existing positions are not force-liquidated; the Master may still execute a no-op rebalance and refresh the defensive placeholder.
  - Reports include `kill_switch_active: true`, `kill_switch_triggered_at: <date>`, `kill_switch_trigger_drawdown: <value>`, and `human_review_required: true`.
- Clearance requires an explicit clearance entry in the portfolio config or runtime parameter, simulating human-review acknowledgment. The backtest harness records clearance events in the rebalance trace.
- Account-level controls run after child target weights are combined; child-level risk rules are not modified.

### Combined Reporting And Calculated Baseline

JSON/Markdown reports must expose:

- portfolio id and config reference
- planning weights and effective weights at each rebalance
- per-child contribution metrics (cumulative return contribution, weight, turnover)
- aggregated equity curve, annualized return, annualized volatility, Sharpe, maximum drawdown, turnover, transaction costs
- snapshot id / manifest reference when present
- account-level risk flags: drawdown breach, kill-switch state, human-review-required
- research limitations and data quality flags
- a calculated multi-asset baseline (e.g. static 60/40 ETF/defensive quarterly rebalance using the existing fixture/snapshot, T close / T+1 open) reused both as the portfolio baseline and as the deferred B010 calculated-baseline followup
- explicit statement that reports are research-only and never claim paper/live execution

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
- no frontend dashboard, browser E2E, React/Next.js, Playwright, Cypress

Regression must specifically prove:

- Master Portfolio module imports contain no network/credential/broker/AI/public-import/frontend dependencies.
- Master pipeline runs offline without env, secrets, or network.
- Master backtest does not write to `trade/data/fixtures/` or commit generated market data.
- Reports never claim paper or live execution at the portfolio layer.
- Default parameters carry no broker/live language.
- Account-level kill-switch behavior is deterministic and visible in report payload.
- Public-import stub remains opt-in and is not auto-invoked by Master pipeline.

## Feature Requirements

### F001 Master Portfolio Configuration

Executor: generator.

Add a Master Portfolio configuration and boundary based on `docs/strategy/00-master-portfolio-allocation.md`. The first version must combine B006 momentum and B010 risk parity as implemented core sleeves, reserve satellite (US quality, HK-China) interface stubs that fall through to defensive/cash placeholder, expose static planning weights summing to `1.0`, declare quarterly rebalance frequency, and declare account-level drawdown threshold and kill-switch semantics.

### F002 Quarterly Portfolio Combiner And Rebalance Workflow

Executor: generator.

Implement a quarterly Master rebalance workflow that consumes child target weights at quarter-ends, applies planning weights to derive portfolio weights, aggregates per-asset weights, executes under T-day close / T+1 open assumptions, and records rebalance trace, equity curve, turnover, transaction costs, per-child contributions, and snapshot references. Between rebalances, the Master must not act on intra-quarter child signals.

### F003 Account-Level Drawdown Kill-Switch

Executor: generator.

Implement a deterministic 15% account-level drawdown kill-switch from rolling high-water mark. When triggered, the Master must not increase any non-defensive sleeve's target weight at the next rebalance, must retain existing positions, must require explicit clearance via config/runtime parameter to lift, and must surface `kill_switch_active`, `kill_switch_triggered_at`, `kill_switch_trigger_drawdown`, and `human_review_required` in the report payload. Account-level controls must not modify child-level risk rules.

### F004 Portfolio Reports And Calculated Baseline

Executor: generator.

Add JSON/Markdown portfolio reports including aggregated equity curve, annualized return, annualized volatility, Sharpe, maximum drawdown, turnover, transaction costs, per-child contributions, planning vs effective weights, snapshot references, account-level risk flags, and explicit research limitations. Add a calculated multi-asset baseline (e.g. static 60/40 ETF/defensive quarterly rebalance using existing fixtures/snapshots and T-close / T+1 open assumptions) referenced both as the portfolio baseline and as the deferred B010 calculated-baseline followup (`BL-B010-S2`). Reports must never claim paper or live execution.

### F005 Safety Guard And Workflow Regression

Executor: generator.

Add regression coverage proving Master Portfolio remains fixture/mock-first and does not introduce network, secret, broker, paper/live, AI-trading, generated-data-commit, or frontend/dashboard dependencies. Account-level kill-switch behavior must be deterministic and visible in the report payload. Required local checks must pass: pytest, ruff, compileall, mypy.

### F006 Independent Evaluation

Executor: codex.

Evaluator runs local/CI-safe L1 verification. It must confirm B011 implements the minimal Master Portfolio Allocation MVP, that combined reports include calculated baseline and account-level risk flags, that the kill-switch triggers and clears deterministically, that snapshot/data-quality semantics are preserved, and that all no-live / no-secret / no-network-by-default / no-broker / no-paper / no-AI safety guards remain intact. The signoff must explicitly note absorption of `BL-B010-S2`.

## Acceptance Summary

B011 is complete only when:

- Required checks pass locally: pytest, ruff, compileall, mypy.
- Master Portfolio configuration exists and is separate from individual strategy configs; planning weights sum to `1.0`; satellite stubs fall through to defensive/cash.
- Quarterly portfolio combiner and rebalance workflow consume child quarter-end weights and record full rebalance trace, equity curve, turnover, costs, contributions, and snapshot references.
- Account-level 15% drawdown kill-switch triggers, blocks non-defensive increases, retains existing positions, requires explicit clearance, and surfaces state in report payload.
- Portfolio reports include aggregated metrics, per-child contributions, planning vs effective weights, account-level risk flags, research limitations, and a calculated multi-asset baseline (absorbing `BL-B010-S2`).
- Master Portfolio path remains fixture/mock-first and offline by default.
- No broker, paper/live execution, secret lookup, AI trading, frontend dashboard, or generated market data commit path is introduced.
- Evaluator signs off F006 with reports under `docs/test-reports/`, explicitly noting `BL-B010-S2` absorption.
