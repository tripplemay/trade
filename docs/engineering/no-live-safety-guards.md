# No-Live Safety Guards

## Purpose

The MVP must be safe by default. No required local or CI flow may connect to a real broker, submit an order, depend on live credentials, or operate real money.

## Guard Principles

- Default mode is local/CI research backtest.
- Broker execution is not implemented in MVP.
- Paper/live modes require a later spec and separate user authorization.
- AI cannot directly or indirectly generate executable orders.

## Required Guard Tests For Implementation Batches

B005 and later implementation batches should include L1 tests or static checks for:

- No live broker entrypoint in default command paths.
- No required `.env` or API key for tests.
- No network call in required CI tests.
- No broker module import from strategy signal code.
- No AI buy/sell/order instruction path.
- No AI parameter mutation path.
- No report output that claims paper/live execution occurred.

## Authorization Boundary

Any future real broker, paper broker, or live-money test must be separately authorized by the user and must state:

- Broker.
- Account or account class.
- Strategy.
- Maximum notional or amount.
- Time window.
- Allowed operation type.

Absent this authorization, all broker/live operations are out of scope.

## Safe Failure Behavior

If code later detects paper/live configuration without explicit authorization, it should fail closed. The safe outcome is a clear error message, not a fallback to best-effort execution.
