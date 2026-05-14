# B014 Regime-Adaptive Stress Validation Extension Spec

## Background

B013 implemented the Regime-Adaptive Multi-Asset Strategy (L1 200-day SMA gating + L2 inverse-vol with 8% vol target + L3 NORMAL/BEAR/CRISIS regime detection + 3% tolerance bands) and signed off with 117 B013 tests + 336 full suite all passing. However, the headline acceptance gate — 2020 max DD < 15% and 2022 max DD < 15% — was reported as `skipped` because the repository does not contain a real historical public-data snapshot. The existing `scripts/acquire_regime_adaptive_snapshot.py` is structurally a CSV-import tool: it validates and copies user-supplied `<SYMBOL>.csv` files into the gitignored `data/public-cache/` directory; it does not download data itself.

B013 therefore landed as **code-correct and safety-bounded but the strategy's crisis-shield claim is not yet evidence-backed**. The user authorized public-data download in B013 planning. B014 closes that gap by adding a minimal Stooq-based fetcher helper, running the fetcher once, and using Codex to validate the snapshot, run the 2020 and 2022 stress windows on the real data, compare B013 against B006 momentum, B010 risk parity, and static 60/40 on the same window, and produce an evidence-backed signoff.

B014 does not change strategy code. Its purpose is empirical validation of the existing B013 claim. If the empirical max DD breaches 15% on either window, that is a research finding (parameter tuning candidate), not a code defect.

## Goal

Implement a minimal, testable Regime-Adaptive Stress Validation Extension that:

- Adds a Stooq-based opt-in CSV fetcher helper that retrieves daily OHLCV for the 9-asset universe (SPY, QQQ, VEA, VWO, IEF, TLT, GLD, DBC, SGOV) over 2018-2025 from the free public Stooq CSV endpoint, writes per-ticker CSVs into a user-supplied source directory, and then invokes the existing `scripts/acquire_regime_adaptive_snapshot.py` to register them as a manifest.
- Adds unit tests for the fetcher using mocked HTTP responses; the fetcher itself must never run during default CI.
- Has Codex perform the one-time real network fetch (with explicit user-authorized opt-in flag), then validate the manifest, sha256, and SGOV inception handling.
- Has Codex run B013 backtest + 2020 (post-SGOV-inception) and 2022 stress windows on the real snapshot and produce a stress report with empirical drawdown / Sharpe / turnover / regime-history numbers.
- Has Codex cross-compare B013 vs B006 momentum vs B010 risk parity vs static 60/40 on the overlapping window, with all strategies running on the same real snapshot.
- Has Codex sign off with an evidence-backed verdict that upgrades B013's stress gate from `skipped` to empirical `pass` or `fail` with numbers; if empirical max DD breaches 15%, this is reported as a research finding (proposed-learnings entry for parameter retuning), not a code failure.

This batch is a validation extension — not a strategy redesign, broker adapter, or new feature.

## Hard Decisions

- Data source: **Stooq** direct CSV endpoint at `https://stooq.com/q/d/l/?s=<symbol>.us&i=d&d1=YYYYMMDD&d2=YYYYMMDD`. Free, no API key, returns plain CSV with columns `Date, Open, High, Low, Close, Volume`. Best-effort public data; treated as non-PIT, research-only.
- Fetcher implementation uses Python **stdlib only** (`urllib.request`, `urllib.error`, `csv`, `pathlib`). No new third-party dependencies. Zero broker / paper / paid-data / AI SDK imports anywhere in the helper.
- Fetcher is **opt-in** via an explicit `--i-understand-this-is-manual-research-data` flag (same idiom as the existing acquire script). It refuses to run without the flag. It is never invoked by default CI.
- The fetcher script is the only B014 module that performs network I/O. It lives under `scripts/` to keep `trade/` strategy modules network-free. Strategy module forbidden-import scans (B013 F010) remain intact.
- The fetcher is **fail-closed**:
  - HTTP error on any ticker → exit non-zero with explicit diagnostic.
  - Partial response (fewer rows than the expected business-day count by a tolerance) → exit non-zero unless `--allow-short-history` is explicitly passed (used only when SGOV-style late-inception tickers are involved).
  - Non-CSV / malformed response → exit non-zero.
- **SGOV inception is 2020-05-28** (iShares 0-3 Month Treasury Bond ETF). The fetcher must allow SGOV's start date to be later than the requested `d1` and explicitly record SGOV's first-available date in the output report. Other 8 tickers must cover the full 2018-01-01 to 2025-12-31 range without short-history fallback.
- 2020 stress window: nominally 2020-02-01 to 2020-12-31. If SGOV data starts 2020-05-28, the **defensive routing during the 2020-02-01 to 2020-05-27 sub-window holds defensive allocation as cash placeholder** (zero return, no symbol). This matches B013's existing defensive routing semantics. The stress report explicitly documents the SGOV pre-inception sub-window as a known caveat.
- 2022 stress window: 2022-01-01 to 2022-12-31. Fully covered by SGOV; no caveats.
- Cross-strategy comparison: B013 + B006 momentum + B010 risk parity + static 60/40 baseline. All four run on the same date range using the same real snapshot. Period alignment by trading-day intersection; no extrapolation.
- All artifacts research-only. Reports, fetcher logs, manifest entries, and docstrings carry the research-only disclaimer. Tests assert absence of `paper-execution`, `live-execution`, `executed-order`, `filled`, `place_order`, `submit_order` phrasing in B014 outputs.
- No mutation of B013 strategy code, B011 master portfolio code, B010 / B006 strategy code, or any spec under `docs/specs/B0xx`. B013's stress gate semantics (pass/skip/fail) are retained — B014 only fills in real data to flip `skipped` to `pass` or `fail`.
- Codex-executed network operation is one-time, explicit, and bounded: only the 9 tickers over 2018-01-01 to 2025-12-31, ≤ 9 HTTP GETs to Stooq, no API keys, no credentials, no broker, no paper or live trading. The acquired data is gitignored under `data/public-cache/`; only the manifest (sha256 references) is committed.
- Default CI continues to use synthetic fixtures and remains fixture/mock-first. Real-snapshot tests are exercised only when the manifest is present and only by explicit research-mode tests.
- If empirical max DD on 2020 or 2022 breaches 15% on the real snapshot, B014 records this in a **proposed-learnings** entry suggesting parameter retune (no automatic code change). This is a research finding, not a code defect.

## Reference Documents

- `docs/specs/B013-regime-adaptive-multi-asset-mvp-spec.md`
- `docs/specs/research/B011-regime-adaptive-multi-asset-spec.md`
- `docs/specs/B009-public-data-snapshot-mvp-spec.md`
- `docs/specs/B010-risk-parity-backtest-mvp-spec.md`
- `docs/specs/B006-global-etf-backtest-mvp-spec.md`
- `docs/test-reports/B013-regime-adaptive-multi-asset-mvp-signoff-2026-05-14.md`
- `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`
- `docs/prd/mvp-prd.md`
- `docs/strategy/00-master-portfolio-allocation.md`
- `docs/engineering/testing-and-fixture-policy.md`
- `docs/engineering/no-live-safety-guards.md`
- `docs/engineering/backtest-report-schema.md`
- `docs/engineering/pit-data-degradation-policy.md`
- `scripts/acquire_regime_adaptive_snapshot.py` (existing CSV-import tool to be invoked downstream by the new fetcher)

## Proposed Implementation Shape

### Stooq Fetcher Helper

A new opt-in CLI: `scripts/fetch_stooq_regime_adaptive_csvs.py`.

Interface (sketch):

```text
python scripts/fetch_stooq_regime_adaptive_csvs.py \
    --output-dir data/public-cache-staging \
    --from 2018-01-01 \
    --to 2025-12-31 \
    --i-understand-this-is-manual-research-data
```

Behavior:

- Requires `--i-understand-this-is-manual-research-data` flag.
- For each ticker in the 9-asset universe, builds the Stooq URL: `https://stooq.com/q/d/l/?s=<symbol_lower>.us&i=d&d1=<YYYYMMDD>&d2=<YYYYMMDD>`.
- Performs HTTP GET via `urllib.request.urlopen` with explicit timeout (e.g., 30s) and a research-only User-Agent string.
- Parses the response as CSV; validates header `Date,Open,High,Low,Close,Volume`; validates each row's date is within the requested window.
- Writes `<SYMBOL>.csv` to the output directory (uppercase symbol filename, preserving Stooq's column order).
- Logs per-ticker fetch summary: ticker, HTTP status, row count, first / last date.
- SGOV exception: accepts short history with explicit note in the log; logs SGOV first-available date.
- Other 8 tickers: must reach `>= 95%` of expected business-day count for the window or exit non-zero (no silent partial fetch).
- After all 9 tickers fetched, optionally invokes the existing acquire script via `subprocess` (or just instructs the user to run it next).
- Network call is opt-in, one-time, bounded.

### Tests For The Fetcher (Generator, Mocked HTTP)

`tests/unit/test_stooq_fetcher.py`:

- Mock `urllib.request.urlopen` to return canned CSV bytes.
- Cover: happy-path 9-ticker fetch, missing-flag refusal, HTTP error → exit non-zero, malformed CSV → exit non-zero, short history without `--allow-short-history` → exit non-zero, SGOV short-history accepted with explicit allowance, output filename casing, log content shape.
- No real network call in any test.

### Real Snapshot Acquisition (Codex)

Codex runs:

1. `python scripts/fetch_stooq_regime_adaptive_csvs.py --output-dir data/public-cache-staging --from 2018-01-01 --to 2025-12-31 --i-understand-this-is-manual-research-data`
2. Inspects per-ticker logs; if any non-SGOV ticker reports < 95% coverage, halts and reports.
3. `python scripts/acquire_regime_adaptive_snapshot.py --source-dir data/public-cache-staging --output-dir data/public-cache --from 2018-01-01 --to 2025-12-31 --i-understand-this-is-manual-research-data`
4. Verifies manifest at `data/public-cache/regime-adaptive-prices-manifest.json` exists, sha256 entries are consistent, SGOV first-date metadata is captured.

Diagnostic record committed to `docs/test-reports/B014-regime-adaptive-stress-validation-acquisition-log-2026-MM-DD.md`. Per-ticker raw CSVs remain gitignored under `data/public-cache/`.

### Stress Backtest On Real Snapshot (Codex)

Codex runs B013 backtest on the acquired snapshot for both stress windows:

- **2020 window**: 2020-02-01 to 2020-12-31 (covers the COVID liquidity crisis). SGOV pre-inception sub-window (2020-02-01 to 2020-05-27) treated as cash-placeholder defensive routing.
- **2022 window**: 2022-01-01 to 2022-12-31 (covers the inflation / stock-bond drawdown). SGOV fully available.

For each window, records: max drawdown, drawdown duration, recovery time, annualized return, annualized volatility, Sharpe, turnover, total transaction costs, regime label timeline (NORMAL / BEAR / CRISIS counts and transitions), gating activity per asset, tolerance-band suppression statistics.

Acceptance gate: `2020 max DD < 0.15` AND `2022 max DD < 0.15`. Pass → empirical signoff. Fail → research finding documented in proposed-learnings (no code change in B014).

### Cross-Strategy Comparison (Codex)

On the same real snapshot, for the overlapping window (intersection of available data across all four strategies):

- **B013 Regime-Adaptive Multi-Asset** with default parameters.
- **B006 Global ETF Momentum** with its default configuration (note: B006 uses a different universe — momentum top-N rotation; comparison is on equity curve, not weight overlap).
- **B010 Risk Parity** with its default inverse-vol configuration.
- **Static 60/40 multi-asset** quarterly rebalance baseline (reuse B011 calculated baseline mechanic).

Per strategy report: equity curve, annualized return, annualized volatility, Sharpe, max drawdown, turnover, transaction costs. Per stress window: drawdown comparison table.

Output: `docs/test-reports/B014-regime-adaptive-cross-strategy-comparison-2026-MM-DD.md` + JSON sidecar.

### Codex Signoff With Empirical Evidence

Codex writes `docs/test-reports/B014-regime-adaptive-stress-validation-signoff-2026-MM-DD.md` containing:

- Empirical 2020 + 2022 max DD numbers.
- Stress gate verdict: `pass` or `fail` with concrete deltas vs 15% threshold.
- Cross-strategy comparison summary.
- Any soft-watch items discovered.
- Framework learnings if the empirical result warrants a proposed-learnings entry (e.g., "default crisis_exposure_scale=0.5 insufficient for 2020 COVID drawdown; recommend X").
- Explicit upgrade note: B013 signoff's stress gate is now empirically resolved.

### Safety And Regression

All existing safety boundaries remain mandatory and B014-specific tests prove:

- Fetcher module contains no broker SDK imports (reuse B012 list).
- Fetcher module contains no AI/LLM SDK imports (reuse B013 list).
- Fetcher module contains no paper-trading API URLs (the fetcher itself targets Stooq's public CSV endpoint — that is the only authorized host).
- Fetcher module's only network call is the explicit Stooq GET, gated behind the opt-in flag.
- No `os.environ` / `os.getenv` reads in the fetcher's parser logic (config comes through CLI args).
- Default CI test path performs no network I/O.
- Reports / logs / docstrings carry the research-only disclaimer; tests assert absence of `paper-execution`, `live-execution`, `executed-order`, `filled`, `place_order`, `submit_order` phrasing in B014 outputs.
- No mutation of B013 strategy code; existing B013 tests continue to pass without modification.
- Required local checks must pass: pytest, ruff, compileall, mypy.

## Feature Requirements

### F001 Stooq Fetcher Helper Script

Executor: generator.

Add `scripts/fetch_stooq_regime_adaptive_csvs.py` that fetches the 9 regime-adaptive tickers' daily OHLCV from Stooq's public CSV endpoint over 2018-01-01 to 2025-12-31 (configurable), writes per-ticker `<SYMBOL>.csv` files to an output directory, and is opt-in via the explicit `--i-understand-this-is-manual-research-data` flag. The fetcher uses stdlib only (urllib + csv), targets only `stooq.com/q/d/l/`, treats SGOV's late inception as an allowed short-history case, and fails closed on HTTP errors, malformed CSV, or insufficient coverage for non-SGOV tickers. Default CI must not invoke it.

### F002 Fetcher Unit Tests With Mocked HTTP

Executor: generator.

Add `tests/unit/test_stooq_fetcher.py` covering: happy-path 9-ticker fetch via mocked HTTP responses, missing-flag refusal, HTTP error fail-closed, malformed CSV fail-closed, short-history rejection for non-SGOV tickers, SGOV short-history acceptance with allowance flag, output filename and CSV schema correctness, no real network call in any test. pytest, ruff, compileall, mypy all pass.

### F003 Real Snapshot Acquisition And Manifest Verification

Executor: codex.

Run `scripts/fetch_stooq_regime_adaptive_csvs.py` once with the explicit opt-in flag to retrieve real Stooq CSVs into a staging directory. Verify per-ticker fetch logs show: all 8 non-SGOV tickers reach ≥ 95% expected business-day coverage; SGOV reports its real first-available date with allowance. Run `scripts/acquire_regime_adaptive_snapshot.py` to register the staged CSVs as a manifest at `data/public-cache/regime-adaptive-prices-manifest.json`. Verify manifest sha256 entries are stable across two consecutive runs of the import (skipping the fetch). Commit an acquisition log at `docs/test-reports/B014-regime-adaptive-stress-validation-acquisition-log-2026-MM-DD.md`. Raw CSVs and the snapshot remain gitignored.

### F004 Stress Backtest On Real Snapshot

Executor: codex.

Run B013 monthly backtest on the real snapshot over 2020-02-01 to 2020-12-31 and 2022-01-01 to 2022-12-31. Use B013 default parameters unchanged. For each window record empirical max drawdown, drawdown duration, recovery time, annualized return / volatility / Sharpe, turnover, transaction costs, regime label timeline, gating activity, tolerance-band statistics. Apply stress acceptance gate: `2020 max DD < 0.15 AND 2022 max DD < 0.15` → `pass`; otherwise `fail` with empirical numbers. Output stress report at `docs/test-reports/B014-regime-adaptive-stress-validation-2026-MM-DD.md` + JSON sidecar. Reports carry the research-only disclaimer.

### F005 Cross-Strategy Comparison On Real Snapshot

Executor: codex.

On the overlapping window of the real snapshot, run B013, B006 momentum, B010 risk parity, and static 60/40 baseline with their default configurations. Produce comparative equity curves, annualized metrics, max drawdown, turnover, transaction costs. Per stress window, produce a comparative drawdown table. Output comparison report at `docs/test-reports/B014-regime-adaptive-cross-strategy-comparison-2026-MM-DD.md` + JSON sidecar. No new strategy code; reuse existing implementations.

### F006 Evidence-Backed Signoff And B013 Stress Gate Resolution

Executor: codex.

Write `docs/test-reports/B014-regime-adaptive-stress-validation-signoff-2026-MM-DD.md` containing: empirical 2020 + 2022 max DD numbers, stress gate verdict (`pass` / `fail`) with concrete deltas vs 15% threshold, cross-strategy comparison summary, any soft-watch items, and framework learnings if warranted (e.g., parameter retune suggestion if max DD > 15%). Explicitly note that B013's stress gate, previously reported as `skipped`, is now empirically resolved. If `fail`, add a `framework/proposed-learnings.md` entry describing the empirical shortfall and recommended next batch (parameter retune); do not change B013 strategy code in B014. Update `progress.json` `evaluator_feedback` and `docs.signoff` per Harness convention. Required local checks must pass: pytest, ruff, compileall, mypy.

## Acceptance Summary

B014 is complete only when:

- Required local checks pass: pytest, ruff, compileall, mypy.
- Stooq fetcher helper script is opt-in, stdlib-only, fail-closed, and never invoked by default CI.
- Fetcher unit tests pass without any real network call.
- Real snapshot is acquired via the explicit opt-in fetcher run + acquire script run; manifest at `data/public-cache/regime-adaptive-prices-manifest.json` exists with consistent sha256 entries; raw CSVs remain gitignored.
- 2020 and 2022 stress windows are run on the real snapshot with empirical max DD numbers reported. Stress acceptance gate verdict (`pass` / `fail`) is explicit.
- Cross-strategy comparison report covers B013 vs B006 vs B010 vs 60/40 on the overlapping window.
- Codex signs off F006 with the empirical numbers and resolves B013's previously `skipped` stress gate.
- If empirical max DD breaches 15% on either window, a `proposed-learnings.md` entry is added describing the shortfall and recommending parameter retune; B013 strategy code is **not** modified in B014.
- No forbidden broker SDK / AI-LLM SDK / paper-trading API URL is introduced; the only authorized network host is `stooq.com`.
- All reports / logs / docstrings carry the research-only disclaimer.
