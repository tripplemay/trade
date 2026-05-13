# B008 Research-Grade Data Expansion Spec

## Background

B006 delivered the first fixture/mock-first Global ETF Momentum backtest MVP. B007 hardened the backtest mechanics with multi-rebalance fixtures, explicit missing T+1 Open handling, clean/warning risk scenarios, stronger metrics, and preserved safety guards.

B007's remaining soft-watch is that the synthetic fixtures validate mechanics, not investable research quality. B008 should improve the data/universe layer enough to support more credible research workflows without compromising the fixture/mock-first CI boundary.

## Goal

Expand the Global ETF backtest data foundation toward research-grade usage while preserving safe defaults: no required network, no API keys, no paid data, no broker, no live/paper execution, and no hidden external dependency in CI.

## Hard Decisions

- Default CI and L1 tests remain fixture/mock-first and offline.
- Research samples must be small, committed only when licensing is safe, and clearly labeled as sample/fixture data.
- Optional public-data import may be added only as manual, disabled-by-default, best-effort tooling; it must not become a required test dependency.
- No paid datasets, broker exports, account statements, `.env`, API keys, or large data files may be committed.
- B008 improves data/universe quality for Global ETF Momentum. It does not implement risk parity, multi-factor, Hong Kong / China ETF strategies, broker/paper/live execution, OMS, frontend, deployment, AI trading, tax optimization, or investment advice.

## Reference Documents

- `docs/specs/B007-backtest-quality-hardening-spec.md`
- `docs/specs/B006-global-etf-backtest-mvp-spec.md`
- `docs/test-reports/B007-backtest-quality-hardening-signoff-2026-05-12.md`
- `docs/engineering/testing-and-fixture-policy.md`
- `docs/engineering/config-and-environment-policy.md`
- `docs/engineering/no-live-safety-guards.md`
- `docs/engineering/backtest-report-schema.md`
- `docs/engineering/pit-data-degradation-policy.md`
- `docs/strategy/01-global-etf-momentum-rotation.md`

## Proposed Implementation Shape

### Research Universe

Add a documented Global ETF research universe with fields such as:

- `ticker`
- `name`
- `asset_class`
- `region`
- `currency`
- `role`
- `inception_date` if available
- `data_source_policy`
- `research_notes`

The universe should include representative sleeves for global equities, US equities, ex-US equities, bonds, gold/commodities, and cash/defensive assets. This is a research universe, not a live trading recommendation.

### Research Samples And Fixtures

Extend local data coverage enough to test more realistic conditions:

- Non-monotonic equity curve.
- Drawdown and recovery.
- Sideways/choppy periods.
- Asset rotation across risk and defensive assets.
- Missing or questionable data flags.

Committed data should stay small and reviewable. If real public sample data is used, licensing/source notes must be documented. Synthetic data remains acceptable if labeled and shaped to exercise research scenarios.

### Optional Public Data Import Boundary

If implemented, a public data import script must be:

- Manual only.
- Disabled by default.
- Excluded from required CI.
- Credential-free.
- Writing only to gitignored local directories.
- Marking outputs as non-PIT / best-effort research data.

If not implemented in B008, add a stub or docs boundary making this explicit so Generator does not accidentally introduce network dependencies.

### Data Quality And Research Limitations

Reports should expose data quality and research limitation markers, such as:

- Missing OHLC fields.
- Non-positive prices.
- Duplicate dates.
- Trading calendar gaps.
- Missing adjusted/open fields.
- Suspicious jumps.
- Synthetic fixture label.
- Non-PIT / best-effort public data label.
- No investment advice / not live-trading-ready label.

## Feature Requirements

### F001 Research Universe And Data Dictionary

Executor: generator.

Create or extend docs/configuration for a research-grade Global ETF universe and data dictionary. Keep it documentation/configuration only; no live broker or trading recommendation semantics.

### F002 Expanded Research Sample / Fixture Data

Executor: generator.

Extend local sample/fixture data so workflow tests cover non-monotonic and more realistic market regimes while preserving deterministic offline CI.

### F003 Optional Public Data Import Boundary

Executor: generator.

Add a safe manual import script or explicit stub/docs boundary. Required tests must prove default paths do not require network or secrets.

### F004 Data Quality Flags And Research Limitations

Executor: generator.

Implement or extend quality flags and report fields so research limitations are visible in JSON/Markdown outputs and tests.

### F005 Workflow And Guard Regression

Executor: generator.

Update workflow E2E and guard tests after data expansion. Preserve all B006/B007 safety invariants.

### F006 Independent Evaluation

Executor: codex.

Evaluator runs local/CI-safe verification, reviews data/universe/report outputs, confirms no hidden external dependencies, and signs off only if B008 improves data credibility without weakening safety boundaries.

## Acceptance Summary

B008 is complete only when:

- Required checks pass locally: pytest, ruff, compileall, mypy.
- Research universe/data dictionary is present and reviewed.
- Default workflow remains deterministic and offline.
- Reports expose data quality and research limitation fields.
- Optional import path, if present, is manual/disabled and excluded from CI.
- No-live/no-secret/no-network/no-broker/no-AI-trade guards still pass.
- Evaluator signs off F006 with reports under `docs/test-reports/`.
