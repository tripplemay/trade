# OMS Tax-Lot Boundary

## Purpose

This document preserves future OMS and broker model boundaries for taxable personal accounts. It is not tax advice and does not implement tax optimization.

## Problem

Broker position models that only expose `average_cost` are insufficient for future taxable-account workflows. US taxable accounts often require lot-level information for realized gains, tax-loss harvesting, and specific identification workflows.

## Future Position Boundary

Future broker/OMS models should preserve space for:

- `tax_lots` array.
- Lot ID.
- Acquisition date.
- Quantity.
- Cost basis.
- Currency.
- Broker-provided lot metadata when available.

## Future OMS Boundary

Future OMS sell workflows should be able to carry lot-selection intent when supported by the broker. This is a future interface boundary only.

B006 must not implement tax optimization, lot selection, or tax advice. It should avoid model names and report claims that imply tax-aware execution is already available.

## Cross-Module Rule

- Portfolio Manager may report that tax-lot data is unavailable.
- Risk/reporting may include tax-friction assumptions.
- Broker Adapter must not collapse all future design assumptions into average cost only.
- AI must not provide personalized tax decisions.
