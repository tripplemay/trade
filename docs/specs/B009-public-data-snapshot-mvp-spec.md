# B009 Public Data Snapshot MVP Spec

## Background

B006 delivered the first fixture/mock-first Global ETF Momentum backtest MVP. B007 hardened backtest mechanics and reporting. B008 expanded the research universe, synthetic research sample, data quality markers, and a fail-closed public import boundary.

The remaining MVP PRD gap is that the system can prove mechanics with committed fixtures, but it does not yet provide a safe, auditable path for a local research user to import public historical data into a reproducible snapshot.

## Goal

Add a manual, disabled-by-default public data import and local snapshot workflow for Global ETF Momentum research, while preserving all existing safety boundaries: no required network in CI, no secrets, no paid data, no broker, no paper/live execution, no AI trading, and no hidden external dependency.

This batch should move the MVP from synthetic fixture-only mechanics toward reproducible local research runs using public best-effort data snapshots.

## Hard Decisions

- Default CI and L1 tests remain fixture/mock-first and offline.
- Public data import must be manual only and disabled by default.
- Imported data must write only to gitignored local directories.
- Imported data is research-only, public-best-effort, and non-PIT unless a later batch proves otherwise.
- No API keys, `.env`, paid datasets, broker exports, account statements, large data files, or generated market data snapshots may be committed.
- If the evaluator environment cannot access public network, evaluator validates fail-closed behavior, local fixture/sample paths, snapshot semantics, and safety guards. Real download execution remains a separately authorized manual/L2 activity.
- B009 does not implement risk parity, multi-factor strategies, Paper Trading broker adapters, live trading, frontend dashboard, cloud deployment, AI execution, tax optimization, or investment advice.

## Reference Documents

- `docs/prd/mvp-prd.md`
- `docs/specs/B008-research-grade-data-expansion-spec.md`
- `docs/specs/B007-backtest-quality-hardening-spec.md`
- `docs/specs/B006-global-etf-backtest-mvp-spec.md`
- `docs/test-reports/B008-research-grade-data-expansion-signoff-2026-05-13.md`
- `docs/engineering/testing-and-fixture-policy.md`
- `docs/engineering/config-and-environment-policy.md`
- `docs/engineering/no-live-safety-guards.md`
- `docs/engineering/backtest-report-schema.md`
- `docs/engineering/pit-data-degradation-policy.md`
- `docs/strategy/00-master-portfolio-allocation.md`
- `docs/strategy/01-global-etf-momentum-rotation.md`

## Proposed Implementation Shape

### Manual Public Data Import Boundary

Provide a CLI/script or extend the existing stub so a local user can intentionally request public data import. The command must require an explicit user action, such as a command argument or flag, and must never run as part of default tests, imports, package initialization, or workflow execution.

The import path should be credential-free. If a provider would require secrets, that provider is out of scope for B009.

### Local Snapshot Manifest

Imported outputs must be organized as local research snapshots. Each snapshot should have a manifest recording at least:

- `snapshot_id`
- source/provider label
- creation timestamp
- ticker list
- date range
- row counts
- file paths under a gitignored local directory
- content hash or per-file hashes when practical
- data source policy / limitation labels
- public-best-effort and non-PIT markers

The snapshot manifest is the auditable bridge between data import and backtest/report artifacts.

### Backtest Loader Integration

The Global ETF Momentum workflow should be able to use a local snapshot when explicitly configured. Default CI and tests must continue to use committed fixtures.

Missing snapshot data must fail closed with a clear error. The workflow must not silently download data, fall back to network, or look for secrets.

### Imported Data Quality Gate

Imported snapshots must run through data quality checks before being treated as research inputs. Reports should expose quality flags and limitations already introduced in B008, including missing OHLC fields, non-positive prices, duplicate dates, trading calendar gaps, missing adjusted/open fields, suspicious jumps, public-best-effort labels, non-PIT labels, and not-live-trading-ready labels.

### Reproducible Research Run Artifact

The workflow should produce or document a reproducible research run artifact structure containing:

- strategy config
- snapshot reference
- quality summary
- backtest report
- target weights or portfolio-compatible output when already supported
- research limitations

This prepares the MVP for later Paper Trading readiness without connecting a broker.

## Feature Requirements

### F001 Public Data Import CLI Boundary

Executor: generator.

Implement or complete a manual-only public data import CLI/script boundary. It must be disabled by default, excluded from CI default paths, credential-free, and output only to gitignored local directories. Tests must prove default paths do not trigger network access.

### F002 Local Data Snapshot Manifest

Executor: generator.

Add snapshot manifest generation for imported local research data. The manifest must record source, timestamp, tickers, date range, row counts, hashes or equivalent integrity metadata, local output paths, and research limitation labels.

### F003 Historical Data Loader Integration

Executor: generator.

Allow Global ETF Momentum backtest workflows to explicitly load a local snapshot while preserving fixture/mock-first defaults. Missing snapshots must fail closed and must not trigger implicit downloads, secret lookup, or broker access.

### F004 Imported Data Quality Gate And Report Labels

Executor: generator.

Run data quality checks against imported snapshots and expose quality flags and research limitations in JSON/Markdown reports. Preserve B008 synthetic fixture labels and add or verify public-best-effort, non-PIT, research-only, and not-live-trading-ready labels.

### F005 Reproducible Research Run Artifact

Executor: generator.

Create or document a reproducible research run artifact structure linking strategy config, snapshot manifest, quality summary, backtest report, and target weights or portfolio-compatible output. This must remain broker-free and suitable for human review.

### F006 Independent Evaluation

Executor: codex.

Evaluator runs local/CI-safe L1 verification. It must confirm default CI remains offline and fixture/mock-first, public import is manual/disabled, outputs are gitignored, reports reference snapshot and limitations, quality gates run, and no secret/broker/live/paper/AI-trading path is introduced.

## Acceptance Summary

B009 is complete only when:

- Required checks pass locally: pytest, ruff, compileall, mypy.
- Default CI/test workflow has no network dependency.
- Public import cannot run unless explicitly requested.
- No secrets, paid data, broker exports, account data, generated market data snapshots, or large data files are committed.
- Imported outputs go to gitignored local directories.
- Snapshot manifests are generated and referenced by research/backtest artifacts.
- Missing snapshots fail closed without implicit network fallback.
- Data quality checks and research limitation labels appear in reports.
- No-live/no-secret/no-network-by-default/no-broker/no-AI-trade guards still pass.
- Evaluator signs off F006 with reports under `docs/test-reports/`.
