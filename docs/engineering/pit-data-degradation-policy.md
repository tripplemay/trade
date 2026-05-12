# PIT Data Degradation Policy

## Purpose

This policy defines how the system should behave when high-quality point-in-time (PIT) fundamentals are not available. It responds to the independent PRD/architecture audit finding that cheap retail data sources often do not provide reliable PIT financial statement data.

## Core Rule

No strategy may make serious historical performance claims from non-PIT fundamental data without explicit degradation labeling.

## US Multi-Factor Strategy Boundary

Until high-quality PIT fundamentals are licensed or verified, the US quality/momentum multi-factor strategy must degrade to price/volume-derived factors only, such as:

- Momentum.
- Low volatility.
- Trend.
- Liquidity derived from daily bars.

Quality factors that require financial statements must remain disabled or marked as non-PIT exploratory research.

## Non-PIT Fundamental Data Handling

If non-PIT fundamentals are used for exploratory research, the system must:

- Mark the run as degraded.
- Apply a conservative availability lag rather than using fiscal period end date.
- Record the assumed `available_at` rule.
- Exclude the run from production-readiness claims.
- Warn about look-ahead and revision bias in reports.

A default exploratory lag may be 2-3 trading days after a filing/accepted timestamp when such timestamp exists. If only fiscal period is available, the data is not suitable for serious backtesting.

## B006 Boundary

B006 Global ETF Backtest MVP should not implement fundamental multi-factor logic. It may implement price-only ETF momentum and should preserve PIT discipline through data snapshot IDs, signal time, and execution time recording.
