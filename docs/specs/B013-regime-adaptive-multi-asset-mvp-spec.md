# B013 Regime-Adaptive Multi-Asset Strategy MVP Spec

## Background

B006-B012 delivered the core MVP path: Global ETF Momentum, Risk Parity, Master Portfolio Allocation with 15% drawdown kill-switch, and Paper Trading prep with target positions schema + abstract broker adapter. MVP PRD §4.5 prep items and §10/§11 success criteria are now substantively met.

The user added a research document (`docs/specs/research/B011-regime-adaptive-multi-asset-spec.md`) and three external research material collections (arxiv, GitHub, Elsevier/SSRN) proposing a Regime-Adaptive Multi-Asset Strategy that stacks three defensive shields on top of inverse-volatility weighting, with tolerance-band rebalancing and stress validation against real crisis windows.

The proposal is well-aligned with the literature: AEGIS (arxiv 2026, 20-year walk-forward through 2008 GFC) demonstrates momentum-gated hierarchical optimization, multiple Elsevier papers cover optimal trend-following under regime-switching models, "Smoothing volatility targeting" (arxiv 2022) and "Single-Asset Adaptive Leveraged Volatility Control" (arxiv 2026) underwrite vol-target stability, and the transaction-cost literature (7+ Elsevier papers) supports tolerance-band rebalancing.

B013 implements this as an independent new strategy module that runs in parallel with B006 momentum and B010 risk parity. It can be plugged into B011 Master Portfolio as an implementable sleeve. The batch continues to enforce fixture/mock-first, snapshot-based, research-only, no-live/no-broker/no-paper/no-AI safety boundaries.

## Goal

Implement a minimal, testable Regime-Adaptive Multi-Asset Strategy MVP that:

- Defines a new multi-asset universe (Risk Core: SPY/QQQ/VEA/VWO; Stabilizers: IEF/TLT/GLD/DBC; Defensive: SGOV) with structured asset class metadata.
- Acquires a real historical public data snapshot covering 2018-2025 daily OHLCV via the B009 snapshot infrastructure, so 2020 (liquidity crisis) and 2022 (inflation / stock-bond drawdown) stress windows can be validated.
- Implements L1 (per-asset 200-day SMA gating), L2 (inverse-volatility weighting with 8% portfolio vol target — reusing B010 modules), and L3 (regime detection from Fast/Slow vol ratio plus SPY trend) as composable defensive shields.
- Implements 3% tolerance-band rebalancing that suppresses small trades and reduces turnover, with explicit regime-override rules so crisis transitions are not delayed.
- Provides a calculated baselines comparison (static 60/40 multi-asset, B006 momentum, B010 risk parity) and an explicit 2020/2022 stress drawdown validation acceptance gate.
- Adds a lightweight parameter sensitivity sweep so the literature-default parameters can be verified rather than blindly adopted.
- Plugs into B011 Master Portfolio as a new implementable sleeve (`regime_adaptive`) with `planning_weight = 0.0` by default, preserving backwards compatibility with existing B011 signoffs and allowing the user to manually rebalance weights post-hoc.
- Adds safety-guard regression coverage proving B013 introduces no new network-by-default, secret, broker, paper/live, AI-trading, generated-data-commit, or frontend dependency.
- Closes with independent Codex L1 verification.

This batch creates a third research-grade backtest path, not a broker, paper trading, live execution, optimizer platform, or trading recommendation product.

## Hard Decisions

- B013 is an **independent new strategy module** (Option A): lives at `trade/strategies/regime_adaptive/` and is registered alongside B006 momentum and B010 risk parity. It does not mutate B010 risk parity code or contracts.
- New universe is exactly: Risk Core `SPY, QQQ, VEA, VWO`; Stabilizers `IEF, TLT, GLD, DBC`; Defensive `SGOV`. Universe configuration must classify each asset by category so L1 and L3 can apply category-specific logic where relevant.
- Real historical public data snapshot via B009 infrastructure: covers 2018-01-01 through 2025-12-31 inclusive (8-year span captures pre-2020, 2020 crash, 2022 inflation, recovery), 9 assets, daily OHLCV plus adjusted close. Snapshot is acquired once and committed as a B009-style manifest reference plus a gitignored cache directory. Default CI continues to use the existing fixture; the real snapshot is exercised by explicit research-mode tests and the stress validation gate.
- Default parameters (literature-aligned, configurable):
  - L1 trend window: 200 trading days SMA
  - L2 volatility lookback: 20 / 60 / 120 trading days (reusing B010 lookback set; default 120)
  - L2 portfolio volatility target: 8% annualized
  - L3 fast vol window: 20 trading days; slow vol window: 120 trading days; crisis ratio threshold: 1.5
  - L3 SPY trend window: 200 trading days SMA
  - L3 crisis exposure cut: 50%
  - L3 bear exposure (SPY < 200-SMA but no crisis): individual asset L1 gating only
  - Tolerance band: 3% absolute weight deviation
  - Account-level drawdown kill-switch threshold: 15% (inherits B011 semantics)
- Parameter sensitivity sweep is a deliberate feature (F008): runs a small deterministic grid over each major parameter (one-at-a-time ±1 step), produces a JSON/Markdown sensitivity report, and surfaces parameter robustness. Not a Monte Carlo, not a learned optimizer.
- Tolerance-band rebalancing rule: at each monthly rebalance signal date, compare current effective weight to target weight per asset; only emit a trade when `|current - target| > 3%`. **Regime override**: when an L3 regime transition occurs (NORMAL → BEAR / NORMAL → CRISIS / CRISIS → NORMAL / etc.), the tolerance band is bypassed and a full rebalance is issued.
- Master Portfolio integration: B011 master configuration grows a new sleeve `regime_adaptive` with `planning_weight = 0.0` and `type = implemented_strategy`. Existing B011 signoff invariants (planning weights sum to 1.0; satellite stubs absorb residual to defensive) are preserved because `regime_adaptive` weight stays at 0.0 by default. Users may set non-zero weight in a future planning step.
- All artifacts remain research-only. Reports, journals, and any docstring must contain "research-only, not a trading instruction" or equivalent. Tests verify the absence of `paper-execution`, `live-execution`, `executed-order`, `filled`, `place_order`, `submit_order`, and similar phrasing in B013 modules and outputs.
- Default CI and L1 tests remain fixture/mock-first and offline.
- Public data acquisition is a one-time research operation. The acquisition script must be opt-in (explicit CLI flag or environment trigger), never auto-invoked by the default test path, never reach out to networks during normal CI runs.
- Pseudocode bug noted in research source (`shielded["SGOV"] = 1.0 - sum(shielded.values() if v else 0 for v in shielded.values())`) must be reimplemented correctly as `1.0 - sum(shielded.values())` semantics (defensive sleeve absorbs residual after L1+L3 weight reductions).
- No leverage. Combined target exposure across all sleeves must remain `<= 1.0`. Residual exposure routes to `SGOV` defensive sleeve.
- No new external SDK or paid data dependency. The public data snapshot uses the same public-best-effort data source pattern as B009; failed fetches must fail closed.
- No broker, paper/live trading, real account data, secrets (in B013 code), AI execution, cloud deployment, or frontend dashboard.

## Reference Documents

### Internal

- `docs/prd/mvp-prd.md`
- `docs/strategy/00-master-portfolio-allocation.md`
- `docs/strategy/02-risk-parity-vol-target.md`
- `docs/specs/research/B011-regime-adaptive-multi-asset-spec.md`
- `docs/specs/B009-public-data-snapshot-mvp-spec.md`
- `docs/specs/B010-risk-parity-backtest-mvp-spec.md`
- `docs/specs/B011-portfolio-allocation-risk-mvp-spec.md`
- `docs/specs/B012-paper-trading-prep-mvp-spec.md`
- `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`
- `docs/test-reports/B012-paper-trading-prep-mvp-signoff-2026-05-14.md`
- `docs/engineering/testing-and-fixture-policy.md`
- `docs/engineering/config-and-environment-policy.md`
- `docs/engineering/no-live-safety-guards.md`
- `docs/engineering/backtest-report-schema.md`
- `docs/engineering/pit-data-degradation-policy.md`

### External (research material)

- `docs/research_materials/arxiv_strategies.json`
- `docs/research_materials/github_strategies.json`
- `docs/research_materials/institutional_strategies.json`

Specifically informing design choices:

- AEGIS (arxiv: "Taming the Black Swan: A Momentum-Gated Hierarchical Optimisation Framework for Asymmetric Alpha Generation") — momentum-gated portfolio construction validated over 2006-2025 including GFC.
- "Smoothing volatility targeting" (arxiv 2022) and "Single-Asset Adaptive Leveraged Volatility Control" (arxiv 2026) — vol-target stability via feedback / smoothing.
- "Optimal Trend Following Rules in Two-State Regime-Switching Models", "Rethinking Trend Following: Optimal Regime-Dependent Allocation" (Elsevier/SSRN) — regime-switching trend-following.
- Multiple Elsevier transaction-cost portfolio papers — tolerance-band rebalancing rationale.

## Proposed Implementation Shape

### Universe And Strategy Configuration

A `RegimeAdaptiveConfig` dataclass with:

- `universe`: `Sequence[AssetEntry]` where each `AssetEntry` carries `symbol`, `category: Literal["risk_core", "stabilizer", "defensive"]`, optional metadata.
- Default universe (in order): `SPY (risk_core)`, `QQQ (risk_core)`, `VEA (risk_core)`, `VWO (risk_core)`, `IEF (stabilizer)`, `TLT (stabilizer)`, `GLD (stabilizer)`, `DBC (stabilizer)`, `SGOV (defensive)`.
- `trend_window_days = 200`
- `vol_lookback_days = 120` (B010 default; 60 and 252 remain selectable)
- `target_volatility = 0.08`
- `regime_fast_vol_window_days = 20`
- `regime_slow_vol_window_days = 120`
- `regime_crisis_ratio = 1.5`
- `regime_spy_symbol = "SPY"`
- `regime_crisis_exposure_scale = 0.5`
- `tolerance_band = 0.03`
- `account_drawdown_threshold = 0.15` (mirrors B011 semantics)
- `max_exposure = 1.0` (no leverage)
- `defensive_symbol = "SGOV"`

Validation: weights non-negative, no leverage, at least one risk_core asset, at least one defensive symbol present, trend/vol windows positive, regime ratio > 1.0, tolerance in `[0, 1]`.

### Historical Public Data Snapshot (Research Path)

Reuse B009 manual public data import + local snapshot workflow:

- Acquisition script (opt-in): downloads daily OHLCV + adjusted close for the 9-symbol universe from 2018-01-01 through 2025-12-31 via the existing B009 public-best-effort data source. Network access only when the user runs the script with an explicit flag.
- Output is written under the gitignored `data/public-cache/` directory plus a committed manifest file `data/public-cache/regime-adaptive-prices-manifest.json` capturing snapshot id, sha256 of price files, date range, asset list, and "public-best-effort, non-PIT, research-only" limitations.
- Default CI loads no real snapshot; it uses synthetic fixtures crafted to exercise normal / bear / crisis regime transitions.
- A dedicated research-mode test (`test_regime_adaptive_stress_2020_2022.py`) loads the real snapshot through `load_snapshot_prices()` and validates the strategy against 2020-Q1 and 2022 windows. This test is skipped if the snapshot manifest is absent.

### L1 — Per-Asset 200-day SMA Trend Gating

For each asset at signal date T:

- `trend_signal_i = 1 if close_i(T) > SMA200_i(T) else 0`
- If `trend_signal_i == 0`, the asset's raw weight is forced to zero.
- Released capital from gated risk_core / stabilizer assets flows to `SGOV` defensive.

Edge cases:

- Insufficient history (<200 trading days): asset is gated off (fail closed).
- `SGOV` itself is never gated; it remains available as defensive.

### L2 — Inverse-Volatility Weighting With 8% Target

Reuse B010 modules (`trade/strategies/risk_parity/` weight engine and target-vol scaling):

- After L1 gating, compute inverse-volatility weights over the non-gated assets:
  ```
  raw_weight_i = 1 / annualized_vol_i
  weight_i = raw_weight_i / sum(raw_weight)
  ```
- Compute estimated portfolio volatility and apply target-vol scaling capped at 1.0:
  ```
  exposure_scale = min(target_vol / est_portfolio_vol, 1.0)
  ```
- Remaining exposure (1.0 − exposure_scale) is held in `SGOV`.

This is the same machinery as B010; B013 documents the reuse explicitly and writes integration tests that depend on B010 contracts.

### L3 — Portfolio-Level Regime Detection And Exposure Adjustment

At each signal date T:

- Compute portfolio daily returns over the trailing slow_vol_window window using L2 weights from the prior period.
- Fast vol: annualized vol of portfolio daily returns over `regime_fast_vol_window_days = 20`.
- Slow vol: annualized vol over `regime_slow_vol_window_days = 120`.
- SPY trend: `close_SPY(T) > SMA200_SPY(T)`.

Regime classification:

| Condition | Regime |
|---|---|
| `fast_vol > slow_vol * 1.5` AND `SPY < SMA200_SPY` | `CRISIS` |
| Not crisis, AND `SPY < SMA200_SPY` | `BEAR` |
| Otherwise | `NORMAL` |

Exposure adjustment:

- `NORMAL`: L1-and-L2 derived weights pass through.
- `BEAR`: rely on per-asset L1 gating; no additional portfolio-level reduction.
- `CRISIS`: scale all non-defensive weights by `regime_crisis_exposure_scale = 0.5`. Released capital flows to `SGOV`.

Output of L3 includes the regime label, the trigger metrics, and a `human_review_required: true` flag when regime is `CRISIS` (mirrors B011 kill-switch payload convention so reports stay consistent).

### Tolerance-Band Rebalancing With Regime Override

At each monthly rebalance signal date:

1. Compute target weights via L1 → L2 → L3 pipeline.
2. Compare to prior period's effective weights per asset.
3. **Regime override check**: if regime label changed (NORMAL ↔ BEAR ↔ CRISIS) vs prior period, **always rebalance fully**.
4. Otherwise, only emit trades for assets where `|target_i - current_i| > tolerance_band`. Other assets retain prior weights; defensive sleeve absorbs any rounding residual.
5. The B011 account-level 15% drawdown kill-switch continues to apply as the outer safety layer when this strategy runs inside the Master Portfolio. When B013 runs standalone, the same kill-switch mechanic is also wired in at the strategy level so reports stay comparable.

### Reports And Baselines

JSON/Markdown reports expose:

- Strategy id and config reference.
- Snapshot id / manifest reference when the real historical snapshot is used.
- Aggregated equity curve, annualized return, annualized volatility, Sharpe, maximum drawdown, turnover, transaction costs.
- Per-asset target weights history.
- Per-asset L1 gating history.
- Regime history (timeline of NORMAL / BEAR / CRISIS).
- Tolerance-band statistics: number of suppressed trades, % turnover saved vs no-band baseline.
- Calculated baselines:
  - Static 60/40 ETF/defensive quarterly rebalance (reuse B011 calculated baseline mechanic, no new code).
  - B006 Global ETF Momentum result on overlapping period (load existing fixture / snapshot result).
  - B010 Risk Parity result on overlapping period.
- 2020 stress window (2020-02-01 → 2020-12-31) drawdown and recovery metrics.
- 2022 stress window (2022-01-01 → 2022-12-31) drawdown and recovery metrics.
- Research limitations and data quality flags.
- Explicit `disclaimer` field: "research-only, not a trading instruction".

Acceptance gate values (for F007 stress validation):

- 2022 max drawdown `< 15%` on the real historical snapshot (matches user proposal target).
- 2020 max drawdown `< 15%` on the real historical snapshot.
- Aggregate turnover demonstrably reduced vs a no-tolerance-band variant on the same snapshot (F008 sensitivity sweep produces the comparison).

If the snapshot is not present in CI, the gate is reported as `skipped` with explicit rationale (not a failure).

### Lightweight Parameter Sensitivity Sweep

A deterministic one-at-a-time sweep over canonical defaults:

- `target_volatility`: {0.06, 0.08, 0.10}
- `regime_fast_vol_window_days`: {15, 20, 30}
- `regime_slow_vol_window_days`: {90, 120, 180}
- `regime_crisis_ratio`: {1.3, 1.5, 1.8}
- `tolerance_band`: {0.00, 0.03, 0.05}
- `trend_window_days`: {150, 200, 250}

Each variation runs the full backtest on the synthetic fixture (CI-safe). Optionally on the real snapshot when present. Output is `data/research/regime-adaptive-sensitivity-<timestamp>.json` plus a Markdown summary committed under `docs/test-reports/research/` (no live data, no AI, no broker, no env access). The sweep is deterministic, single-process, fixture-first, and finishes under a few seconds on the synthetic fixture.

This is **not** a learned optimizer, **not** Monte Carlo, **not** an automated parameter-tuning loop. It exists so the literature defaults can be verified.

### Master Portfolio Integration

B011 master configuration grows a new sleeve entry:

```text
{
  id: "regime_adaptive",
  type: "implemented_strategy",
  strategy_ref: "regime_adaptive_multi_asset",
  planning_weight: 0.0,
  role: "regime defensive overlay",
}
```

Backwards-compat invariants:

- `planning_weight = 0.0` so existing B011 signoff behavior is unchanged.
- Existing satellite stubs (US Quality 0.20, HK-China 0.10) remain in place.
- Master portfolio's planning weights `momentum 0.40 + risk_parity 0.30 + us_quality_stub 0.20 + hk_china_stub 0.10 + regime_adaptive 0.00 = 1.00`.
- Master backtest path treats `regime_adaptive` as implemented but zero-weighted: it does not invoke the strategy backtest when `planning_weight == 0` to avoid unnecessary computation; it does validate the strategy is loadable.
- User may set `planning_weight > 0` in a future planning step; that is not part of B013 acceptance.

### Safety And Regression

All existing safety boundaries remain mandatory and B013-specific tests prove:

- B013 modules contain no forbidden broker SDK imports (reuse B012 `FORBIDDEN_BROKER_SDK_MODULES`).
- B013 modules contain no AI/LLM SDK imports (`openai`, `anthropic`, `google.generativeai`, `langchain`, etc.) — add the AI SDK list to the regression scanner.
- B013 modules contain no paper-trading API URLs.
- B013 modules contain no `os.environ` / `os.getenv` reads. The public data acquisition script may read env, but it lives under `scripts/` and is excluded from the strategy module scan.
- B013 backtest path performs no socket I/O during default-fixture run.
- Reports and docstrings include the research-only disclaimer; tests assert absence of `paper-execution`, `live-execution`, `executed-order`, `filled`, `place_order`, `submit_order` phrasing in B013 outputs.
- Master Portfolio backwards-compat: existing B011 tests continue to pass without modification (other than the new sleeve definition).
- Required local checks must pass: pytest, ruff, compileall, mypy.

## Feature Requirements

### F001 Strategy Configuration And Universe Boundaries

Executor: generator.

Add `RegimeAdaptiveConfig` dataclass with the 9-symbol universe (Risk Core / Stabilizer / Defensive classification), default parameters (trend 200-SMA, vol target 8%, regime fast/slow 20/120, regime ratio 1.5, crisis exposure scale 0.5, tolerance band 0.03, drawdown 0.15, max exposure 1.0, defensive symbol SGOV), and validation. Tests cover default construction, validation success and failure paths, classification correctness, and serialization.

### F002 Historical Public Data Snapshot Acquisition

Executor: generator.

Reuse B009 snapshot infrastructure. Provide an opt-in `scripts/acquire_regime_adaptive_snapshot.py` (or equivalent CLI entry) that downloads daily OHLCV + adjusted close for the 9-asset universe across 2018-01-01 to 2025-12-31, writes a manifest at `data/public-cache/regime-adaptive-prices-manifest.json`, and stores price files under `data/public-cache/` (gitignored). The script must fail closed on missing assets and never run during default CI. Tests cover manifest schema, fail-closed behavior on simulated missing assets, and snapshot id determinism. Real network call is only exercised when the user runs the script manually.

### F003 L1 Per-Asset 200-day SMA Trend Gating

Executor: generator.

Implement `apply_trend_gating(prices, config)` that, for each asset and signal date, computes the 200-day SMA from adjusted close and returns a boolean gating mask plus per-asset raw weight zero-outs. Insufficient history (<200 days) gates the asset off (fail closed). `SGOV` (defensive) is never gated. Tests cover full-history pass-through, partial-history fail-closed, transitions at threshold, and that gated capital is reported as available for defensive routing.

### F004 L2 Inverse-Volatility Weighting With 8% Target

Executor: generator.

Wire the regime-adaptive strategy to the existing B010 inverse-volatility weight engine and target-volatility exposure-scaling utility. Configure `target_volatility = 0.08` as the default for this strategy. Insert L2 after L1 gating so only non-gated assets enter weight estimation; gated assets carry zero weight. Residual exposure after target-vol scaling routes to `SGOV`. Tests verify the integration contract with B010 modules (no duplication of B010 logic) and round-trip through the L1 → L2 pipeline.

### F005 L3 Regime Detection And Exposure Adjustment

Executor: generator.

Implement `detect_regime(prices, prior_weights, config)` returning `RegimeState(regime: Literal["NORMAL","BEAR","CRISIS"], fast_vol, slow_vol, ratio, spy_trend_signal, triggered_at, human_review_required)`. Implement `apply_regime_exposure_adjustment(weights, regime_state, config)` which, on `CRISIS`, scales all non-defensive weights by `regime_crisis_exposure_scale = 0.5` and routes the released exposure to `SGOV`. Tests cover all four classification quadrants (vol ratio low/high × SPY trend up/down), exposure scale correctness, defensive absorption, and `human_review_required` flag wiring.

### F006 Tolerance-Band Rebalancing And Backtest Workflow

Executor: generator.

Implement the monthly backtest workflow that:

1. Reads price history (snapshot or fixture).
2. At each monthly rebalance signal date, runs L1 → L2 → L3 to derive target weights.
3. Compares to prior period effective weights; emits trades only where `|target_i − current_i| > tolerance_band`. On regime transition, bypass the band and rebalance fully.
4. Applies T-day close signal / T+1 open execution semantics consistent with B006/B010.
5. Records rebalance trace, equity curve, turnover, transaction costs, regime history, gating history, snapshot references.

Tests cover happy-path monthly cadence, tolerance-band suppression, regime-override-forces-rebalance, T+1 execution, deterministic equity curve, turnover bookkeeping, and account-level 15% drawdown kill-switch wiring.

### F007 Reports, Baselines, And Stress Validation

Executor: generator.

Implement JSON/Markdown report generation including aggregated equity, annualized metrics, turnover, transaction costs, per-asset weight history, gating history, regime history, tolerance-band statistics, snapshot/manifest references, account-level risk flags, research limitations, and the fixed research-only disclaimer. Include calculated baselines: static 60/40 (reuse B011 mechanic), B006 momentum and B010 risk parity on overlapping periods (load existing results). Implement the stress validation suite that, when the real historical snapshot is present, asserts 2020 and 2022 window max drawdown `< 15%`; when the snapshot is absent, reports `skipped` rather than failing. Tests cover report schema, baseline integration, stress gate pass/skip semantics, and disclaimer presence.

### F008 Lightweight Parameter Sensitivity Sweep

Executor: generator.

Implement a deterministic one-at-a-time parameter sweep over the six canonical knobs (target vol, fast/slow vol windows, regime ratio, tolerance band, trend window) with three values each (literature default ± 1 step). Run the full backtest on the synthetic fixture for each variation. Optional run on the real snapshot when present. Emit a JSON sensitivity report and a Markdown summary under `docs/test-reports/research/`. Sweep must be deterministic, single-process, complete in seconds on the synthetic fixture, and never invoke network or external services. Tests cover deterministic output, parameter coverage, and absence of network / env / broker imports.

### F009 Master Portfolio Sleeve Integration

Executor: generator.

Extend B011 Master Portfolio configuration with a new sleeve entry `regime_adaptive` (`type: implemented_strategy`, `planning_weight: 0.0`, `role: regime defensive overlay`). Update planning-weight validation to remain at sum = 1.0 across the now-five-entry sleeve set (`momentum 0.40 + risk_parity 0.30 + us_quality_stub 0.20 + hk_china_stub 0.10 + regime_adaptive 0.00`). Master backtest path treats zero-weight implemented strategies as loadable-but-uninvoked. Existing B011 tests must continue to pass without modification (beyond the new sleeve entry). Tests cover the new sleeve config, sum invariant, zero-weight short-circuit, and the loadability check.

### F010 Safety Guard And Workflow Regression

Executor: generator.

Add regression coverage proving B013 modules contain no forbidden broker SDK imports (reuse B012 list), no AI/LLM SDK imports (new list: `openai`, `anthropic`, `google.generativeai`, `langchain`, `transformers`, `torch`, `tensorflow`, `sklearn` outside research scripts), no paper-trading API URLs, no `os.environ` / `os.getenv` reads in strategy modules (acquisition script is excluded), no socket I/O during fixture-based runs, and that reports / docstrings carry the research-only disclaimer. Required local checks must pass: pytest, ruff, compileall, mypy.

### F011 Independent Evaluation

Executor: codex.

Evaluator runs local/CI-safe L1 verification. Must confirm:

- B013 implements the regime-adaptive multi-asset MVP per spec.
- L1 + L2 + L3 pipeline composes correctly and is deterministic.
- Tolerance-band rebalancing reduces turnover and is overridden on regime transitions.
- Real historical snapshot manifest is loadable when present; default CI works without it.
- 2020 and 2022 stress windows produce a report; when the snapshot is loaded, max drawdown is `< 15%` (acceptance gate). When the snapshot is absent in CI, the gate reports `skipped` correctly.
- Parameter sensitivity sweep is deterministic and offline.
- Master Portfolio integration: new sleeve at 0 weight; existing B011 invariants preserved.
- All no-live / no-secret / no-network-by-default / no-broker / no-paper / no-AI safety guards remain intact.

Produce review and signoff under `docs/test-reports/`. Signoff must explicitly note the real-snapshot acquisition operation status (acquired / pending / skipped) and whether the 2020/2022 stress gates passed, skipped, or failed.

## Acceptance Summary

B013 is complete only when:

- Required checks pass locally: pytest, ruff, compileall, mypy.
- `RegimeAdaptiveConfig` exists with the 9-asset universe and validates.
- B009-style real historical public data snapshot acquisition script is opt-in, deterministic, fail-closed, and produces a committed manifest. Default CI runs without the real snapshot.
- L1 per-asset 200-day SMA gating, L2 inverse-vol with 8% target (reusing B010), and L3 regime detection compose deterministically.
- 3% tolerance-band rebalancing suppresses small trades, with regime transitions forcing a full rebalance.
- Reports include aggregated metrics, per-asset weight/gating/regime histories, tolerance-band turnover savings, calculated baselines (60/40, B006, B010), and 2020/2022 stress validation outputs.
- Parameter sensitivity sweep runs deterministically over 6 knobs and emits a research report.
- B011 Master Portfolio gains a `regime_adaptive` sleeve at `planning_weight = 0.0`; existing B011 signoff invariants preserved.
- No forbidden broker SDK, AI/LLM SDK, paper-trading API URL, env reads in strategy modules, socket I/O on default fixture runs, or paper/live execution language is introduced anywhere in B013 modules.
- Reports / journals / docstrings carry the research-only disclaimer.
- Evaluator signs off F011 with explicit notes on snapshot acquisition status and 2020/2022 stress gate outcomes.
