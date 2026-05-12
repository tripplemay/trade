# Master Portfolio Allocation

## Purpose

This strategy-level document defines the initial account-level allocation framework for a USD 100k-500k personal quantitative trading account. It responds to independent audit findings that the system needs a Master Portfolio Manager before single-strategy implementation becomes too isolated.

## Account Objective

The account should prioritize robust, low-frequency, risk-controlled compounding over maximum standalone strategy alpha. The allocation framework should be understandable, auditable, and suitable for manual oversight before any paper/live automation.

## Core-Satellite Structure

| Sleeve | Role | Initial Planning Weight | Notes |
|---|---|---:|---|
| Global ETF momentum | Core trend engine | 40% | First B005 implementation target |
| Risk parity / volatility target | Core stabilizer | 30% | Planned after ETF momentum MVP |
| US quality momentum / multi-factor | Satellite alpha | 20% | Tax drag requires later tax-aware design |
| Hong Kong / China ETF sleeve | Satellite regional exposure | 10% | Prefer US-listed ADR/ETF proxies for sub-USD 500k accounts |

These weights are planning defaults, not live trading instructions.

## Portfolio Manager Role

The Master Portfolio Manager owns strategy budgets and buying-power limits. Child strategies receive budget-constrained inputs and must not assume access to the full account.

Future execution flow:

```text
Strategy signals/targets -> Portfolio Manager -> Risk -> OMS -> Broker Adapter
```

## Rebalancing Policy

- Initial model: static baseline plus quarterly rebalance.
- Rebalance should consider transaction costs and tax friction before future paper/live use.
- Dynamic regime allocation is a future enhancement, not an MVP requirement.

## Account-Level Risk Controls

- Account-level drawdown kill switch should be modeled before paper/live trading.
- Planning threshold: if total account equity drawdown from high-water mark exceeds 15%, block new non-defensive risk-asset exposure until a human review clears the state.
- Child strategies may have local risk rules, but account-level controls override child-strategy targets.
- Risk controls must be visible in reports rather than hidden in execution code.

## Execution Frictions

Future backtests and paper/live planning should account for:

- Slippage and bid/ask spread assumptions.
- T-day close signal and T+1 open execution gaps.
- Optional MOC/TWAP/VWAP planning for later execution research.
- Tax drag for taxable accounts, especially short-term gains in high-turnover equity strategies.

## Macro And Regime Filters

Macro filters should begin as explicit model inputs, not implicit discretionary overrides. Candidate flags include:

- VIX risk-off threshold.
- Yield-curve or rate-shock regime.
- Inflation-sensitive long-bond constraint.

B005 may include basic configurable macro-filter placeholders for global ETF momentum, but broad dynamic allocation is later scope.

## AI Risk Overlay Boundary

AI can support future news/filing risk triage and report explanation. It cannot buy, sell, place orders, change strategy parameters, or override account-level risk rules.

For cost and rate-limit control, future AI news/filing analysis should use a keyword or traditional NLP prefilter before LLM calls.

## B005 Implications

B005 should implement global ETF momentum in a way that can later plug into this master allocation model:

- Strategy ID and budget assumption included in outputs.
- Target weights emitted in a portfolio-compatible format.
- Drawdown and risk flags available to account-level controls.
- Slippage/cost assumptions explicit.
- No claim that single-strategy backtest equals whole-account performance.
