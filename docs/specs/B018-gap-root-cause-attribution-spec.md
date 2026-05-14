# B018 B013/B010 vs 60/40 Gap Root-Cause Attribution Spec

## Background

B017 produced two empirical negative findings on the B014 yfinance real snapshot (2020-06-01..2022-12-31 calm window):

- **B015 conclusion**: regime-aware L1 activation policy does NOT shrink B013's absolute-return gap vs static 60/40. `only_crisis` is +$257 vs `always_on` baseline (negligible) but worsens 2022 max DD from -0.51% to -7.72% (15× degradation). `only_non_normal` is worse by -$3,148. **L1 trend gating is NOT the gap source.**
- **B016 conclusion**: HRP weighting does NOT shrink B010's absolute-return gap vs static 60/40. HRP is -$496 vs `inverse_volatility` baseline AND turnover increased 41%. **Weighting algorithm choice is NOT the gap source.**

Both stress gates remained safe (no 2020/2022 max DD breached -15%), so neither result is a code defect. But the **real source of the $32k (B013) / $55k (B010) gap remains an open research question** with several plausible candidates:

- L2 8% portfolio volatility target is too conservative — forces persistent low total exposure (exposure_scale << 1.0) and routes residual to defensive sleeve.
- Defensive sleeve drag — SGOV (~3-4% annualized) + bonds + gold absorbed ~30-50% of capital while equities returned 30%+ in the same window.
- Universe choice — B013's 9-asset universe (4 risk_core + 4 stabilizers + 1 defensive) systematically under-weights pure equity vs 60/40's 2-asset (SPY + bond) bias.
- Inverse-vol weighting bias — within the L2 step, inverse-vol over-weights low-vol assets (bonds, gold, SGOV) which under-perform in calm periods.
- Rebalance cadence — monthly rebalance may chop up trends; quarterly or annual might capture more upside.

Without quantifying which factor contributes how much, any further "optimization" (e.g., satellite strategies, smoothed vol, VIX overlay) risks being applied at the wrong layer. B018 is a focused empirical attribution batch that decomposes the gap into measurable contributions per candidate factor and produces a diagnostic report with Pareto-style parameter recommendations (concrete trade-offs: "vol_target X gives Y% gap reduction at Z% max-DD cost").

**B018 is research diagnostic, not a strategy code change.** It does not modify B010/B011/B013/B015/B016 defaults. If B018 surfaces an actionable parameter retune, that becomes a candidate for a follow-up batch (B019+); B018 stops at the recommendation.

## Goal

Implement a minimal, testable gap root-cause attribution extension that:

- Adds a **P&L attribution decomposition** module that, given a backtest result and a benchmark equity curve, computes per-asset and per-period contribution to the absolute-return gap. Reusable for B010 and B013 against the static 60/40 baseline already cached by B014.
- Adds a **parameter sweep harness** that, on the B014 yfinance real snapshot, runs B010 and B013 with parameter variations along three axes:
  - **Vol target sweep**: `target_volatility ∈ {0.05, 0.08, 0.10, 0.12, 0.15}` (5 values)
  - **Universe ablation**: full 9-asset (control), drop SGOV, drop all stabilizers (only 4 risk_core + 1 defensive), only SPY + IEF (60/40-like), only SPY (single-asset). 4-5 variants.
  - **Rebalance cadence**: monthly (control), quarterly, semi-annual, annual. 3-4 variants.
- Each parameter variant runs both B010 and B013 on the real snapshot 2020-06-01..2022-12-31 window plus the 2020 and 2022 stress sub-windows; records ending value, gap vs 60/40, 2020 / 2022 max DD, turnover, total transaction costs, Sharpe.
- Synthesizes a **diagnostic report** that:
  - Identifies the largest contributor to the gap (per-layer attribution: L2 vol scaling vs defensive drag vs universe vs cadence vs weighting).
  - Produces **Pareto-style parameter recommendations**: at least 3 configurations spanning low-DD / balanced / high-return with concrete trade-off numbers ("config X: gap shrinks Y%, but 2022 max DD goes from -A% to -B%").
  - Notes which factors are essentially trade-offs (cannot be optimized away) and which are tunable.
- Closes with independent Codex L1 verification + signoff. Codex may optionally add a `BL-B018-*` backlog entry if a clear actionable retune candidate emerges (e.g., "vol_target=12% Pareto-dominates 8% on this window — candidate for B019 retune batch").

**B018 does NOT modify any strategy default parameters, any spec under `docs/specs/B0xx`, or any existing strategy module behavior.** It only adds new analysis modules + tests + reports. All artifacts research-only.

## Hard Decisions

- B018 is a **mixed batch**: generator delivers attribution + sweep harnesses (F001-F002); Codex executes against real snapshot + writes diagnostic report + signoff (F003-F005). State flow `new → planning → building → verifying → done`.
- New code lives at:
  - `trade/analysis/pnl_attribution.py` (P&L decomposition module, pure stdlib)
  - `trade/analysis/parameter_sweep.py` (sweep harness, pure stdlib)
  - `scripts/generate_b018_attribution_report.py` (CLI wrapper)
- Pure-stdlib like the rest of `trade/`. No scipy / numpy / pandas / sklearn / networkx / new third-party deps.
- B018 reuses:
  - B014 yfinance manifest at `data/public-cache/regime-adaptive-prices-manifest.json` (acquired in B017 — assumed present this session for evaluator; if absent in checkout, the report runs in `skipped` mode like B015/B016 patterns).
  - B014 static 60/40 baseline sidecar at `docs/test-reports/B014-regime-adaptive-cross-strategy-comparison-2026-05-14.json` for the gap reference.
  - Existing B010 / B013 backtest entry points (no modification).
- Vol target sweep: 5 values × 2 strategies (B010, B013) × 1 main window + 2 stress windows = 30 backtest runs. Deterministic; cached per (params, snapshot_id) hash.
- Universe ablation: 4-5 variants × 2 strategies × 3 windows = ~30 runs.
- Rebalance cadence sweep: 3-4 variants × 2 strategies × 3 windows = ~24 runs.
- Total parameter sweep budget: ~80-100 backtest runs. Each B013 monthly backtest on 3-year window completes in seconds, so total wall time should be well under 5 minutes. Acceptable.
- **B010 and B013 default parameters are NOT modified.** Each sweep variant constructs an override config object inline; the strategy's default config is read but never mutated.
- B011 master portfolio invariants preserved — B018 does not touch master portfolio at all.
- Synthetic-fixture path: if B014 manifest is absent, attribution + sweep run on a synthetic 9-asset fixture (smaller, deterministic) so default CI stays green. The diagnostic report flags `real_data_status = "skipped"` per established B015/B016 pattern.
- All artifacts research-only. Reports, logs, docstrings carry the research-only disclaimer. Tests assert absence of `paper-execution`, `live-execution`, `executed-order`, `filled`, `place_order`, `submit_order` phrasing in B018 outputs.
- No mutation of any B013/B010/B011/B012/B014/B015/B016/B017 strategy code, test, or spec.
- No new broker / paper / live / AI surface; no env reads in strategy modules; no socket I/O on fixture runs.
- Required local checks must pass: pytest, ruff, compileall, mypy.

## Reference Documents

- `docs/specs/B010-risk-parity-backtest-mvp-spec.md`
- `docs/specs/B013-regime-adaptive-multi-asset-mvp-spec.md`
- `docs/specs/B014-regime-adaptive-stress-validation-spec.md`
- `docs/specs/B015-regime-adaptive-activation-policy-spec.md`
- `docs/specs/B016-risk-parity-hrp-upgrade-spec.md`
- `docs/specs/B017-b015-b016-real-data-validation-spec.md`
- `docs/test-reports/B017-real-data-validation-signoff-2026-05-15.md` (empirical baseline this batch builds on)
- `docs/test-reports/B015-regime-adaptive-activation-policy-comparison-2026-05-15.{md,json}` (real-data B015 numbers)
- `docs/test-reports/B016-risk-parity-hrp-comparison-2026-05-15.{md,json}` (real-data B016 numbers)
- `docs/test-reports/B014-regime-adaptive-cross-strategy-comparison-2026-05-14.{md,json}` (static 60/40 baseline sidecar)
- `framework/proposed-learnings.md` (B017 entries: "synthetic vs real reversal" + "gap source unknown")
- `docs/strategy/00-master-portfolio-allocation.md`
- `docs/strategy/02-risk-parity-vol-target.md`
- `docs/prd/mvp-prd.md`
- `docs/engineering/testing-and-fixture-policy.md`
- `docs/engineering/no-live-safety-guards.md`
- `docs/engineering/backtest-report-schema.md`

## Proposed Implementation Shape

### P&L Attribution Module

`trade/analysis/pnl_attribution.py` (new):

```python
# Pure-stdlib P&L attribution. Research-only.

def compute_per_asset_contribution(
    backtest_result: BacktestResult,
    benchmark_equity_curve: Sequence[tuple[date, float]],
) -> dict[str, float]: ...
# Per-asset cumulative-return contribution gap. For B013: returns
# {'SPY': +X, 'IEF': -Y, 'SGOV': -Z, ...} where positive means strategy
# benefited from this asset vs benchmark; negative means it dragged.

def compute_per_layer_contribution(
    backtest_result: BacktestResult,
    benchmark_equity_curve: Sequence[tuple[date, float]],
) -> dict[str, float]: ...
# Per-layer attribution: 'l1_gating', 'l2_vol_scaling',
# 'defensive_routing', 'l3_crisis_cut' for B013; 'l2_vol_scaling',
# 'defensive_routing' for B010. Sums approximately match the
# total gap.

def attribution_summary(
    backtest_result: BacktestResult,
    benchmark_equity_curve: Sequence[tuple[date, float]],
) -> AttributionReport: ...
# Combined per-asset + per-layer + total gap.
```

Pure stdlib (math + statistics + dataclasses + typing). No third-party deps. Deterministic. Edge cases: empty backtest, missing periods, single-asset backtest.

### Parameter Sweep Harness

`trade/analysis/parameter_sweep.py` (new):

```python
# Pure-stdlib parameter sweep harness. Research-only.

@dataclass(frozen=True, slots=True)
class SweepDimension:
    name: str  # 'vol_target' | 'universe' | 'cadence'
    values: Sequence[Any]

@dataclass(frozen=True, slots=True)
class SweepRunResult:
    strategy: str  # 'b010' | 'b013'
    dimension: str
    value: Any
    window: str  # '2020_06_to_2022_12' | '2020_stress' | '2022_stress'
    ending_value: float
    gap_vs_60_40: float
    max_drawdown: float
    turnover: float
    transaction_costs: float
    sharpe: float

def run_vol_target_sweep(
    snapshot_records: Mapping[str, Sequence[DailyBar]],
    strategy_name: str,
    targets: Sequence[float],
    windows: Sequence[tuple[date, date]],
) -> list[SweepRunResult]: ...

def run_universe_ablation_sweep(
    snapshot_records: Mapping[str, Sequence[DailyBar]],
    strategy_name: str,
    variants: Sequence[tuple[str, Sequence[str]]],  # (variant_name, asset_subset)
    windows: Sequence[tuple[date, date]],
) -> list[SweepRunResult]: ...

def run_cadence_sweep(
    snapshot_records: Mapping[str, Sequence[DailyBar]],
    strategy_name: str,
    cadences: Sequence[str],  # 'monthly' | 'quarterly' | 'semiannual' | 'annual'
    windows: Sequence[tuple[date, date]],
) -> list[SweepRunResult]: ...
```

Each sweep iterates over the parameter values, constructs an override config inline (never mutates strategy defaults), runs the backtest, records the metrics. Cadence sweep may need careful handling if B010/B013 don't support all cadences natively — in that case, only supported cadences run, others are skipped with explicit note.

### Diagnostic Report

`docs/test-reports/B018-gap-attribution-2026-MM-DD.md` + JSON sidecar (Codex emits):

Sections:

1. **Real-data baseline recap** — B013/B010 vs 60/40 numbers from B017.
2. **Per-asset gap attribution** — for B013 and B010 on the calm window, which assets contributed positively / negatively vs 60/40.
3. **Per-layer gap attribution** — for B013, how much of the gap is L1 / L2 / defensive / L3.
4. **Vol target sweep results** — table + narrative: how does gap and max DD vary with `target_volatility`?
5. **Universe ablation results** — table + narrative: dropping SGOV / stabilizers / using minimal universe.
6. **Rebalance cadence sweep results** — table + narrative: monthly vs quarterly vs annual.
7. **Pareto recommendations** — at least 3 configurations spanning low-DD / balanced / high-return, with concrete trade-off numbers. Format:
   ```
   ## Config "balanced" — target_vol=0.10, universe=full, cadence=monthly
   - Ending value: 132,xxx (vs always_on B013 baseline 126,726 = +X%)
   - Gap vs 60/40: 26,xxx (vs always_on B013 baseline 32,252 = -Y%)
   - 2020 max DD: -2.X% (vs always_on -1.62%)
   - 2022 max DD: -1.X% (vs always_on -0.51%)
   - Trade-off: pays Δ DD for Δ gap reduction.
   ```
8. **Conclusion** — does any single factor dominate the gap? Or is it a sum of trade-offs? What's the cleanest follow-up?
9. **Research-only disclaimer.**

If B014 manifest absent in checkout: `real_data_status = "skipped"`; synthetic fixture results are reported with the same structure but explicit caveat. Default CI stays green either way.

### Safety And Regression

- New modules pure stdlib (math + statistics + dataclasses + typing + collections.abc). No scipy / numpy / pandas / sklearn / networkx / yfinance / broker / AI SDK imports.
- B010 / B013 / B011 / B015 / B016 strategy modules untouched.
- No mutation of strategy default parameters or master portfolio sleeve registrations.
- B018 modules: no `os.environ` / `os.getenv` reads; no socket I/O on default fixture runs.
- Reports / docstrings / logs include research-only disclaimer.
- All pre-existing tests pass without modification.
- Required local checks must pass: pytest, ruff, compileall, mypy.

## Feature Requirements

### F001 P&L Attribution Module + Unit Tests

Executor: generator.

Add `trade/analysis/pnl_attribution.py` (pure stdlib) with `compute_per_asset_contribution`, `compute_per_layer_contribution`, `attribution_summary` covering B010 (L2 vol_scaling + defensive_routing layers) and B013 (L1 gating + L2 vol_scaling + L3 crisis_cut + defensive_routing layers). Add `tests/unit/test_pnl_attribution.py` with deterministic unit tests on canned backtest results + canned benchmark curves; covers per-asset signs, per-layer sums approximately match total gap, edge cases (empty result, missing periods, single-asset backtest, missing benchmark dates). pytest / ruff / compileall / mypy all pass.

### F002 Parameter Sweep Harness + Unit Tests

Executor: generator.

Add `trade/analysis/parameter_sweep.py` (pure stdlib) with `run_vol_target_sweep` (5 values), `run_universe_ablation_sweep` (4-5 variants), `run_cadence_sweep` (3-4 variants). Each function takes pre-loaded snapshot records, strategy name, parameter values, and window tuples; returns deterministic `SweepRunResult` list. **Constructs override configs inline; never mutates strategy defaults.** Add `tests/unit/test_parameter_sweep.py` with mocked snapshot records: each sweep returns the expected number of results, results are deterministic across runs, override config does not leak into default, unsupported cadences are skipped with diagnostic. pytest / ruff / compileall / mypy all pass.

### F003 Real-Data Attribution Run

Executor: codex.

Runs `trade/analysis/pnl_attribution.py` against the B014 manifest (if present in `data/public-cache/`) for both B013 and B010 vs static 60/40 baseline (loaded from B014 sidecar). Produces per-asset contribution tables and per-layer attribution tables for the 2020-06-01..2022-12-31 calm window + 2020 + 2022 stress sub-windows. Outputs JSON sidecar `docs/test-reports/B018-gap-attribution-2026-MM-DD.json` (sections 1-3). If manifest absent, runs on synthetic 9-asset fixture and marks `real_data_status = "skipped"`.

### F004 Real-Data Parameter Sweeps

Executor: codex.

Runs all three parameter sweeps (vol_target, universe, cadence) against the B014 manifest for both B013 and B010. Appends sweep tables to the B018 JSON sidecar (sections 4-6). Each sweep result includes ending value, gap vs 60/40, 2020 max DD, 2022 max DD, turnover, costs, Sharpe.

### F005 Diagnostic Report + Pareto Recommendations + Codex Signoff

Executor: codex.

Emits the Markdown diagnostic report at `docs/test-reports/B018-gap-attribution-2026-MM-DD.md` combining F003 + F004 outputs into the spec'd 9 sections. Includes at least 3 Pareto-style configuration recommendations with concrete trade-off numbers ("config X: gap shrinks Y%, max DD changes from -A% to -B%"). Writes the B018 signoff at `docs/test-reports/B018-gap-attribution-signoff-2026-MM-DD.md` with: scope, verification (`pytest`, `ruff`, `mypy`, `compileall` all green), high-level findings, optional `backlog.json` BL-B018-* entry if a clear actionable retune candidate emerges. Updates `progress.json` `evaluator_feedback` and `docs.signoff` per Harness convention. **B018 itself does NOT modify B010 / B013 default parameters** — any retune is a follow-up batch candidate, not part of B018 acceptance.

## Acceptance Summary

B018 is complete only when:

- Required local checks pass: pytest, ruff, compileall, mypy.
- `trade/analysis/pnl_attribution.py` exists, is pure stdlib (no scipy/numpy/pandas/sklearn), has unit tests, and produces deterministic per-asset + per-layer attribution.
- `trade/analysis/parameter_sweep.py` exists, is pure stdlib, has unit tests, and runs all three sweeps deterministically; override configs do not mutate defaults.
- Real-data attribution run completes (or marks `skipped` if manifest absent) and emits JSON + Markdown report.
- Diagnostic report at `docs/test-reports/B018-gap-attribution-2026-MM-DD.md` contains all 9 spec'd sections, with at least 3 Pareto-style configuration recommendations spanning low-DD / balanced / high-return.
- Codex signoff at `docs/test-reports/B018-gap-attribution-signoff-2026-MM-DD.md` records empirical findings and optional backlog entry.
- B010 / B013 / B011 / B015 / B016 strategy modules and tests are untouched.
- No forbidden imports (scipy / numpy / pandas / sklearn / networkx / broker / AI); no env reads in strategy modules; no socket I/O on default fixture runs; no paper / live execution phrasing in B018 outputs.
- All reports carry the research-only disclaimer.
