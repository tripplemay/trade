# B005 Pre-Backtest Architecture Adjudication Review 2026-05-12

## Scope

This is the independent Evaluator review for B005 F006.

Reviewed documents:

- `docs/specs/B005-pre-backtest-architecture-adjudication-spec.md`
- `docs/engineering/python-package-boundary.md`
- `docs/engineering/portfolio-allocation-boundary.md`
- `docs/engineering/backtest-report-schema.md`
- `docs/engineering/pit-data-degradation-policy.md`
- `docs/engineering/oms-tax-lot-boundary.md`
- `docs/engineering/ai-filing-prefilter-policy.md`
- `docs/specs/B004-core-engineering-foundation-spec.md`
- `docs/prd/mvp-prd.md`
- `docs/architecture/01-broker-adapter-spec.md`
- `docs/architecture/02-data-model-point-in-time-policy.md`
- `docs/architecture/03-environment-isolation-and-live-authorization.md`
- `docs/research/strategy-audit-report-2026-05-12.md`
- `docs/research/prd-architecture-audit-2026-05-12.md`

## Result

PASS.

No blocking consistency defects were found. B005 is a documentation/adjudication batch that absorbs the independent PRD/architecture audit findings before the Global ETF Backtest MVP implementation. It does not authorize product code, live trading, real broker calls, external API hard dependencies, hidden secret dependencies, formal frontend implementation, or tax advice.

## Findings

No blocking findings.

## Evidence

| Area | Evidence | Result |
|---|---|---|
| Documentation-only boundary | The B005 spec states the batch does not implement product code, package scaffolding, broker adapters, data providers, OMS, AI pipelines, frontend, deployment, migrations, or live/paper trading. B006 is explicitly the deferred Global ETF Backtest MVP implementation batch. | PASS |
| Portfolio Manager adjudication | B005 AD-001 and updated engineering docs define `Strategy signals/targets -> Portfolio Manager -> Risk -> OMS -> Broker Adapter`. PM owns strategy budget allocation, buying-power limits, account-level targets, and account-level risk state, matching both audit reports. | PASS |
| T+1 Open execution assumption | B005 AD-002 and `backtest-report-schema.md` require T-day close for signal generation and T+1 open as default execution price. Reports must record signal price, execution price, execution timing, execution assumption, and slippage model. | PASS |
| PIT data degradation | `pit-data-degradation-policy.md` preserves the B002 PIT policy while acknowledging retail-data limitations. It requires US multi-factor fundamentals to degrade to price/volume-derived factors until high-quality PIT fundamentals are licensed or verified. Non-PIT fundamental research must be labeled degraded, lagged, and excluded from production-readiness claims. | PASS |
| Tax-lot / OMS boundary | `oms-tax-lot-boundary.md` preserves future tax-lot fields and OMS lot-selection intent while explicitly stating it is not tax advice and B006 must not implement tax optimization, lot selection, or tax advice. | PASS |
| AI filing prefilter | `ai-filing-prefilter-policy.md` requires deterministic prefilters before LLM analysis and forbids AI from buying, selling, placing/canceling/replacing orders, changing strategy parameters, allocating capital, overriding PM/risk/kill switches, or claiming filtered-out documents were reviewed. | PASS |
| No live trading / broker calls | B005 handoff requires no live broker, no paper broker, no hidden secrets, and no required network. It remains consistent with B002 environment isolation and explicit authorization requirements. | PASS |
| No external API hard dependency | B005 keeps B006 fixture/mock-first and required tests free from network, secrets, real broker, or external API availability. | PASS |
| No formal frontend scope | B005 introduces no frontend implementation and remains aligned with the B003 PRD exclusion of a formal dashboard/app before backtest outputs stabilize. | PASS |
| No tax advice | Tax-related documents preserve interface boundaries and tax-friction assumptions only; they explicitly prohibit tax advice and B006 tax optimization. | PASS |

## Non-Blocking Risks

| ID | Risk | Impact | Recommendation |
|---|---|---|---|
| R1 | B006 will be the first implementation batch after several documentation-only guardrails. | Implementation could accidentally omit guard tests or report fields. | B006 acceptance should explicitly require no-live/no-secret/no-network/no-broker-call guard tests and report fields for signal/execution price and PM-compatible output. |
| R2 | T+1 open defaults are now mandatory, but fallback behavior for missing open prices is only a report flag in the schema. | Edge cases around holidays, suspended assets, or missing open data could create inconsistent backtest behavior. | B006 should define deterministic fallback behavior and mark any fallback in JSON/Markdown reports. |
| R3 | PIT degradation policy permits exploratory non-PIT fundamentals with conservative lag. | Future readers may overinterpret degraded exploratory results. | B006 should avoid fundamentals entirely; later factor batches should place a visible degraded/PIT status in every report. |

## Conclusion

B005 F006 passes independent Evaluator review. The adjudications are consistent with B001-B004 and both independent audit reports, and the B006 handoff is suitable for a fixture/mock-first Global ETF Backtest MVP implementation.
