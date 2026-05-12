# B004 Core Engineering Foundation Review 2026-05-12

## Scope

This is the independent Evaluator review for B004 F007.

Reviewed documents:

- `docs/specs/B004-core-engineering-foundation-spec.md`
- `docs/engineering/python-package-boundary.md`
- `docs/engineering/config-and-environment-policy.md`
- `docs/engineering/no-live-safety-guards.md`
- `docs/engineering/testing-and-fixture-policy.md`
- `docs/engineering/portfolio-allocation-boundary.md`
- `docs/engineering/backtest-report-schema.md`
- `docs/strategy/00-master-portfolio-allocation.md`
- `docs/prd/mvp-prd.md`
- `docs/specs/B001-strategy-research-roadmap-spec.md`
- `docs/specs/B002-data-source-and-broker-adapter-spec.md`
- `docs/specs/B003-mvp-product-prd-spec.md`
- `docs/research/strategy-audit-report-2026-05-12.md`

## Result

PASS.

No blocking consistency defects were found. B004 remains a documentation/specification batch and does not authorize product implementation code, live trading, real broker calls, external API hard dependencies, hidden secret dependencies, or formal frontend app implementation.

## Findings

No blocking findings.

## Evidence

| Area | Evidence | Result |
|---|---|---|
| Documentation-only boundary | The B004 spec explicitly excludes product source code, Python package scaffolding, CI configuration, migrations, frontend app, broker integration, data downloader, and deployment configuration. The produced artifacts are Markdown documents under `docs/`. | PASS |
| B001 strategy consistency | B004 preserves USD 100k-500k personal-account scope, robust low-frequency strategy style, global ETF momentum as B005 first implementation target, risk parity as later stabilizer, US quality momentum and Hong Kong / China ETF as satellite sleeves, and AI as risk overlay only. | PASS |
| B002 data/broker/environment consistency | B004 requires fixture/local file first, no live broker or paper broker API by default, safe local/CI defaults, explicit paper/live authorization, no default `.env`/API key/broker credential dependency, and no required network calls. | PASS |
| B003 PRD consistency | B004 aligns with the B003 PRD by setting B004 as engineering foundation planning and B005 as global ETF backtest MVP. It keeps formal frontend dashboard, cloud production deployment, live broker execution, real-money trading, and AI autonomous trading out of MVP scope. | PASS |
| Strategy audit incorporation | `00-master-portfolio-allocation.md` and `portfolio-allocation-boundary.md` address the audit's master portfolio allocator gap with a core-satellite structure, static baseline plus quarterly rebalance, account-level drawdown kill switch, slippage/tax/macro-filter boundaries, and AI prefilter constraints. | PASS |
| No-live safety | `no-live-safety-guards.md` states no required local/CI flow may connect to a broker, submit orders, depend on live credentials, or operate real money. It also requires later explicit authorization for real broker, paper broker, or live-money tests. | PASS |
| Fixture/mock-only CI | `testing-and-fixture-policy.md` and `config-and-environment-policy.md` require B005 L1 tests to run without `.env`, network, paid data, external APIs, or broker credentials. Optional public data scripts must be manual and disabled by default. | PASS |
| Broker/API boundary | `python-package-boundary.md` limits the `brokers` module to interface contracts and mocks in MVP, prohibits broker modules from default local/CI flows, and says strategies must not import broker credentials or call broker modules. | PASS |
| Secret boundary | Config policy disallows required `.env`, API keys, broker credentials, paid market data files, real account exports, and auto-detecting credentials as authorization. | PASS |
| Frontend boundary | `python-package-boundary.md` and `backtest-report-schema.md` keep reporting to JSON/Markdown/optional CSV and explicitly exclude a formal frontend dashboard. No frontend app implementation is authorized by B004. | PASS |
| AI boundary | B004 states AI cannot buy, sell, place orders, change parameters, bypass risk controls, generate executable trade decisions, modify child-strategy budgets, or alter rebalance schedules. | PASS |
| B005 handoff | B004 gives B005 a narrow global ETF backtest MVP handoff with fixture/mock-first data, local/CI-safe execution, JSON/Markdown reports, data snapshot and parameter recording, and guard tests for no-live/no-secret/no-broker-call/AI no-buy behavior. | PASS |

## Non-Blocking Risks

| ID | Risk | Impact | Recommendation |
|---|---|---|---|
| R1 | B004 is documentation-only; guard tests are specified but not yet executable. | Future implementation could violate no-live/no-secret/no-broker-call boundaries if tests are missed. | B005 acceptance should require L1 guard tests for no `.env`, no network in required tests, no broker calls from default paths, and no AI buy/autoparameter paths. |
| R2 | Optional public data download scripts are allowed later if scoped. | Scope creep could make external APIs implicit dependencies. | Require optional scripts to be disabled by default, excluded from CI, safe without credentials, and documented as non-PIT research aids only. |
| R3 | `mypy` is intended but may be staged. | Type-checking could be deferred indefinitely. | If B005 defers `mypy`, require an explicit staged adoption note in the B005 spec and keep `compileall` plus tests mandatory. |

## Conclusion

B004 F007 passes independent Evaluator review. The B004 documentation set is consistent with B001/B002/B003 and the independent strategy audit, and is suitable as the handoff baseline for B005 Global ETF Backtest MVP planning and implementation.
