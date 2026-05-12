# Portfolio Allocation Boundary

## Purpose

This document defines the engineering boundary for portfolio-level allocation and account-level risk. It pairs with `docs/strategy/00-master-portfolio-allocation.md`.

## Responsibilities

The portfolio layer is the Portfolio Manager (PM). It converts child-strategy outputs into account-level target allocations and allocates strategy budgets / buying-power limits before any future OMS or broker handoff. It should not generate raw alpha signals itself.

The intended future chain is:

```text
Strategy signals/targets -> Portfolio Manager -> Risk -> OMS -> Broker Adapter
```

## Inputs

- Account size or notional assumption.
- Child strategy target weights or desired exposures.
- Strategy budget caps.
- Buying-power limits by strategy sleeve.
- Current allocation snapshot.
- Risk state, including drawdown state and macro-risk flags.
- Rebalance schedule.
- Tax-lot availability flag for future OMS use.

## Outputs

- Account-level target weights.
- Child-strategy budget allocations.
- Buying-power limits passed to child-strategy risk checks.
- Risk-adjusted target weights.
- Rebalance instructions for future paper/live batches.
- Risk flags and blocked-action reasons.

## MVP Planning Decisions

- Initial model: static baseline allocation plus quarterly rebalance.
- No dynamic regime allocation in MVP implementation unless a future spec explicitly adds it.
- Account-level drawdown kill switch is a required boundary and should be represented in reports/tests before any paper/live work.
- Slippage, tax, and macro filters start as explicit parameters/assumptions before becoming complex optimizers.

## B006 Boundary

B006 global ETF backtest may run as a single-strategy backtest, but its output should be compatible with the Portfolio Manager:

- Strategy ID.
- Target weights.
- Assumed strategy budget.
- Risk flags.
- Drawdown metrics.
- Slippage/cost assumptions.
- Data snapshot and parameter metadata.
- Signal timing and T+1 open execution assumption.

## Prohibited Behavior

- Portfolio layer must not call broker execution directly in MVP.
- Portfolio layer must not override risk kill switches.
- AI cannot modify child-strategy budgets or rebalance schedules.
- Tax-aware logic must not claim personalized tax advice.
- Future OMS integration must preserve tax-lot identity rather than only average cost.
