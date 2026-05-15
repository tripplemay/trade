# Gap Attribution Methodology

## Purpose

When a strategy underperforms a benchmark by a material absolute-return gap, and one or more "intuitive fix" hypotheses (re-gate the trend signal, change the weighting method, re-tune a single knob) have been **empirically falsified** by previous batches, the next research move is **systematic root-cause attribution**, not another single-variant re-tune.

## When to use

This methodology applies when **all** of the following are true:

1. The performance gap is real on the project's standard real-data snapshot (not just a fixture artifact — see `testing-and-fixture-policy.md` §Fixture vs Real-Data Signal Reversal).
2. At least one prior batch has tested a directional hypothesis ("doing X will shrink the gap") and the result was **no improvement or worse**.
3. The next instinct is to try yet another single hypothesis (a different weighting method, a different gate). **Stop and attribute first.**

## Reference incident — B017 → B018 (2026-05-15)

| Batch | Hypothesis | Real-data result |
|---|---|---|
| B015 | Gating B013 by regime activation policy will shrink the B013 vs 60/40 gap | All 3 policies — `none / only_non_normal / production` — failed; `only_non_normal` was strictly worse |
| B016 | HRP weighting will shrink the B010 vs 60/40 gap | HRP `-$496` ending value, turnover `+41%` (worse) |

After two falsified hypotheses, B018 ran systematic attribution and found the dominant drag was **`l2_vol_scaling`** (with `l1_gating` as secondary), and the **actionable axes** were `vol_target` and `cadence` — not the weighting method, not the gating policy, not the universe.

## The four-step protocol

### Step 1 — Per-asset attribution

Decompose the strategy's realized return on the same windows the gap is measured on, into per-asset signed dollar contributions:

```
contribution(asset) = Σ_t (capital_t × weight_{asset,t} × return_{asset,t})
```

Compare against the benchmark's per-asset contribution. Assets whose contribution sign or magnitude differs most from the benchmark are the *symptomatic carriers* of the gap. They are not the *cause* — they are where the cause manifests.

### Step 2 — Per-layer attribution

Decompose the strategy's loss vs a "no-overlay" baseline (typically the same universe held at strategy-implied risk weights without any overlay) into the contribution of each strategy layer:

```
layer_drag(layer) = Σ_t (capital_t × parked_fraction_{layer,t}
                          × (defensive_return_t − avg_risk_return_t))
```

For B018 the layers were `l1_gating`, `l2_vol_scaling`, `l3_crisis_cut`, and `defensive_routing` (B013 has all four; B010 has the latter two only). The layer with the largest cumulative drag is the *root cause candidate*.

### Step 3 — Three-axis sensitivity sweep

For each strategy under attribution, sweep across three independent axes:

| Axis | B018 grid |
|---|---|
| Risk-target knob (e.g. `vol_target`) | `{0.05, 0.08, 0.10, 0.12, 0.15}` |
| Universe ablation | `{full, drop_SGOV, drop_stabilizers, SPY+IEF, SPY only}` |
| Rebalance cadence | `{monthly, quarterly, semiannual, annual}` |

Each cell is a backtest run on the same calm window plus at least two stress sub-windows. Records `ending_value / gap_vs_benchmark / max_drawdown / turnover / transaction_costs / sharpe`. The dimension where the best cell beats the worst cell by the largest margin is the *most actionable axis*. The dimension where everything clusters tightly (e.g. universe ablation in B018, mostly because defensive-asset invariants constrain the variants) is *constrained* and should not be the focus of follow-up retunes.

### Step 4 — Pareto recommendation set

Emit at least three configuration candidates: one **low-DD** (minimize stress-window max drawdown), one **balanced** (best trade-off between gap-shrink and DD), one **high-return** (maximize ending value, accept higher DD). Each recommendation must include concrete trade-off numbers ("config X: gap shrinks by Y%, 2022 max DD goes from -A% to -B%").

The output is a research-only diagnostic. **The attribution batch itself does not modify any default strategy parameter.** Any retune that the recommendations suggest is a *follow-up batch candidate* logged to `backlog.json`, not a B018-style spec change.

## Hard boundaries (non-negotiable)

- The attribution module is pure-stdlib (no scipy / numpy / pandas / sklearn). It runs anywhere `trade/` runs.
- Override configs are constructed inline (e.g. `dataclasses.replace`); **strategy default parameters are never mutated** by the attribution / sweep harness.
- Manifest-absent fallback: when the real-data snapshot is missing, the harness runs on a synthetic fixture and tags `real_data_status='skipped'` so downstream readers do not over-trust the result.
- Output reports carry the standard research-only disclaimer; attribution evidence does not authorize paper or live trading.

## Reference implementation

- Code: `trade/analysis/pnl_attribution.py` + `trade/analysis/parameter_sweep.py`
- Tests: `tests/unit/test_pnl_attribution.py` + `tests/unit/test_parameter_sweep.py`
- Real-data report: `docs/test-reports/B018-gap-attribution-2026-05-15.md` + JSON sidecar
- Signoff: `docs/test-reports/B018-gap-attribution-signoff-2026-05-15.md`
