# B016 Risk Parity HRP Upgrade Spec

## Background

B010 implemented the Risk Parity / Volatility Target backtest MVP using plain inverse-volatility weighting: per-asset weight is inversely proportional to annualized volatility, then normalized and scaled to a target portfolio volatility. This algorithm is signal-blind and well-tested, but ignores cross-asset correlation. Two practical consequences:

1. Highly correlated assets (e.g., SPY + VEA + VWO equity ETFs) all get individual inverse-vol weights without "correlation discount", which concentrates risk despite the inverse-vol facade.
2. Tail-correlated assets (e.g., bonds + equities in 2022) become a single cluster, so naive inverse-vol over-weights them as if they were independent.

Hierarchical Risk Parity (HRP, De Prado 2016) addresses this by:

1. Building a correlation-based distance matrix.
2. Single-linkage hierarchical clustering on that matrix.
3. Quasi-diagonalization (reorder assets to push correlated assets adjacent).
4. Recursive bisection: at each tree split, allocate capital between the two child clusters inversely proportional to cluster variance, recursing until each leaf is a single asset.

The B013 research material analysis (planner session pre-B013) referenced multiple 2026 arxiv papers (`Beyond De Prado and Cotton`, `Hierarchical Minimum Variance Portfolios`, `Topological Risk Parity`) endorsing HRP and its variants over plain inverse-vol on Sharpe, drawdown, and stability metrics. Additionally, B014's cross-strategy comparison revealed that plain inverse-vol B010 underperformed static 60/40 by ~25pp cumulative return in 2020-06..2022-12. HRP's correlation awareness may close some of that gap because it can size cross-asset class allocations more like a 60/40 split (lower equity beta when bonds-and-equity are uncorrelated, higher when correlated).

B016 adds HRP as a **selectable weighting policy** on B010 risk parity. Default remains `inverse_volatility` (backwards-compat with B010 signoff). The HRP implementation is pure-stdlib (no scipy/numpy/pandas) to match the existing `trade/` zero-third-party-deps design.

## Goal

Implement a minimal, testable HRP upgrade for B010 risk parity that:

- Adds a `weighting_method` policy switch to `RiskParityParameters` accepting `"inverse_volatility"` (current behavior, default) and `"hrp"` (new). Validation rejects other values.
- Implements plain HRP (De Prado 2016) as a pure-stdlib algorithm: correlation matrix → distance matrix `sqrt(0.5 * (1 - corr))` → single-linkage hierarchical clustering → quasi-diagonalization → recursive bisection. Lives in a new `trade/strategies/risk_parity_hrp.py` module so it can be unit-tested independently.
- Wires HRP into B010's monthly backtest workflow: when `weighting_method == "hrp"`, compute weights via HRP; otherwise unchanged inverse-vol path. L2 target-vol scaling, defensive sleeve routing, and exposure cap (≤1.0) apply identically regardless of weighting method.
- Adds a comparative backtest harness that, on the B014 yfinance snapshot (if present), runs B010 with both weighting policies on the B013 9-asset universe, and computes the same metrics + comparison vs static 60/40 baseline. If the snapshot is absent, the harness runs on synthetic fixture only and the real-data section is `skipped`.
- Preserves B010 signoff behavior bit-for-bit when `weighting_method == "inverse_volatility"` (default).
- B011 Master Portfolio's `risk_parity` sleeve continues to use the default (inverse-vol) and its existing tests pass without modification.
- Adds safety-guard regression proving B016 introduces no new third-party imports (specifically not scipy, numpy, pandas, sklearn, etc.) and no environment access.
- Closes with independent Codex L1 verification.

This batch is a B010 parameter expansion + algorithm addition. It does not introduce a new strategy, broker adapter, paper-trading API, or new universe.

## Hard Decisions

- Add `weighting_method: Literal["inverse_volatility", "hrp"]` to `RiskParityParameters`. Existing field already named `weighting_method` is currently a free `str` defaulted to `"inverse_volatility"`; tighten to `Literal` with validation. Other values raise `ValueError` with diagnostic listing valid choices.
- Default value: `weighting_method = "inverse_volatility"`. Backwards-compat hard requirement: existing B010 callers and the B011 master portfolio `risk_parity` sleeve registration produce identical outputs to B010 signoff on the synthetic fixture.
- HRP implementation lives in a new module `trade/strategies/risk_parity_hrp.py`. Top-level public entry: `compute_hrp_weights(returns: Sequence[Sequence[float]], symbols: Sequence[str]) -> dict[str, float]`. Inputs are daily return series per asset (already aligned, no missing); outputs are normalized weights summing to ≈1.0.
- HRP is pure-stdlib: `math`, `statistics`, plus standard typing. **No new third-party dependency**. No scipy, numpy, pandas, sklearn, networkx. The implementation is small (~200 lines) and reviewable.
- Distance metric: `d_ij = sqrt(0.5 * (1 - corr_ij))` (De Prado canonical).
- Clustering algorithm: single linkage. Implemented from scratch in pure Python (~50 lines). Tested directly against canned reference outputs.
- Quasi-diagonalization: standard recursive tree traversal.
- Recursive bisection: at each split, allocate `alpha_1 = 1 - V_1 / (V_1 + V_2)` to left cluster, `alpha_2 = 1 - alpha_1` to right cluster. Within-cluster variance estimated as inverse-variance weighted sum.
- Edge cases:
  - Universe size n = 1: trivially weight = 1.0.
  - Universe size n = 2: inverse-variance weights (no clustering needed; both methods agree).
  - All-zero variance for an asset (degenerate): fail closed (`ValueError`); same as B010's existing behavior on zero-vol assets.
  - Single perfect-correlation pair: HRP still emits valid weights (single linkage on `d_ij = 0` collapses pair early).
- HRP runs **before** L2 target-vol scaling. The exposure scaling caps and defensive routing remain identical: portfolio-vol scaling capped at 1.0, residual exposure to defensive sleeve.
- Comparative backtest harness lives at `trade/strategies/risk_parity_hrp_comparison.py` (or equivalent under risk_parity-related namespace). Reuses B014 yfinance snapshot loader; when manifest absent, `real_data_status = "skipped"` and synthetic fixture is used.
- B010 unit tests for inverse-vol path are unchanged. New HRP unit tests live in `tests/unit/test_risk_parity_hrp.py` and cover the algorithm's pieces (correlation matrix, distance matrix, clustering, quasi-diagonalization, recursive bisection, end-to-end).
- B011 Master Portfolio `risk_parity` sleeve registration is unchanged (default `inverse_volatility`). No B011 tests are modified.
- B013 / B015 strategy code remain untouched. B013's L2 reuse of B010 inverse-vol path is unchanged because L2 in B013 explicitly invokes the inverse-vol math (not the new HRP path). B016 does not change the B013 L2 contract.
- All artifacts research-only. Reports, logs, docstrings carry the research-only disclaimer. Tests assert absence of `paper-execution`, `live-execution`, `executed-order`, `filled`, `place_order`, `submit_order` phrasing in B016 outputs.
- Default CI continues to use synthetic fixtures and remains fixture/mock-first. The real-snapshot comparative backtest is exercised by a research-mode test that is skipped if the manifest is absent.
- No broker, paper/live trading, real account data, secrets in strategy modules, AI execution, cloud deployment, or frontend dashboard. No env reads. No socket I/O during fixture runs.

## Reference Documents

- `docs/specs/B010-risk-parity-backtest-mvp-spec.md`
- `docs/specs/B013-regime-adaptive-multi-asset-mvp-spec.md`
- `docs/specs/B014-regime-adaptive-stress-validation-spec.md`
- `docs/specs/B015-regime-adaptive-activation-policy-spec.md`
- `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`
- `docs/test-reports/B014-regime-adaptive-stress-validation-signoff-2026-05-14.md`
- `docs/test-reports/B014-regime-adaptive-cross-strategy-comparison-2026-05-14.md`
- `docs/research_materials/arxiv_strategies.json` (HRP variant papers)
- `docs/strategy/00-master-portfolio-allocation.md`
- `docs/strategy/02-risk-parity-vol-target.md`
- `docs/prd/mvp-prd.md`
- `docs/engineering/testing-and-fixture-policy.md`
- `docs/engineering/no-live-safety-guards.md`
- `docs/engineering/backtest-report-schema.md`

External (informational, no implementation dependency):

- De Prado, M. L. (2016). "Building Diversified Portfolios that Outperform Out-of-Sample." Journal of Portfolio Management. — canonical HRP reference.
- arxiv 2026 follow-up papers tracked in `docs/research_materials/arxiv_strategies.json`.

## Proposed Implementation Shape

### Configuration Tightening

`trade/strategies/risk_parity.py`:

- Tighten `weighting_method` from free `str` to `Literal["inverse_volatility", "hrp"]` and add validation in `__post_init__` (or equivalent) that raises `ValueError` for other strings with diagnostic listing valid choices.
- `parameter_hash` already includes `weighting_method` since it is a field; verify two configs differing only on this field produce different hashes.

### HRP Algorithm Module

`trade/strategies/risk_parity_hrp.py` (new):

```python
# Pure-stdlib HRP per De Prado (2016). Research-only.

def compute_correlation_matrix(returns: Sequence[Sequence[float]]) -> list[list[float]]: ...
def compute_distance_matrix(corr: Sequence[Sequence[float]]) -> list[list[float]]: ...
def single_linkage_clustering(dist: Sequence[Sequence[float]]) -> ClusterNode: ...
def quasi_diagonalize(root: ClusterNode) -> list[int]: ...
def recursive_bisection(
    order: Sequence[int],
    variances: Sequence[float],
    correlations: Sequence[Sequence[float]],
) -> list[float]: ...
def compute_hrp_weights(
    returns: Sequence[Sequence[float]],
    symbols: Sequence[str],
) -> dict[str, float]: ...
```

Where `ClusterNode` is a dataclass tree (`left: ClusterNode | None`, `right: ClusterNode | None`, `leaf_index: int | None`).

Edge cases handled:

- n=1: returns `{symbols[0]: 1.0}`.
- n=2: inverse-variance weights, no clustering needed.
- Zero variance on any asset: `ValueError` (matches B010 existing).
- Missing / NaN values: caller responsibility; HRP module assumes pre-cleaned input.

### B010 Workflow Integration

`trade/strategies/risk_parity.py` (or wherever the backtest loop lives, currently `trade/backtest/...`):

- At weighting step: if `parameters.weighting_method == "hrp"`, call `compute_hrp_weights(returns, symbols)`; else preserve the existing inverse-vol code path.
- L2 target-vol scaling, defensive routing, exposure cap (≤1.0) apply uniformly to whichever weights came back.
- Per-period rebalance trace records `weighting_method: str` so reports can show which path was active.

### Comparative Backtest Harness

`trade/strategies/risk_parity_hrp_comparison.py` (new) + `scripts/generate_b016_hrp_comparison_report.py` (new):

- Loads B014 manifest if present; falls back to synthetic fixture.
- On the B013 9-asset universe and B014 snapshot's overlapping window, runs:
  - B010 with `weighting_method = "inverse_volatility"` (current behavior).
  - B010 with `weighting_method = "hrp"` (new).
- For each, records: annualized return, annualized volatility, Sharpe, max DD, turnover, per-asset weight history.
- Reuses B014's sidecar for `static_60_40` baseline if available (no recompute).
- Emits `docs/test-reports/B016-risk-parity-hrp-comparison-2026-MM-DD.md` + JSON sidecar. Includes narrative on whether HRP closes any of the inverse-vol vs 60/40 gap.
- Real-data branch reports `skipped` when manifest absent (per established pattern from B015).

### Reports

Comparative report content:

- Per-method metrics table: inverse-vol B010, HRP B010, static 60/40.
- Equity curve overlay (if practical) or terminal value table.
- Per-asset weight history dump for both methods (truncated for readability; full data in JSON sidecar).
- 2020 + 2022 stress sub-window max DD per method.
- Narrative: does HRP shrink the absolute-return gap vs 60/40 in 2020-06..2022-12? Empirical research finding, not pass/fail.
- Research-only disclaimer; no paper/live execution phrasing.

### Safety And Regression

- `weighting_method == "inverse_volatility"` (default) must produce bit-for-bit identical outputs to B010 signoff on the synthetic fixture: full B010 test suite + B011 master portfolio test suite pass unchanged.
- New HRP module imports only `math`, `statistics`, `dataclasses`, `typing`, `collections.abc`. No scipy, numpy, pandas, sklearn, networkx. New comparison module imports only stdlib + `trade.*` modules.
- No `os.environ` / `os.getenv` reads in any strategy module.
- No socket I/O during fixture-based runs.
- Reports / logs / docstrings include the research-only disclaimer.
- B013 / B015 tests continue to pass without modification.
- Required local checks must pass: pytest, ruff, compileall, mypy.

## Feature Requirements

### F001 Tighten `weighting_method` And Validate

Executor: generator.

Tighten `RiskParityParameters.weighting_method` from free `str` to `Literal["inverse_volatility", "hrp"]`. Default remains `"inverse_volatility"`. Validation rejects any other string with `ValueError` and diagnostic listing valid choices. Verify `parameter_hash()` produces distinct hashes for the two valid values when all else equal. Tests cover default construction, both valid values, invalid string rejection, hash distinctness.

### F002 HRP Algorithm Module And Unit Tests

Executor: generator.

Add `trade/strategies/risk_parity_hrp.py` implementing De Prado (2016) HRP in pure stdlib: correlation matrix, distance matrix `sqrt(0.5 * (1 - corr))`, single-linkage hierarchical clustering, quasi-diagonalization, recursive bisection, and `compute_hrp_weights` top-level entry. **No scipy / numpy / pandas import**. Add `tests/unit/test_risk_parity_hrp.py` covering: correlation matrix on canned series; distance matrix correctness; single linkage on small reference cases; quasi-diagonalization order; recursive bisection split formula; end-to-end on n=1, n=2, n=3, n=5, n=9 universes; zero-variance asset rejection (`ValueError`); deterministic output across runs.

### F003 B010 Workflow Integration

Executor: generator.

Wire HRP into the existing B010 monthly backtest. When `parameters.weighting_method == "hrp"`, the weighting step calls `compute_hrp_weights`; otherwise the existing inverse-vol path is unchanged. L2 target-vol scaling, defensive sleeve routing, and exposure cap apply identically. Per-period rebalance trace records `weighting_method` so downstream reports can attribute. Tests cover: HRP path runs end-to-end on a 9-asset synthetic fixture; inverse-vol path remains bit-for-bit identical to prior; trace records the active method.

### F004 Comparative Backtest Harness And Report

Executor: generator.

Add `trade/strategies/risk_parity_hrp_comparison.py` (harness) and `scripts/generate_b016_hrp_comparison_report.py` (CLI). On the B013 9-asset universe, run B010 with both weighting policies over B014 snapshot's overlapping window (when manifest present) or synthetic fixture (when absent). Emit `docs/test-reports/B016-risk-parity-hrp-comparison-2026-MM-DD.md` + JSON sidecar containing: per-method metrics, 2020 + 2022 stress sub-window max DD, per-asset weight history summary, narrative on inverse-vol vs HRP vs 60/40 absolute-return gap, real-data status (`run` / `skipped`). Reports include research-only disclaimer. Tests cover schema correctness, real-data `skipped` semantics, and `run` semantics (using a fixture manifest stub).

### F005 Backwards-Compat And Safety Regression

Executor: generator.

Prove that `weighting_method = "inverse_volatility"` (default) reproduces B010 signoff behavior bit-for-bit on the synthetic fixture: full pre-existing B010 + B011 + B013 + B015 test suites pass without modification. Add B016-specific regression tests confirming: no new third-party imports in `trade/strategies/risk_parity_hrp.py` or harness (specifically not scipy, numpy, pandas, sklearn, networkx); no broker / AI / LLM SDK imports; no `os.environ` reads in any new strategy module; no socket I/O on fixture runs; no paper / live execution phrasing in B016 outputs. Required local checks must pass: pytest, ruff, compileall, mypy.

### F006 Independent Evaluation

Executor: codex.

Evaluator runs local/CI-safe L1 verification. Must confirm: (1) `weighting_method` Literal + validation works; (2) HRP algorithm produces correct weights on canned reference cases; (3) `inverse_volatility` default reproduces B010 signoff bit-for-bit on synthetic fixture; (4) comparative report exists with both methods + 60/40 baseline + 2020/2022 stress sub-windows + narrative; (5) if B014 snapshot present, HRP empirical numbers are consistent with the report's narrative; if absent, real-data section is `skipped` correctly; (6) no scipy/numpy/pandas/sklearn imports in B016 strategy modules; (7) all no-live / no-secret / no-network-by-default / no-broker / no-paper / no-AI safety guards remain intact. Produce review and signoff under `docs/test-reports/`. Signoff explicitly notes: backwards-compat verification result, HRP empirical performance vs inverse-vol on real snapshot (if available), and whether HRP shrinks the absolute-return gap vs 60/40 (empirical research finding, not pass/fail).

## Acceptance Summary

B016 is complete only when:

- Required local checks pass: pytest, ruff, compileall, mypy.
- `RiskParityParameters.weighting_method` is `Literal["inverse_volatility", "hrp"]` with validation; default `"inverse_volatility"`; `parameter_hash` distinguishes the two values.
- `trade/strategies/risk_parity_hrp.py` implements De Prado HRP in pure stdlib (no scipy/numpy/pandas/sklearn imports) with full unit test coverage.
- B010 monthly backtest dispatches between inverse-vol (default) and HRP based on the policy; L2 target-vol scaling and defensive routing apply uniformly; per-period trace records active method.
- Default `weighting_method = "inverse_volatility"` reproduces B010 signoff behavior bit-for-bit on the synthetic fixture; pre-existing B010 + B011 + B013 + B015 test suites pass without modification.
- Comparative report at `docs/test-reports/B016-risk-parity-hrp-comparison-2026-MM-DD.md` exists with inverse-vol B010 row + HRP B010 row + static 60/40 row + 2020/2022 stress sub-window max DD per method + narrative on the absolute-return gap.
- Real-data branch reports `run` when B014 manifest present, `skipped` when absent (no failure).
- No new forbidden imports (scipy/numpy/pandas/sklearn/broker/AI/LLM); no env reads; no socket I/O on fixture runs; no paper/live execution phrasing in B016 outputs.
- Evaluator signs off F006 with explicit notes on backwards-compat and HRP-vs-inverse-vol-vs-60/40 empirical comparison.
