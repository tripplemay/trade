# Backtest Report Schema

## Purpose

B006 should output reproducible JSON and Markdown reports. This document defines the expected fields at the planning level.

## Execution Price Decision

B006 Global ETF Backtest MVP must use T-day close data for signal generation and T+1 open price as the default execution price assumption. T-day close must not be used as the default execution price for a signal generated after the close.

## Snapshot Tail Headroom for T+1 Execution

Sweep, comparison and reporting CLIs that consume a snapshot **must reserve at least one trading-day headroom after the last signal date** they actually use. The T+1 execution model requires the next trading day to exist after each signal date — without that headroom, a signal generated at the snapshot tail has no executable T+1 day and the run fails with `no trading date exists after signal_date` (or equivalent boundary error), even though the data point at the signal date itself is present.

**Required practice:**

1. When a CLI accepts a snapshot and a window, the default behavior must trim the last signal date so that one trading day of headroom remains; alternatively, the CLI must explicitly document and surface the assumed tail headroom in its run header / report metadata so reviewers can audit the cutoff.
2. When a CLI ingests a snapshot end-to-end without an explicit window, it must either (a) auto-trim the tail to leave headroom, or (b) refuse to run and ask the user for an explicit window.
3. New sweep / comparison / report scripts added under `scripts/` are subject to this rule; existing scripts should be retrofitted opportunistically when touched.

**Reference incident — B019 F004 (2026-05-15):** `scripts/generate_b015_activation_policy_report.py` consumed the full B014 snapshot to its tail without trimming. The last signal date had no T+1 trading day in the snapshot, triggering the boundary error. Codex worked around it by passing an explicit window with one-trading-day headroom; logged as Soft-watch S1 in `docs/test-reports/B019-retune-signoff-2026-05-15.md` for a permanent script-side fix.

## Required JSON Sections

| Section | Required Fields |
|---|---|
| `run` | run ID, timestamp, package version or git SHA if available, environment, command/config reference |
| `strategy` | strategy ID, strategy version, universe ID, rebalance frequency, signal timing, execution timing, execution price policy |
| `data` | data snapshot ID, fixture/public/local source label, date range, trading calendar, adjusted price policy |
| `parameters` | momentum windows, weights, Top N, defensive asset, trend filter, costs, slippage, benchmark |
| `execution` | signal date/time, signal price field, execution date/time, execution price field, execution assumption, slippage model |
| `portfolio` | starting capital assumption, strategy budget, target weights policy, max position constraints |
| `risk` | exposure limits, drawdown, kill-switch state, violations, warning flags |
| `metrics` | CAGR, annualized volatility, Sharpe, max drawdown, turnover, monthly returns, yearly returns, benchmark comparison |
| `outputs` | paths to Markdown/CSV/chart files if generated |

## Markdown Report Requirements

Markdown reports should be human-readable and include:

- Summary result.
- Data and parameter assumptions.
- Signal price and execution price assumptions.
- Performance metrics.
- Benchmark comparison.
- Drawdown and turnover discussion.
- Risk violations or warnings.
- Reproducibility section with snapshot/config references.

## Risk Flags

Reports should explicitly flag:

- Missing or invalid data.
- Rebalance dates skipped because of calendar/data gaps.
- Missing T+1 open price or fallback execution-price use.
- Position limit violations.
- Defensive-asset switch activation.
- Account-level drawdown kill-switch state when available.
- Any use of optional public data rather than committed fixture data.

## Non-Goals

- This schema does not dictate frontend rendering; how a workbench / dashboard consumes the JSON is a consumer concern (see PRD §7).
- No live execution report.
- No broker fill report.
- No personalized investment or tax advice.
