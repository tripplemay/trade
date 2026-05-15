# B015 Regime-Adaptive Activation Policy Spec

## Background

B014 closed the empirical stress validation gate for B013 (2020 max DD -4.76%, 2022 max DD -1.66%, both well under -15%). The same batch's cross-strategy comparison surfaced an actionable research finding: in the calm window 2020-06-01..2022-12-31, the regime-adaptive strategy ($126,726) underperformed a simple static 60/40 ($158,978) by ~25 percentage points of cumulative return. B013's three-layer defensive cascade was paying premium for crisis insurance every period — including months where no crisis was present.

The natural follow-up question: **can the strategy keep its low-drawdown crisis shield while recovering more of the bull-market upside?** B015 takes the smallest defensible step toward that goal: make B013's L1 200-day SMA trend gating *conditional on the current regime label*, controlled by an explicit configurable policy. L2 (inverse-volatility weighting + 8% vol target) and L3 (regime detection + crisis exposure cut) remain unchanged. The L3 crisis cut by design only fires in CRISIS regime; L1 is the layer responsible for the persistent defensive bias in NORMAL.

B015 is research validation, not a new strategy. The default configuration preserves B013's signoff behavior exactly — backwards compatibility is a hard requirement.

> Cross-link (B019, 2026-05-15): the activation-policy comparison sidecars produced by B015 were captured under the prior B013 default `target_volatility=0.08`. After B019 F003 retuned B013 to `target_volatility=0.11`, a re-run of the activation-policy comparison harness under the new default is recorded in `docs/test-reports/B019-b015-activation-policy-rerun-2026-05-15.{json,md}`. The historical B015 sidecars are immutable; consult the B019 rerun for the current default behavior.

## Goal

Implement a minimal, testable Regime-Adaptive Activation Policy extension that:

- Adds a `regime_activation_policy` configuration field to `RegimeAdaptiveConfig` with three values: `always_on` (current B013 behavior, default), `only_non_normal` (L1 gating active in BEAR + CRISIS, skipped in NORMAL), `only_crisis` (L1 gating active in CRISIS only, skipped in NORMAL + BEAR).
- When the active policy says "L1 is skipped" for the current regime label, the per-asset 200-day SMA gating is bypassed: every non-defensive asset is treated as ungated and flows into L2 inverse-vol weighting. SGOV defensive routing for residual exposure (from L2 vol-target capping) remains in place.
- L2 (inverse-vol + 8% vol target + exposure scaling capped at 1.0) and L3 (regime detection + 50% non-defensive exposure cut on CRISIS) behavior remain unchanged across all three policies.
- Default `regime_activation_policy = always_on` so existing callers — including the B011 Master Portfolio's `regime_adaptive` sleeve registration — observe no behavior change.
- On the real B014 yfinance snapshot, run a comparative backtest across the three policies and produce a research report quantifying the trade-off (max DD vs cumulative return) for each policy on the 2020 and 2022 stress windows plus the broader 2020-06-01..2022-12-31 calm window.
- Extend the B014-style cross-strategy comparison to include all three policies of B013 alongside B006 momentum, B010 risk parity, and static 60/40 baseline.
- Add safety-guard regression coverage proving B015 introduces no new forbidden imports or environment access, and proving the `always_on` policy reproduces B013 signoff behavior bit-for-bit on the synthetic fixture.
- Close with independent Codex L1 verification.

This batch is a B013 parameter expansion + research validation; it does not introduce a new strategy module, broker adapter, paper-trading API, or new universe.

## Hard Decisions

- `regime_activation_policy` lives on `RegimeAdaptiveConfig` and is the single configuration knob this batch adds. No other parameters are added or modified in B015.
- Default value: `regime_activation_policy = "always_on"`. The B011 Master Portfolio `regime_adaptive` sleeve registration and any existing call sites must continue to work without modification and produce identical outputs.
- Three values supported:
  - `always_on`: L1 gating active in `NORMAL`, `BEAR`, `CRISIS`.
  - `only_non_normal`: L1 gating active in `BEAR`, `CRISIS`; skipped in `NORMAL`.
  - `only_crisis`: L1 gating active in `CRISIS`; skipped in `NORMAL`, `BEAR`.
- Validation: enum value must be one of the three strings; any other value → `ValueError` at config construction.
- When L1 is **skipped** for a regime, the trend-gating layer returns "ungated, full weight available" for every non-defensive asset for that signal date. SGOV (defensive sleeve) is never affected by L1 activation; defensive routing of residual exposure (from L2 target-vol capping or L3 crisis cut) remains intact in all policies.
- L2 inverse-vol weighting and 8% target volatility scaling apply to whatever assets L1 hands over. No changes to L2 logic. No new vol-target multiplier per regime.
- L3 regime detection logic is unchanged. CRISIS exposure halving still applies regardless of activation policy. The activation policy gates only L1.
- The activation policy is a runtime decision per signal date: the regime label computed by L3 (or pre-known for the period) is the input to "should L1 fire this period?". The regime label itself is computed using B013's existing logic (Fast/Slow vol ratio + SPY 200-SMA trend) and is unaffected by activation policy.
- Master Portfolio backwards-compat: existing B011 sleeve registration uses default `always_on`, so B011 signoff invariants and tests pass without modification. Users may pass a non-default `RegimeAdaptiveConfig` through any sleeve factory but B015 does not change the default factory signature.
- All artifacts research-only. Reports, logs, and docstrings carry the research-only disclaimer. Tests assert absence of `paper-execution`, `live-execution`, `executed-order`, `filled`, `place_order`, `submit_order` phrasing in B015 outputs.
- Real B014 yfinance snapshot is reused as-is. If the manifest is absent in CI, the comparative backtest report status is `skipped` for the real-data portion; the synthetic-fixture comparison still runs.
- The B013 signoff stress gate (`2020 max DD < 0.15` AND `2022 max DD < 0.15`) is re-evaluated for `only_non_normal` and `only_crisis` policies on the real snapshot. Pass / fail per policy is recorded; B013's `always_on` default is the canonical baseline. **No B013 strategy code is mutated in B015** — the activation policy is the only behavior switch and it is opt-in via config.
- No broker, paper/live trading, real account data, secrets in strategy modules, AI execution, cloud deployment, or frontend dashboard.
- Default CI continues to use synthetic fixtures and remains fixture/mock-first. The real-snapshot comparative backtest is exercised by an explicit research-mode test that is skipped if the manifest is absent.
- yfinance and the fetcher script remain unchanged; B015 does not perform network I/O.

## Reference Documents

- `docs/specs/B014-regime-adaptive-stress-validation-spec.md`
- `docs/specs/B013-regime-adaptive-multi-asset-mvp-spec.md`
- `docs/specs/B010-risk-parity-backtest-mvp-spec.md`
- `docs/specs/B011-portfolio-allocation-risk-mvp-spec.md`
- `docs/test-reports/B013-regime-adaptive-multi-asset-mvp-signoff-2026-05-14.md`
- `docs/test-reports/B014-regime-adaptive-stress-validation-signoff-2026-05-14.md`
- `docs/test-reports/B014-regime-adaptive-cross-strategy-comparison-2026-05-14.md`
- `docs/test-reports/B014-regime-adaptive-stress-validation-2026-05-14.md`
- `docs/strategy/00-master-portfolio-allocation.md`
- `docs/prd/mvp-prd.md`
- `docs/engineering/testing-and-fixture-policy.md`
- `docs/engineering/no-live-safety-guards.md`
- `docs/engineering/backtest-report-schema.md`

## Proposed Implementation Shape

### Configuration Extension

`trade/strategies/regime_adaptive/config.py`:

- Add module-level `RegimeActivationPolicy` literal type `Literal["always_on", "only_non_normal", "only_crisis"]` (or equivalent enum).
- Add `regime_activation_policy: RegimeActivationPolicy = "always_on"` field to `RegimeAdaptiveConfig` dataclass.
- Validation: any string outside the three accepted values raises `ValueError` with diagnostic naming the bad value and listing the valid choices.
- `parameter_hash` (or equivalent) must include `regime_activation_policy` so two configs differing only in this field produce different hashes.

### L1 Gating Policy Gate

`trade/strategies/regime_adaptive/trend_gating.py` (or wherever L1 lives):

- Existing `apply_trend_gating(prices, config)` keeps its signature.
- New helper `should_l1_gate_run(regime_label, policy)` returns `bool`:
  - `policy == "always_on"` → `True` for any regime.
  - `policy == "only_non_normal"` → `True` if regime in `{BEAR, CRISIS}`, else `False`.
  - `policy == "only_crisis"` → `True` if regime == `CRISIS`, else `False`.
- The backtest workflow (`trade/strategies/regime_adaptive/backtest.py`) invokes `should_l1_gate_run(regime_state.regime, config.regime_activation_policy)` after L3 produces the regime label. When `False`, the workflow bypasses `apply_trend_gating` and treats every non-defensive asset as ungated for that signal date.
- SGOV (defensive sleeve) is unaffected by activation policy. L1 is only relevant for non-defensive assets.
- Per-period rebalance trace records the active policy plus an explicit `l1_active: bool` flag so reports can show when L1 was skipped.

### Comparative Backtest On Real Snapshot

A new opt-in research-mode test or harness (NOT default CI) that, given the B014 manifest exists, runs three backtests over 2020-02-01..2022-12-31 (or the snapshot's full overlapping window):

- B013 with `always_on` (canonical baseline).
- B013 with `only_non_normal`.
- B013 with `only_crisis`.

For each policy, records: annualized return, annualized volatility, Sharpe, max DD (full window), 2020-stress-window max DD, 2022-stress-window max DD, turnover, regime label distribution (counts of NORMAL/BEAR/CRISIS periods), percent of periods where L1 actually fired.

The comparative report places these three rows alongside cached B006 momentum, B010 risk parity, and static 60/40 baseline rows from B014's comparison sidecar (or recomputed in B015 — implementer's choice based on whichever is more reliable).

### Reports

JSON/Markdown comparative report at `docs/test-reports/B015-regime-adaptive-activation-policy-comparison-2026-MM-DD.md` + JSON sidecar. Contents:

- Per-policy metrics table (3 B013 policies + B006 + B010 + 60/40).
- 2020 + 2022 stress gate verdict per B013 policy (must remain `pass` on `always_on`; may or may not pass on the other two — research finding either way).
- L1 firing rate per policy (e.g., `only_non_normal` may have L1 firing ~30% of periods; `only_crisis` ~5%).
- Notes on whether the cumulative-return gap vs 60/40 shrank under `only_non_normal` or `only_crisis`.
- Research limitations and the research-only disclaimer.

If real snapshot absent in CI: comparison runs on synthetic fixture only and report flags real-data section as `skipped`.

### Safety And Regression

- `regime_activation_policy = "always_on"` must produce bit-for-bit identical outputs to B013 signoff behavior on the synthetic fixture: full B013 test suite passes unchanged, the new code paths are inert.
- New code does not introduce any new third-party import, env reads, network I/O, or forbidden broker/AI SDK reference.
- B011 Master Portfolio tests continue to pass without modification (default `always_on` preserves the 0-weight sleeve invariant).
- B014 fetcher and snapshot importer remain untouched.
- Required local checks must pass: pytest, ruff, compileall, mypy.

## Feature Requirements

### F001 Configuration Field And Validation

Executor: generator.

Add `regime_activation_policy` to `RegimeAdaptiveConfig` with literal type `Literal["always_on", "only_non_normal", "only_crisis"]` and default `"always_on"`. Validation rejects any other string with a diagnostic listing valid choices. `parameter_hash` (or equivalent) includes the new field so configs differing only here produce distinct hashes. Tests cover default construction, the three valid values, invalid-string rejection, and hash distinctness across the three policies.

### F002 L1 Gating Respects Activation Policy

Executor: generator.

Add `should_l1_gate_run(regime_label, policy) -> bool` helper covering the three-policy × three-regime truth table. In the backtest workflow, after L3 produces the regime label, route through `should_l1_gate_run`; when it returns `False`, bypass `apply_trend_gating` and treat all non-defensive assets as ungated for that signal date. Record `l1_active: bool` on the per-period rebalance trace. SGOV defensive routing remains in place. Tests cover all 9 combinations (3 policies × 3 regimes), trace flag correctness, and the invariant that `always_on` always fires L1.

### F003 Comparative Backtest On Real Snapshot

Executor: generator.

Add a research-mode comparative backtest harness that, when the B014 manifest exists, runs B013 with each of the three activation policies on the real snapshot over the full overlapping window (and the 2020 + 2022 stress sub-windows). Records per-policy: annualized return, annualized volatility, Sharpe, max DD per window, turnover, regime label distribution, L1 firing rate. If the manifest is absent, the real-data section is `skipped` and the harness still runs on the synthetic fixture for at least a smoke test. Default CI does not require the manifest.

### F004 Comparative Report And Cross-Strategy Extension

Executor: generator.

Emit `docs/test-reports/B015-regime-adaptive-activation-policy-comparison-2026-MM-DD.md` + JSON sidecar with: per-policy metrics table for the three B013 policies, cross-strategy rows for B006 momentum + B010 risk parity + static 60/40 (reuse B014's comparison sidecar where possible; recompute only what is missing), 2020 + 2022 stress verdict per B013 policy, L1 firing rate per policy, narrative note on whether the absolute-return gap vs 60/40 shrank under `only_non_normal` / `only_crisis`. Reports include the research-only disclaimer.

### F005 Backwards-Compat And Safety Regression

Executor: generator.

Prove that `regime_activation_policy = "always_on"` reproduces B013 signoff behavior exactly on the synthetic fixture: the full pre-existing B013 test suite passes without modification, no equity-curve or weight-history deltas vs the prior-batch fixture-based golden outputs. Add B015-specific regression tests confirming no new broker/AI SDK imports, no `os.environ` reads in strategy modules, no socket I/O during fixture runs, no paper/live execution phrasing in B015 outputs. Required local checks must pass: pytest, ruff, compileall, mypy.

### F006 Independent Evaluation

Executor: codex.

Evaluator runs local/CI-safe L1 verification. Must confirm: `regime_activation_policy` enum + validation works; `should_l1_gate_run` truth table is correct across all 9 combinations; `always_on` reproduces B013 behavior bit-for-bit on the synthetic fixture (B013 signoff backwards-compat); the comparative report exists; if the real B014 snapshot is present, the three-policy comparison numbers are consistent with the report's narrative; if absent, the real-data section is `skipped` not failed; all safety guards remain intact. Produce review and signoff under `docs/test-reports/`. Signoff notes whether `only_non_normal` or `only_crisis` shrank the absolute-return gap vs 60/40 (empirical research finding, not a pass/fail criterion).

## Acceptance Summary

B015 is complete only when:

- Required local checks pass: pytest, ruff, compileall, mypy.
- `RegimeAdaptiveConfig.regime_activation_policy` field exists, validates, and is included in `parameter_hash`.
- `should_l1_gate_run(regime_label, policy)` returns the correct bool for all 9 combinations.
- The backtest workflow bypasses L1 when `should_l1_gate_run` returns `False` and records `l1_active` on the per-period rebalance trace.
- The default `regime_activation_policy = "always_on"` reproduces B013 signoff behavior bit-for-bit on the synthetic fixture; the full pre-existing B013 test suite passes without modification.
- The B011 Master Portfolio `regime_adaptive` sleeve registration continues to pass without modification; existing B011 invariants preserved.
- Comparative report at `docs/test-reports/B015-regime-adaptive-activation-policy-comparison-2026-MM-DD.md` exists with three B013 policy rows + B006 + B010 + 60/40 rows + 2020/2022 stress verdict per policy + L1 firing rate + narrative note on the absolute-return gap vs 60/40.
- No new forbidden imports, no env reads, no network I/O on default fixture runs, no paper/live execution phrasing in B015 outputs.
- Evaluator signs off F006 with explicit notes on backwards-compat and whether `only_non_normal` or `only_crisis` shrank the absolute-return gap.
