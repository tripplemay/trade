# B019 B010 / B013 Cadence + Vol-Target Retune Spec

## Background

B018 (`docs/test-reports/B018-gap-attribution-signoff-2026-05-15.md`) ran systematic per-asset + per-layer attribution + three-axis sweep on the B014 yfinance real snapshot. Findings:

- `l2_vol_scaling` is the dominant drag on both B010 and B013.
- `l1_gating` is a secondary drag for B013 but not the root cause.
- `vol_target` and `cadence` are the actionable axes; `universe` ablation is mostly constrained by defensive-asset invariants and does not produce a clean dominance story.
- Specifically: **B010 quarterly cadence improves 2022 max DD from -1.06% to ~-0.12% while keeping calm-window ending value above 103k**; **10–12% vol_target raises ending value but increases drawdown** — the sweet spot is the joint search of these two axes.

`BL-B018-S1` was filed in `backlog.json` to evaluate this joint retune in a follow-up batch. **B019 is that batch.** The B018 sweep grid was coarse (`vol_target ∈ {0.05, 0.08, 0.10, 0.12, 0.15}`, `cadence ∈ {monthly, quarterly, semiannual, annual}`); B019 runs a fine grid in the neighborhood that B018 surfaced and decides — based on a deterministic 4-condition acceptance gate — whether to actually change B010 / B013 default parameters.

Per framework v0.9.21 #1 (`docs/engineering/testing-and-fixture-policy.md` §"Fixture vs Real-Data Signal Reversal"), any acceptance gate that compares returns / drawdown / turnover between variants must be re-verified on the real-data snapshot before signoff. B019's gate is evaluated exclusively on the B014 snapshot.

## Goal

Run a fine-grained `(cadence, vol_target)` sweep on the B014 yfinance real snapshot for B010 and B013, and **conditionally** modify B010 / B013 default parameters if and only if at least one configuration meets all four acceptance gates simultaneously. If the gate is met, also synchronize all downstream consumers (B011 Master Portfolio risk_parity sleeve, B014 stress baselines, B015 activation-policy comparison baselines) so the repository never carries an inconsistent state.

If no configuration meets the gate, B019 closes as a research-only PASS and a `BL-B019-S1` backlog entry is added to record "joint retune evaluated; gate not met" so future planners do not re-attempt the same search blindly.

## Hard Decisions

- **Two-stage execution**:
  - **Stage 1 (research)**: F001 widens the sweep harness to accept arbitrary `vol_target` grids and a single-cadence comparison helper; F002 (Codex) executes on the real snapshot, writes the report, and emits the explicit gate verdict.
  - **Stage 2 (conditional)**: F003 + F004 + F005 execute only when F002's gate verdict is `gate_met`. If `gate_not_met`, F003 and F004 are marked `skipped` with explicit reason; F005 still produces the signoff (research-only PASS).
- **Sweep grid**:
  - `vol_target ∈ {0.09, 0.10, 0.11, 0.12, 0.13}` (5 values, 1 % steps centered on the B018 sweet spot)
  - `cadence ∈ {monthly, quarterly}` (2 values; B018 already proved semiannual / annual are not Pareto frontier)
  - 5 × 2 = 10 cells × 2 strategies (B010, B013) × 3 windows (calm + 2 stress) = 60 backtest runs. All deterministic, all on the same snapshot hash.
- **Acceptance gate (all four must hold simultaneously for a single `(cadence, vol_target)` cell to qualify, evaluated against the matching strategy's current default)**:
  1. Calm-window ending value uplift `≥ +1 %` vs default
  2. Calm-window absolute gap vs static 60/40 narrowed by `≥ 5 percentage points`
  3. Both stress-window max drawdowns `≤` default's stress-window max drawdowns (do-no-harm)
  4. Calm-window turnover increase `≤ +15 %` vs default
- **Window definitions** (re-used from B018 for direct comparability):
  - Calm: 2020-06-01 .. 2022-12-31
  - Stress 1: 2020-02-01 .. 2020-12-31
  - Stress 2: 2022-01-01 .. 2022-12-31
- **Snapshot**: B014 yfinance manifest at `data/public-cache/regime-adaptive-prices-manifest.json` (snapshot id `regime-adaptive:b69883b08eedea7d`, established by B017 / B018).
- **Winner selection** (when multiple cells qualify): the cell with the highest calm-window ending value. Ties broken by lower stress-2 max DD, then by lower turnover.
- **Pure stdlib trade/ module**: B019's harness extension does not introduce scipy / numpy / pandas / sklearn / networkx / yfinance / broker / AI SDK imports. The `trade/analysis/parameter_sweep.py` module remains pure stdlib.
- **Default mutation discipline**: Stage 2 changes the *frozen-dataclass field defaults* on the B010 and B013 strategy config types, plus any module-level constant that records the cadence (e.g. `DEFAULT_REBALANCE_FREQUENCY`). It does **not** restructure the override-config plumbing established in B018 (`dataclasses.replace`-based override remains the only mutation pathway during a sweep run). The B018 sweep harness must continue to function unchanged.
- **Downstream synchronization (Stage 2 only)**:
  - **B011 Master Portfolio**: the risk_parity sleeve config that wraps B010 must be updated so the master-portfolio sleeve still uses B010's new default; any B011 baseline test or fixture that hard-codes the prior `target_volatility` / `rebalance_frequency` is updated in lockstep with the strategy change.
  - **B014 stress baselines**: `docs/test-reports/B014-regime-adaptive-cross-strategy-comparison-2026-05-14.json` (and any sibling Markdown summary) records B010 / B013 numbers under the prior defaults. B019 does **not** rewrite the historical B014 sidecar (it is a frozen test report). Instead, B019 emits a new `docs/test-reports/B019-default-change-baseline-2026-MM-DD.{json,md}` capturing the new-default numbers on the same windows so future batches have a clean reference, and adds a one-line cross-link in `B014-regime-adaptive-stress-validation-spec.md` Background pointing at the B019 baseline.
  - **B015 activation-policy comparison**: the snapshot baseline at `docs/test-reports/B015-regime-adaptive-activation-policy-comparison-2026-05-15.json` was computed at the prior defaults. B019 does **not** rewrite this historical record; instead, F004 re-runs the comparison under new defaults and writes `docs/test-reports/B019-b015-activation-policy-rerun-2026-MM-DD.{json,md}`. The B015 spec gets a one-line cross-link.
  - **Unit tests**: any test in `tests/unit/` that hard-codes the prior default `target_volatility` or `rebalance_frequency` is updated in F003. A grep audit (`rg "target_volatility\s*[=:]\s*0\.0?8|rebalance_frequency\s*[=:]\s*['\"]monthly['\"]" trade tests`) is part of F003's checklist.
- **Backlog discipline**:
  - If gate met: F005 closes `BL-B018-S1` (mark resolved, point at signoff).
  - If gate not met: F005 closes `BL-B018-S1` (mark not actionable on this snapshot) and adds `BL-B019-S1` (record specifically what configurations were tested and which gate failed, so a future batch on a different snapshot or a different axis does not duplicate effort).
- **Real-data reverify (framework v0.9.21 #1)**: F005 must re-execute the winning configuration on the snapshot under the new defaults and confirm ending value / DD / turnover match F002's prediction within ±0.1 % (numerical determinism — same code path, same snapshot, same dates). Any drift > 0.1 % blocks signoff.
- **Research-only disclaimer**: all B019 reports carry the standard disclaimer; this batch does not authorize paper or live trading.

## Feature Requirements

### F001 — Sweep harness fine-grid extension + unit tests

Executor: `generator`.

Extend `trade/analysis/parameter_sweep.py`:

- Confirm `run_vol_target_sweep` already accepts an arbitrary `Sequence[float]` grid (per B018 F002). If yes, no signature change. If a B018 implementation choice forces grid validation against a hard-coded constant, relax it so any positive `vol_target` is accepted.
- Add a public helper `run_cadence_vs_default_sweep(records, strategy_name, cadences, vol_targets, windows, *, default_baseline=True) -> list[SweepRunResult]` that, for each `(cadence, vol_target)` pair plus the strategy's current default `(default_cadence, default_vol_target)` baseline, returns a deterministic result list. The default baseline is included as one extra cell so the gate evaluator can compute deltas against it without a separate run.
- Add a public helper `evaluate_retune_gate(results, strategy_name, gate=DEFAULT_GATE) -> RetuneGateVerdict` that, given the result list from `run_cadence_vs_default_sweep`, returns a typed verdict containing per-cell pass/fail flags for each of the four gate conditions and a top-level `gate_met: bool` plus `winning_cell: tuple[str, float] | None`. `DEFAULT_GATE` is a frozen dataclass holding `min_calm_uplift_pct=1.0`, `min_calm_gap_narrowing_pp=5.0`, `do_no_harm_on_stress=True`, `max_turnover_increase_pct=15.0`.
- Add `tests/unit/test_parameter_sweep_b019.py` with the following coverage (using deterministic synthetic fixtures already established in `tests/unit/test_parameter_sweep.py`):
  - `run_cadence_vs_default_sweep` returns `len(cadences) * len(vol_targets) + 1` cells (the `+1` is the default baseline).
  - The default baseline cell carries the strategy's actual default values, not a hard-coded constant.
  - `evaluate_retune_gate` correctly identifies a synthetic "all-pass" winning cell, a "fails gate 3" cell, a "fails gate 4" cell, and a "no cell qualifies" sweep.
  - Determinism: two consecutive runs return byte-identical `RetuneGateVerdict`.
  - No mutation of strategy defaults (assert defaults equal before / after).

`pytest` / `ruff check trade tests scripts` / `mypy trade` / `compileall -q trade tests scripts` all pass with `.venv/bin/python`.

### F002 — Stage 1: real-data fine sweep + Pareto report + gate verdict

Executor: `codex`.

Run `run_cadence_vs_default_sweep` for B010 and B013 on the B014 snapshot across the three windows. Run `evaluate_retune_gate` on the results. Emit:

- `docs/test-reports/B019-retune-sweep-2026-MM-DD.json`: full sweep matrix (60 cells + 2 default baselines), per-cell metrics (`ending_value`, `gap_vs_60_40`, `max_drawdown`, `turnover`, `transaction_costs`, `sharpe`), per-cell gate verdicts, and the top-level `gate_met` boolean per strategy with the winning cell (or null).
- `docs/test-reports/B019-retune-sweep-2026-MM-DD.md`: narrative report with sections:
  1. Background (link to B018 + BL-B018-S1 + framework v0.9.21 #1)
  2. Sweep matrix table (one per strategy)
  3. Per-cell gate verdict table
  4. Pareto recommendations (low-DD / balanced / high-return per strategy, with concrete trade-off numbers in B018's format)
  5. Top-level verdict: `gate_met=True/False` per strategy, winning cell (if any)
  6. Snapshot recap + research-only disclaimer

If the B014 manifest is absent in checkout, the report runs on the synthetic 9-asset fixture (B018's fallback path), tags `real_data_status='skipped'`, and writes verdict `gate_met=False` with reason `"manifest absent — fixture-only run does not satisfy framework v0.9.21 #1 real-data reverify requirement"`.

Update `progress.json.evaluator_feedback` with the verdict summary so Generator (Stage 2) reads it without re-parsing the JSON.

### F003 — Stage 2 (conditional): default mutation + unit-test updates

Executor: `generator`. **Skipped if F002 verdict is `gate_not_met` for both strategies.** If exactly one strategy's gate met, F003 modifies only that strategy's default and skips the other.

Per qualifying strategy:

- Modify the relevant `trade/strategies/*.py` config dataclass field defaults to the winning `(cadence, vol_target)` from F002.
- If the strategy module exposes a `DEFAULT_*` constant for `cadence` or `vol_target`, update it consistently.
- Run `rg "target_volatility\s*[=:]\s*0\.0?8|rebalance_frequency\s*[=:]\s*['\"]monthly['\"]" trade tests` and update every hit in `tests/unit/` so the prior default is no longer asserted as the baseline. Hits in `tests/unit/test_parameter_sweep.py` and `tests/unit/test_parameter_sweep_b019.py` are *not* updated if they explicitly construct a `vol_target=0.08` override (those are testing override behavior, not the default). Hits in `docs/specs/` / `docs/test-reports/` are *not* mutated (historical records).
- All previously-passing tests continue to pass; any new assertion in updated tests reflects the new default deterministically.

### F004 — Stage 2 (conditional): downstream baseline synchronization

Executor: `generator`. **Skipped if F003 was skipped.**

- Update B011 Master Portfolio sleeve config (if it hard-codes a `vol_target` or `cadence` for the risk_parity sleeve) so it consumes the new B010 default through the normal config-loading path. Update any B011 unit test or fixture that hard-codes the prior numbers.
- Add `docs/test-reports/B019-default-change-baseline-2026-MM-DD.{json,md}`: re-run B010 and B013 on the same three windows under the new defaults and record the numbers. This is the new reference baseline for future batches.
- Add `docs/test-reports/B019-b015-activation-policy-rerun-2026-MM-DD.{json,md}`: re-run B015's activation-policy comparison harness under the new B013 default and capture the updated comparison.
- Add a single one-line cross-link in `docs/specs/B014-regime-adaptive-stress-validation-spec.md` Background pointing at the B019 default-change baseline (do not rewrite the B014 sidecar).
- Add a single one-line cross-link in `docs/specs/B015-regime-adaptive-activation-policy-spec.md` Background pointing at the B019 activation-policy rerun.
- Strategy spec text: update `docs/strategy/02-risk-parity-vol-target.md` (and `docs/strategy/00-master-portfolio-allocation.md` if the master spec quotes the prior B010 default explicitly) so the documented defaults match the code.

### F005 — Stage 2 Codex regression verification + signoff

Executor: `codex`.

- Run full test suite with `.venv/bin/python -m pytest tests/ -q` (must be green).
- Run `.venv/bin/python -m mypy trade` and `.venv/bin/python -m ruff check trade tests scripts` (must be clean).
- Run `.venv/bin/python -m compileall -q trade tests scripts` (must be clean).
- If F003 / F004 ran (gate met): re-execute the winning configuration on the snapshot using the new defaults and assert each metric matches F002's prediction within ±0.1 % (numerical determinism check). Any drift > 0.1 % blocks signoff and re-opens F003 / F004 as `fixing`.
- If F003 / F004 were skipped (gate not met): no determinism check needed.
- Backlog handling:
  - Mark `BL-B018-S1` resolved in `backlog.json` (link to B019 signoff).
  - If gate not met, add `BL-B019-S1` describing exactly which `(cadence, vol_target)` cells were evaluated and which gate condition failed, so future batches on a different snapshot do not blindly re-run the same search.
- Write `docs/test-reports/B019-retune-signoff-2026-MM-DD.md` using `framework/templates/signoff-report.md`. The signoff records:
  - Scope (Stage 1 always, Stage 2 conditionally)
  - Verification commands and their results
  - High-level findings (winning cell per strategy, or "gate not met")
  - Backlog updates
  - Disclaimer
- Update `progress.json`: `status → done`, `docs.signoff` set, `evaluator_feedback` summarizes both stages.

## Out Of Scope

- Re-tuning any axis other than `cadence` and `vol_target` (universe, weighting method, L1 / L3 layer parameters all stay at current defaults).
- Touching B016 HRP code path (B017 already established HRP is not the gap source on real data; B019 does not re-evaluate weighting).
- Changing B011 Master Portfolio sleeve weights (only the risk_parity sleeve's parameters are passed-through from B010's new defaults; the 70 / 20 / 10 sleeve allocation is untouched).
- Adding new satellite strategies (BL-B011-S2 remains a separate future batch).
- Smoothed vol targeting / VIX overlay (BL-B013-D1 / D2 remain separate future batches).
- Changing the snapshot — B019 uses the same `regime-adaptive:b69883b08eedea7d` snapshot established by B017 / B018 so cross-batch comparability is preserved.
- Live / paper / broker / secret integrations — all hard guards remain in place.
- Spec or code changes to historical test reports (`B014` / `B015` / `B016` / `B017` / `B018` JSON sidecars are immutable historical records; B019 cross-links forward, never overwrites backward).

## Acceptance

Batch is **done** when:

1. F001 PASS: `parameter_sweep.py` extension + unit tests merged on `main`; `pytest` / `ruff` / `mypy` / `compileall` clean.
2. F002 PASS: `B019-retune-sweep-2026-MM-DD.{json,md}` written with explicit per-cell gate verdicts and top-level `gate_met` per strategy; `progress.json.evaluator_feedback` updated.
3. F003 + F004 either PASS (Stage 2 executed because gate met for at least one strategy) or correctly marked `skipped` with reason recorded in features.json status comment.
4. F005 PASS: signoff written per `framework/templates/signoff-report.md`; `BL-B018-S1` resolved; if applicable `BL-B019-S1` added; `progress.json.status = done`.
5. All real-data reverify checks (F005 numerical determinism vs F002 prediction) pass within ±0.1 % when Stage 2 ran.
6. No mutation of `B014` / `B015` / `B016` / `B017` / `B018` historical reports.
7. Research-only disclaimer present on every B019 artifact.

_Disclaimer: research-only; never authorizes paper or live trading._
