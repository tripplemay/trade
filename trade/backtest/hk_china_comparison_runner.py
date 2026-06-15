"""B063 F004 — assemble + run the proxy-vs-real comparison from on-disk frames.

The B063 F003 harness (:mod:`trade.backtest.hk_china_comparison`) is the pure
two-backtest comparator. This module is the **assembly layer** that turns the
unified prices frame + FX rates into the two same-caliber USD frames the harness
needs, derives the shared quarterly signal-date calendar, and returns the F004
decision-report payload.

It is kept in ``trade`` (offline, mypy-strict, CI-tested) and is fed an
already-loaded prices ``DataFrame`` + an :class:`~trade.data.fx.FxConverter` so
it stays pure and testable. The thin VM/ops wrapper
``scripts/test/hk_china_proxy_vs_real_backtest.py`` does the disk IO and runs it
on the prod VM, where the real CN/HK + FX data actually live (``trade`` never
fetches — that is the workbench ``data_refresh`` job).

**Same-caliber fairness (spec §2/§3).** Both sides are converted to USD through
the SAME FX path (:func:`trade.data.hk_china_real_universe.to_usd_prices`; the
proxy ETFs and the defensive asset are US-listed, so they pass through
unchanged), and the signal dates are the **intersection** of the two trading
calendars' confirmed quarter-ends. Sharing the calendar matters because both
backtest engines fall back to the defensive asset when the signal date is not a
trading date in their *own* frame; picking dates present in both keeps a
CN/HK-vs-US calendar mismatch from spuriously forcing one side defensive.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from trade.backtest.hk_china_comparison import (
    PROXY_TICKERS,
    ComparisonResult,
    build_comparison_payload,
    run_proxy_vs_real_comparison,
)
from trade.backtest.master_portfolio import identify_quarter_end_signal_dates
from trade.backtest.monthly import BacktestError, BacktestParameters
from trade.data.fx import FxConverter
from trade.data.hk_china_real_universe import (
    PRICES_REQUIRED_COLUMNS,
    REAL_UNIVERSE_TICKERS,
    to_usd_prices,
    usd_price_bars,
)
from trade.strategies.hk_china_momentum.parameters import HkChinaMomentumParameters
from trade.strategies.hk_china_real.parameters import HkChinaRealParameters


def _subset_to_usd(
    unified_prices: pd.DataFrame,
    tickers: frozenset[str],
    converter: FxConverter,
) -> pd.DataFrame:
    """USD-converted long-format frame for ``tickers`` from the unified prices.

    Dates are normalized to ``datetime64`` (the shared momentum factors compare
    against ``pd.Timestamp(as_of)``). USD-quoted rows (proxy ETFs + the defensive
    asset) pass through :func:`to_usd_prices` unchanged; CNY/HKD rows convert at
    each bar's as-of FX rate."""

    missing = [c for c in PRICES_REQUIRED_COLUMNS if c not in unified_prices.columns]
    if missing:
        raise BacktestError(f"unified prices frame missing required columns {missing}")
    subset = unified_prices[unified_prices["ticker"].isin(tickers)].copy()
    if not subset.empty:
        subset["date"] = pd.to_datetime(subset["date"])
    return to_usd_prices(subset.reset_index(drop=True), converter)


def build_usd_frames(
    unified_prices: pd.DataFrame,
    converter: FxConverter,
    *,
    proxy_defensive_asset: str,
    real_defensive_asset: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The two same-caliber USD frames: ``(proxy_usd, real_usd)``.

    Proxy = the four US-listed ETFs (:data:`PROXY_TICKERS`) + its defensive
    asset. Real = the wide CN/HK individual-stock universe
    (:data:`REAL_UNIVERSE_TICKERS`) + its defensive asset, FX-converted to USD.
    Each side carries its own defensive asset so defensive periods can be priced
    on the same frame the signal runs on."""

    proxy_usd = _subset_to_usd(
        unified_prices, frozenset(PROXY_TICKERS) | {proxy_defensive_asset}, converter
    )
    real_usd = _subset_to_usd(
        unified_prices,
        frozenset(REAL_UNIVERSE_TICKERS) | {real_defensive_asset},
        converter,
    )
    return proxy_usd, real_usd


_PROXY_EQUITY: frozenset[str] = frozenset(PROXY_TICKERS)
_REAL_EQUITY: frozenset[str] = frozenset(REAL_UNIVERSE_TICKERS)


def _equity_trading_dates(usd_prices: pd.DataFrame, equity: frozenset[str]) -> set[date]:
    """Dates on which at least one *equity* name traded — the market's real
    calendar. The defensive asset (a US-listed bond ETF, present on both sides)
    is excluded on purpose: including it would inject the US calendar into the
    intersection and let a US-only date masquerade as a shared trading day."""

    return {bar.date for bar in usd_price_bars(usd_prices) if bar.symbol in equity}


def shared_quarterly_signal_dates(
    proxy_usd: pd.DataFrame, real_usd: pd.DataFrame
) -> tuple[date, ...]:
    """Confirmed quarter-ends on which BOTH markets' equities traded.

    The calendar is the intersection of the proxy ETF calendar and the real
    CN/HK calendar (defensive asset excluded). Sharing only days both markets
    were open keeps either engine from being spuriously forced defensive by a
    calendar mismatch (each indexes its selected names by the signal date);
    execution (T+1) still uses each engine's own full calendar, so a shared-only
    signal calendar never blocks execution."""

    proxy_dates = _equity_trading_dates(proxy_usd, _PROXY_EQUITY)
    real_dates = _equity_trading_dates(real_usd, _REAL_EQUITY)
    common = tuple(sorted(proxy_dates & real_dates))
    return identify_quarter_end_signal_dates(common)


def run_comparison_from_unified(
    unified_prices: pd.DataFrame,
    converter: FxConverter,
    *,
    proxy_parameters: HkChinaMomentumParameters | None = None,
    real_parameters: HkChinaRealParameters | None = None,
    backtest_parameters: BacktestParameters | None = None,
) -> tuple[ComparisonResult, tuple[date, ...]]:
    """Assemble the USD frames + shared calendar and run the F003 comparison.

    Returns ``(result, signal_dates)`` — the signal dates are returned so the
    report can record exactly which quarter-ends drove the comparison."""

    proxy_parameters = proxy_parameters or HkChinaMomentumParameters()
    real_parameters = real_parameters or HkChinaRealParameters()
    backtest_parameters = backtest_parameters or BacktestParameters()

    proxy_usd, real_usd = build_usd_frames(
        unified_prices,
        converter,
        proxy_defensive_asset=proxy_parameters.defensive_asset,
        real_defensive_asset=real_parameters.defensive_asset,
    )
    signal_dates = shared_quarterly_signal_dates(proxy_usd, real_usd)
    if not signal_dates:
        raise BacktestError(
            "no shared quarter-end signal dates between the proxy and real "
            "calendars — the real CN/HK price coverage does not overlap the proxy "
            "history by a full confirmed quarter (data not ready for comparison)"
        )
    result = run_proxy_vs_real_comparison(
        proxy_usd_prices=proxy_usd,
        real_usd_prices=real_usd,
        signal_dates=signal_dates,
        proxy_parameters=proxy_parameters,
        real_parameters=real_parameters,
        backtest_parameters=backtest_parameters,
    )
    return result, signal_dates


def _coverage(usd_prices: pd.DataFrame, tickers: tuple[str, ...]) -> dict[str, object]:
    """Per-frame data-coverage provenance for the report (window + which names
    actually have any USD bar)."""

    bars = usd_price_bars(usd_prices)
    present = sorted({bar.symbol for bar in bars})
    dates = sorted({bar.date for bar in bars})
    return {
        "window_start": dates[0].isoformat() if dates else None,
        "window_end": dates[-1].isoformat() if dates else None,
        "trading_dates": len(dates),
        "names_with_data": [t for t in tickers if t in present],
        "names_missing_data": [t for t in tickers if t not in present],
    }


def build_runner_payload(
    result: ComparisonResult,
    signal_dates: tuple[date, ...],
    proxy_usd: pd.DataFrame,
    real_usd: pd.DataFrame,
) -> dict[str, object]:
    """Full report payload: the F003 comparison payload + run metadata.

    The metadata block records the shared signal calendar and each frame's data
    coverage so the F004 decision report can state exactly what window + which
    real names backed the numbers (point-in-time honesty, spec §2)."""

    payload = build_comparison_payload(result)
    payload["run_metadata"] = {
        "signal_dates": [d.isoformat() for d in signal_dates],
        "n_signal_dates": len(signal_dates),
        "proxy_coverage": _coverage(proxy_usd, PROXY_TICKERS),
        "real_coverage": _coverage(real_usd, REAL_UNIVERSE_TICKERS),
    }
    return payload


__all__ = [
    "build_runner_payload",
    "build_usd_frames",
    "run_comparison_from_unified",
    "shared_quarterly_signal_dates",
]
