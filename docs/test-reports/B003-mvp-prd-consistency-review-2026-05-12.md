# B003 MVP PRD Consistency Review 2026-05-12

## Scope

This is the independent Evaluator review for B003 F005.

Reviewed documents:

- `docs/specs/B003-mvp-product-prd-spec.md`
- `docs/prd/mvp-prd.md`
- `docs/specs/B001-strategy-research-roadmap-spec.md`
- `docs/specs/B002-data-source-and-broker-adapter-spec.md`

## Result

PASS.

No blocking consistency defects were found. The MVP PRD is consistent with B001 strategy scope and B002 data, broker, point-in-time, and environment-isolation constraints. It does not introduce unauthorized live trading, real-money operation, live broker execution, AI autonomous trading, or a premature formal frontend dashboard scope.

## Findings

No blocking findings.

## Evidence

| Area | Evidence | Result |
|---|---|---|
| Product assumptions | The PRD targets the project owner / personal quant user, USD 100k-500k capital, US/Hong Kong/global ETF markets, and low-frequency robust strategies, matching B001/B002 assumptions. | PASS |
| MVP objective | The PRD defines the MVP as a reproducible, testable, auditable research/backtest system for the global ETF momentum strategy, not a live trading product. | PASS |
| Strategy scope | The PRD implements only global ETF momentum in MVP and keeps risk parity, US quality momentum, Hong Kong / China ETF, and AI risk filtering as later planning items, preserving B001 strategy hierarchy. | PASS |
| Data scope | The PRD limits MVP data to ETF master data, daily OHLCV, adjusted close, corporate actions, trading calendar, defensive assets, and small fixtures. It does not require institutional-grade data, real-time data, tick data, Level 2 order book, or a full fundamentals database. | PASS |
| Backtest assumptions | The PRD requires monthly rebalancing, T-day close signal generation, T+1 execution assumptions, cost/slippage parameters, defensive asset switching, Top N holdings, equal weight plus risk caps, benchmark comparison, and data snapshot IDs. This matches B001 and B002 anti-lookahead expectations. | PASS |
| Paper Trading boundary | The PRD explicitly does not implement a real paper broker API in MVP; it only prepares target-position, strategy-config, and report formats for future paper trading. | PASS |
| Broker/live boundary | The PRD excludes live broker ordering, real-money automated trading, IBKR/Alpaca/Futu/Tiger actual API integration, and real broker calls. It also states real broker or live-money tests require separate authorization containing broker, account, strategy, amount, and time window. | PASS |
| AI boundary | The PRD states AI is only for future explanation and risk filtering, and explicitly forbids direct buys, adds, parameter changes, and bypassing risk controls. This preserves B001 AI constraints. | PASS |
| Frontend boundary | The PRD explicitly excludes a complete frontend dashboard, requires Markdown/JSON reports, and says frontend architecture may be planned later but no Next.js/React app should be created for MVP. | PASS |
| Security/compliance | The PRD prohibits API keys, `.env`, paid market data, real account exports, unauthorized broker calls, real-money trades, external investment advice, and AI direct control of trading. | PASS |
| Milestone alignment | The PRD maps B004 to core engineering foundation, B005 to global ETF backtest MVP, B006 to risk parity, B008/B009 to paper/broker work, and keeps live out of MVP. | PASS |

## Non-Blocking Risks

| ID | Risk | Impact | Recommendation |
|---|---|---|---|
| R1 | The PRD allows B004 frontend planning documentation while excluding frontend app creation. | Future scope creep could turn planning into premature implementation. | In B004, treat frontend work as architecture notes only unless a new spec explicitly authorizes UI implementation. |
| R2 | B005 data input remains open between public sample data, synthetic fixtures, or provider interfaces. | Implementation may drift into external API dependency if not constrained. | Require B005 acceptance to keep default CI and L1 tests fixture/mock-only, with any real provider script optional and disabled by default. |
| R3 | The PRD is product documentation only; no executable guard currently enforces no-live and no-AI-trading constraints. | Later implementation could violate boundaries without tests. | Add guard tests in implementation batches for no live trading entrypoint, no real broker default, no secret dependency, and AI no-buy/no-autoparameter behavior. |

## Conclusion

B003 F005 passes independent Evaluator review. The MVP PRD is suitable as the product scope baseline for B004/B005 planning and implementation.
