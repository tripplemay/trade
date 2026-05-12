# Backtest Report Schema

## Purpose

B006 should output reproducible JSON and Markdown reports. This document defines the expected fields at the planning level.

## Execution Price Decision

B006 Global ETF Backtest MVP must use T-day close data for signal generation and T+1 open price as the default execution price assumption. T-day close must not be used as the default execution price for a signal generated after the close.

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

- No formal frontend dashboard.
- No live execution report.
- No broker fill report.
- No personalized investment or tax advice.
