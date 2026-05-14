# B017 B015 + B016 Real-Data Validation Extension Spec

## Background

B015 (Regime-Adaptive Activation Policy) and B016 (Risk Parity HRP Upgrade) both shipped with their core research questions left as empirical-evidence-pending:

- **B015's question:** does `only_non_normal` or `only_crisis` activation policy shrink B013's absolute-return gap vs static 60/40 in the 2020-06..2022-12 calm window?
- **B016's question:** does correlation-aware HRP weighting shrink B010's absolute-return gap vs static 60/40 on the same real snapshot?

Both batches added `generate_b015_activation_policy_report.py` and `generate_b016_hrp_comparison_report.py` CLI scripts that produce real-data reports when the B014 yfinance snapshot manifest is present at `data/public-cache/regime-adaptive-prices-manifest.json`. The manifest is gitignored by design (raw CSVs are research-only data, not commitable), so both reports currently sit at `real_data_status = "skipped"` in their committed forms.

The user authorized (option B at B015 / B016 done wrap-ups) to handle the real-data validation as a Codex-only follow-up batch rather than baked into the original spec batches. B017 is that batch.

B017 contains no code changes. It is a Codex-executed research-validation pipeline: acquire snapshot → regenerate both reports → cross-analyze → signoff with empirical numbers and any framework-learning entries.

## Goal

Run a single, focused, Codex-only research-validation pass that:

- Acquires the B014 real 9-asset yfinance snapshot (2018-2025) by running the existing opt-in scripts in sequence (`scripts/fetch_yfinance_regime_adaptive_csvs.py` → `scripts/acquire_regime_adaptive_snapshot.py`), reusing the established public-data-acquisition pipeline. Snapshot raw CSVs remain gitignored; only the manifest sha256 fingerprint is committed (already gitignored under `data/public-cache/` per existing pattern).
- Regenerates `docs/test-reports/B015-regime-adaptive-activation-policy-comparison-2026-MM-DD.md` with `real_data_status = "ran"` so the three activation policies (always_on / only_non_normal / only_crisis) have empirical metrics on the B014 snapshot.
- Regenerates `docs/test-reports/B016-risk-parity-hrp-comparison-2026-MM-DD.md` with `real_data_status = "ran"` so the two weighting methods (inverse_volatility / hrp) have empirical metrics on the same snapshot.
- Performs a cross-analysis comparing all six configurations (B015's three activation policies × B016's two weighting methods × B014's static 60/40 baseline) on the overlapping window 2020-06-01..2022-12-31. Note: B015 and B016 are independent variants over the same base, so the six configurations don't all combine — clarify in the analysis what the relevant comparisons are.
- Produces an evidence-backed signoff at `docs/test-reports/B017-real-data-validation-signoff-2026-MM-DD.md` recording empirical 2020/2022 stress max DD per configuration, the cumulative return gap vs static 60/40 per configuration, and a narrative answering both B015 and B016 research questions with concrete numbers.
- If any configuration's empirical 2020 or 2022 max DD violates the -15% B013 stress threshold, that is a research finding that propagates to `framework/proposed-learnings.md` — not a code defect.
- If the cross-analysis reveals an obvious parameter-tuning candidate (e.g., HRP + only_non_normal substantially outperforms always_on inverse-vol), add a backlog entry recommending follow-up.

This batch is research validation only. No strategy code, broker adapter, paper-trading API, or new universe is introduced.

## Hard Decisions

- B017 is a **Codex-only batch**. State flow `new → planning → verifying → done` (no `building` phase). All four features have `executor: codex`.
- No new code is written. Both report generators and the snapshot acquisition pipeline already exist (from B014, B015, B016).
- Network access is required exactly once, for `scripts/fetch_yfinance_regime_adaptive_csvs.py`. User authorized this one-time fetch for the B016 batch (carried forward from B014's user authorization of public yfinance access). All other Codex work is offline.
- Snapshot raw CSVs are gitignored under `data/public-cache/`. Only the manifest is observable (and even the manifest is gitignored per project-status memory). Codex inspects manifest sha256 fingerprints in the acquisition log without committing the raw data.
- Acquired snapshot must satisfy the established constraints: 8 non-SGOV tickers >=95% expected business-day coverage; SGOV is the only allowed short-history ticker (inception 2020-05-28); other tickers cover 2018-01-01 through 2025-12-31.
- Comparison window: 2020-06-01..2022-12-31 (overlapping window where SGOV is fully available, established in B014 and reused by B015 + B016).
- Stress sub-windows: 2020-02-01..2020-12-31 (COVID) and 2022-01-01..2022-12-31 (inflation), inherited from B013/B014 spec.
- Configurations to evaluate empirically:
  - **B015 three activation policies on B013** (using B013's default weighting + universe + L2 + L3): `always_on` (baseline), `only_non_normal`, `only_crisis`.
  - **B016 two weighting methods on B010** (using B010's default universe + lookback + target vol): `inverse_volatility` (baseline), `hrp`.
  - **B014 static 60/40 baseline**: reused from `docs/test-reports/B014-regime-adaptive-cross-strategy-comparison-2026-05-14.json` sidecar (no recompute needed since it's deterministic per window).
- B015 and B016 vary different strategies (B015 modifies B013; B016 modifies B010). They do not stack into a 3×2 matrix. The cross-analysis treats them as parallel research questions over the same real snapshot.
- Empirical pass/fail criteria:
  - **B015 stress gate**: each of the three activation policies must produce 2020 max DD < -15% AND 2022 max DD < -15% to count as preserving B013's stress-shield property. If a policy breaches, that's a research finding, not a B017 defect — note it explicitly in signoff.
  - **B016 stress gate**: both weighting methods should be checked at the same -15% threshold for 2020 / 2022 windows on B010's universe. Same finding-not-defect rule.
- Signoff verdict for B017 itself is `pass` if: acquisition completes cleanly, both reports regenerate without error, cross-analysis runs, and signoff is produced. The empirical numbers are reported as findings, not gating.
- All reports / logs / signoff include the research-only disclaimer.
- No mutation of any strategy code, any spec under `docs/specs/B0xx`, or any test. B017 only adds reports under `docs/test-reports/` and (if warranted) entries to `framework/proposed-learnings.md` and `backlog.json`.
- Local checks (`pytest`, `ruff`, `compileall`, `mypy`) must remain green throughout B017 — but Codex does not modify code, so this should be a no-op verification.

## Reference Documents

- `docs/specs/B014-regime-adaptive-stress-validation-spec.md`
- `docs/specs/B015-regime-adaptive-activation-policy-spec.md`
- `docs/specs/B016-risk-parity-hrp-upgrade-spec.md`
- `docs/test-reports/B014-regime-adaptive-stress-validation-signoff-2026-05-14.md`
- `docs/test-reports/B014-regime-adaptive-cross-strategy-comparison-2026-05-14.md`
- `docs/test-reports/B014-regime-adaptive-cross-strategy-comparison-2026-05-14.json`
- `docs/test-reports/B015-regime-adaptive-activation-policy-signoff-2026-05-14.md`
- `docs/test-reports/B015-regime-adaptive-activation-policy-comparison-2026-05-14.md` (current synthetic-fixture version, to be regenerated)
- `docs/test-reports/B016-risk-parity-hrp-upgrade-signoff-2026-05-15.md`
- `docs/test-reports/B016-risk-parity-hrp-comparison-2026-05-14.md` (current synthetic-fixture version, to be regenerated)
- `scripts/fetch_yfinance_regime_adaptive_csvs.py`
- `scripts/acquire_regime_adaptive_snapshot.py`
- `scripts/generate_b015_activation_policy_report.py`
- `scripts/generate_b016_hrp_comparison_report.py`
- `docs/engineering/no-live-safety-guards.md`

## Proposed Implementation Shape

### Real Snapshot Acquisition (Codex)

Codex runs (with explicit opt-in flags):

```text
.venv/bin/python scripts/fetch_yfinance_regime_adaptive_csvs.py \
    --output-dir data/public-cache-staging \
    --from 2018-01-01 \
    --to 2025-12-31 \
    --i-understand-this-is-manual-research-data

.venv/bin/python scripts/acquire_regime_adaptive_snapshot.py \
    --source-dir data/public-cache-staging \
    --output-dir data/public-cache \
    --from 2018-01-01 \
    --to 2025-12-31 \
    --i-understand-this-is-manual-research-data
```

Verifies per-ticker coverage (8 non-SGOV ≥95%; SGOV exempt) and writes an acquisition log at `docs/test-reports/B017-real-data-validation-acquisition-log-2026-MM-DD.md` capturing per-ticker rows, sha256, first/last dates.

### B015 Report Regeneration (Codex)

```text
.venv/bin/python scripts/generate_b015_activation_policy_report.py \
    --output-dir docs/test-reports
```

Confirms the regenerated report's `real_data_status = "ran"`. Records 2020 / 2022 max DD per policy, full-window ending value per policy, regime label distribution per policy, L1 firing rate per policy. The committed report file at `docs/test-reports/B015-regime-adaptive-activation-policy-comparison-2026-05-15.md` (or today's date stamp) replaces the synthetic-fixture version.

### B016 Report Regeneration (Codex)

```text
.venv/bin/python scripts/generate_b016_hrp_comparison_report.py \
    --output-dir docs/test-reports
```

Confirms the regenerated report's `real_data_status = "ran"`. Records 2020 / 2022 max DD per method, full-window ending value per method, turnover per method. Committed report file at `docs/test-reports/B016-risk-parity-hrp-comparison-2026-05-15.md` (or today's date stamp).

### Cross-Analysis And Signoff (Codex)

Produces `docs/test-reports/B017-real-data-validation-signoff-2026-MM-DD.md` containing:

- **B015 verdict per activation policy**: 2020 max DD, 2022 max DD, full-window ending value, vs B013 always_on baseline, vs static 60/40 baseline.
- **B016 verdict per weighting method**: 2020 max DD, 2022 max DD, full-window ending value, vs B010 inverse_volatility baseline, vs static 60/40 baseline.
- **Narrative answering the two research questions**:
  - Does `only_non_normal` or `only_crisis` shrink B013's gap vs 60/40? By how many percentage points?
  - Does HRP shrink B010's gap vs 60/40? By how many percentage points?
- **Soft-watch** for any surprising findings (e.g., one configuration violating the -15% stress threshold, or a configuration dramatically outperforming).
- **Framework Learnings**: if a clear parameter retuning candidate emerges, add a `framework/proposed-learnings.md` entry recommending follow-up batch.
- **Backlog entries**: if cross-analysis suggests a "HRP × non-normal activation" hybrid is worth exploring, add a new BL-B017-* entry.
- Research-only disclaimer.

## Feature Requirements

### F001 Real Snapshot Acquisition

Executor: codex.

Run the yfinance fetcher and acquire script in sequence using the established opt-in flags. Verify per-ticker coverage thresholds (8 non-SGOV ≥95% expected business days; SGOV inception 2020-05-28 exempt). Write acquisition log at `docs/test-reports/B017-real-data-validation-acquisition-log-2026-MM-DD.md` capturing sha256 fingerprints, row counts, first/last dates per ticker. Raw CSVs remain gitignored. If any non-SGOV ticker fails the coverage bar or any other fetch fails, abort B017 with explicit diagnostic — do not silently proceed with bad data.

### F002 Regenerate B015 Real-Data Report

Executor: codex.

Run `scripts/generate_b015_activation_policy_report.py` with the manifest now present. Confirm the new report's `real_data_status = "ran"` (or equivalent). Extract per-policy empirical numbers: 2020-02-01..2020-12-31 max DD, 2022-01-01..2022-12-31 max DD, 2020-06-01..2022-12-31 ending value, regime label counts, L1 firing rate. Commit the regenerated `docs/test-reports/B015-regime-adaptive-activation-policy-comparison-2026-MM-DD.md` + JSON sidecar.

### F003 Regenerate B016 Real-Data Report

Executor: codex.

Run `scripts/generate_b016_hrp_comparison_report.py` with the manifest present. Confirm `real_data_status = "ran"`. Extract per-method empirical numbers: 2020 max DD, 2022 max DD, full-window ending value, annualized Sharpe, turnover, per-asset average weight. Commit the regenerated `docs/test-reports/B016-risk-parity-hrp-comparison-2026-MM-DD.md` + JSON sidecar.

### F004 Cross-Analysis And Evidence-Backed Signoff

Executor: codex.

Produce `docs/test-reports/B017-real-data-validation-signoff-2026-MM-DD.md` with cross-analysis answering both research questions:

- **B015**: does `only_non_normal` / `only_crisis` shrink B013's vs-60/40 gap, and by how much? Are 2020/2022 stress drawdowns still under 15%?
- **B016**: does HRP shrink B010's vs-60/40 gap, and by how much? Are 2020/2022 stress drawdowns still under 15%?

Add **framework/proposed-learnings.md** entries for any actionable parameter retuning candidates. Add **backlog.json** entries for any worth-exploring hybrid configurations (e.g., HRP + activation_policy). Update `progress.json` `evaluator_feedback` and `docs.signoff` per Harness convention. Local checks (`pytest`, `ruff`, `compileall`, `mypy`) must remain green — should be no-op since no code is modified.

## Acceptance Summary

B017 is complete only when:

- Real yfinance 9-asset snapshot (2018-2025) is acquired and registered as a manifest at `data/public-cache/regime-adaptive-prices-manifest.json`. Raw CSVs remain gitignored.
- Acquisition log committed at `docs/test-reports/B017-real-data-validation-acquisition-log-2026-MM-DD.md`.
- `docs/test-reports/B015-regime-adaptive-activation-policy-comparison-2026-MM-DD.md` regenerated with `real_data_status = "ran"` and committed.
- `docs/test-reports/B016-risk-parity-hrp-comparison-2026-MM-DD.md` regenerated with `real_data_status = "ran"` and committed.
- `docs/test-reports/B017-real-data-validation-signoff-2026-MM-DD.md` produced with empirical 2020 / 2022 max DD per configuration, gap-vs-60/40 narrative answering both research questions, and any soft-watch / framework-learnings / backlog entries.
- Local checks remain green (no-op since B017 modifies no code).
- No mutation of any strategy code, any spec under `docs/specs/B0xx`, or any test.
- No new third-party SDK / broker / AI / paper / live execution surface introduced; only the existing opt-in yfinance fetcher performs a one-time network call.
- All reports carry the research-only disclaimer.
