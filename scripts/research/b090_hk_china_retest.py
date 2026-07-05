#!/usr/bin/env python
"""B090 F001 — real-vs-proxy HK/China retest with the 200D MA warmup fix.

Research-only (touches NO strategy/production code). Reuses B063's decision
harness (:mod:`trade.backtest.hk_china_comparison_runner`) unchanged.

B063's methodology bug: the real individual-stock strategy went defensive on
~20/20 quarters because the fetched price frame started at the scored window, so
the first ~200 trading days had NO 200D-MA / 12m-momentum warmup — the
trend/scoring gate starved every early quarter and forced it defensive (0 stock
picks). The fix = provide >=200 trading days of price history BEFORE the first
scored quarter, so the MA/momentum gates are warm and the real strategy can
actually participate.

Two hard data facts constrain the honest window:
  * The shared defensive asset **SGOV** only lists from 2020-05-28 — a defensive
    quarter before that cannot be priced (the engine KeyErrors), so the scored
    signal window is floored at SGOV's inception. This is a real data limit, not
    a choice.
  * Every real stock was fetched with FULL history (back to 2001-2004), so at
    the 2020 window start the MA/momentum gates have years of warmup available.

Demonstration (isolates the warmup effect, same signal dates both runs):
  * NO-WARMUP  = frame truncated to start at the scored-window start (SGOV
    inception) -> early quarters have <200d history -> reproduces B063's
    starved / forced-defensive early quarters.
  * WITH-WARMUP = full-history frame -> MA/momentum warm at the window start ->
    the real strategy participates.

We also apply the task-literal 200th-shared-trading-day signal filter and report
it as a diagnostic (it is subsumed by the stricter SGOV floor in this dataset).

Run:  workbench/backend/.venv/bin/python -m scripts.research.b090_hk_china_retest
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from trade.backtest.hk_china_comparison import PROXY_TICKERS, ComparisonResult
from trade.backtest.hk_china_comparison_runner import (
    build_usd_frames,
    run_proxy_vs_real_comparison,
    shared_quarterly_signal_dates,
)
from trade.backtest.monthly import BacktestParameters
from trade.data.fx import FxConverter
from trade.data.hk_china_real_universe import (
    REAL_RISK_PROXIES,
    REAL_UNIVERSE_TICKERS,
    load_real_universe,
    usd_price_bars,
)
from trade.strategies.hk_china_momentum.factors import _wide_close, above_200d_ma
from trade.strategies.hk_china_momentum.parameters import HkChinaMomentumParameters
from trade.strategies.hk_china_real.construction import build_real_portfolio
from trade.strategies.hk_china_real.parameters import HkChinaRealParameters

_OUT_DIR = Path("data/research/b090_hk")
_UNIFIED_CSV = _OUT_DIR / "unified_prices.csv"
_FX_CSV = _OUT_DIR / "fx_daily.csv"

_DEFENSIVE_ASSET = "SGOV"
_WARMUP_TRADING_DAYS = 200


def _equity_trading_dates(usd_prices: pd.DataFrame, equity: frozenset[str]) -> set[date]:
    """Dates on which at least one *equity* name traded (defensive asset excluded)."""

    return {bar.date for bar in usd_price_bars(usd_prices) if bar.symbol in equity}


def shared_trading_days(proxy_usd: pd.DataFrame, real_usd: pd.DataFrame) -> list[date]:
    """Sorted intersection of the proxy-equity and real-equity trading calendars."""

    proxy_dates = _equity_trading_dates(proxy_usd, frozenset(PROXY_TICKERS))
    real_dates = _equity_trading_dates(real_usd, frozenset(REAL_UNIVERSE_TICKERS))
    return sorted(proxy_dates & real_dates)


def warmup_filter(
    signal_dates: tuple[date, ...],
    shared_days: list[date],
    *,
    warmup: int = _WARMUP_TRADING_DAYS,
) -> tuple[date, ...]:
    """Keep only signal dates on/after the ``warmup``-th shared trading day.

    Too-short history (< ``warmup`` shared days) -> no valid cutoff -> empty."""

    if len(shared_days) < warmup:
        return ()
    cutoff = shared_days[warmup - 1]
    return tuple(d for d in signal_dates if d >= cutoff)


def _defensive_asset_floor(unified: pd.DataFrame) -> date:
    """Earliest date the defensive asset (SGOV) trades — the pricing floor.

    A defensive quarter before this cannot be priced, so no signal date may
    precede it."""

    sgov = unified[unified["ticker"] == _DEFENSIVE_ASSET]
    if sgov.empty:
        raise SystemExit(f"defensive asset {_DEFENSIVE_ASSET} absent from frame")
    return pd.to_datetime(sgov["date"]).min().date()


def _run(
    unified: pd.DataFrame,
    converter: FxConverter,
    signal_dates: tuple[date, ...],
) -> ComparisonResult:
    """Build USD frames from ``unified`` and run the B063 comparison over
    ``signal_dates`` (dates fixed by caller so warmup/no-warmup use identical
    dates and differ only in the price history depth of ``unified``)."""

    proxy_usd, real_usd = build_usd_frames(
        unified,
        converter,
        proxy_defensive_asset=_DEFENSIVE_ASSET,
        real_defensive_asset=_DEFENSIVE_ASSET,
    )
    return run_proxy_vs_real_comparison(
        proxy_usd_prices=proxy_usd,
        real_usd_prices=real_usd,
        signal_dates=signal_dates,
        proxy_parameters=HkChinaMomentumParameters(),
        real_parameters=HkChinaRealParameters(),
        backtest_parameters=BacktestParameters(),
    )


@dataclass(frozen=True, slots=True)
class RetestOutcome:
    scored_window_start: date
    all_signal_dates: tuple[date, ...]
    warmup_filtered_dates: tuple[date, ...]
    scored_signal_dates: tuple[date, ...]
    no_warmup: ComparisonResult
    with_warmup: ComparisonResult


def run_retest(unified: pd.DataFrame, converter: FxConverter) -> RetestOutcome:
    """The full B090 retest: derive the runnable window, then compare a
    no-warmup (truncated-history) run against a with-warmup (full-history) run
    over identical signal dates."""

    full_proxy, full_real = build_usd_frames(
        unified,
        converter,
        proxy_defensive_asset=_DEFENSIVE_ASSET,
        real_defensive_asset=_DEFENSIVE_ASSET,
    )
    all_signals = shared_quarterly_signal_dates(full_proxy, full_real)
    shared_days = shared_trading_days(full_proxy, full_real)
    warmup_dates = warmup_filter(all_signals, shared_days)

    # SGOV pricing floor — the binding constraint on the runnable window.
    floor = _defensive_asset_floor(unified)
    scored_signals = tuple(d for d in all_signals if d >= floor)
    if not scored_signals:
        raise SystemExit("no signal dates on/after the SGOV pricing floor")

    # NO-WARMUP: truncate stock history to the scored-window start (reproduces
    # B063's starved early quarters). WITH-WARMUP: full history.
    truncated = unified[pd.to_datetime(unified["date"]) >= pd.Timestamp(floor)].copy()
    no_warmup = _run(truncated, converter, scored_signals)
    with_warmup = _run(unified, converter, scored_signals)

    return RetestOutcome(
        scored_window_start=floor,
        all_signal_dates=all_signals,
        warmup_filtered_dates=warmup_dates,
        scored_signal_dates=scored_signals,
        no_warmup=no_warmup,
        with_warmup=with_warmup,
    )


def _fmt(value: float) -> str:
    return f"{value:+.4f}"


def _print_report(outcome: RetestOutcome) -> None:
    nw, ww = outcome.no_warmup, outcome.with_warmup
    print(
        f"\nsignal dates (full shared history): {len(outcome.all_signal_dates)} "
        f"({outcome.all_signal_dates[0]}..{outcome.all_signal_dates[-1]})"
    )
    print(
        f"200D-warmup-filtered signal dates: {len(outcome.warmup_filtered_dates)} "
        f"(task-literal filter; subsumed by SGOV floor here)"
    )
    print(
        f"SGOV pricing floor: {outcome.scored_window_start} -> "
        f"{len(outcome.scored_signal_dates)} runnable scored quarters "
        f"({outcome.scored_signal_dates[0]}..{outcome.scored_signal_dates[-1]})"
    )

    def _real_lines(label: str, side: object) -> None:
        real = side.real  # type: ignore[attr-defined]
        total = real.total_periods
        print(f"  {label}:")
        print(f"    real defensive_periods        = {real.defensive_periods}/{total}")
        print(f"    real forced_defensive_periods = {real.forced_defensive_periods}/{total}")
        print(f"    real avg_scored/quarter       = {real.avg_scored:.2f}")
        print(f"    real avg_holdings/quarter     = {real.avg_holdings:.2f}")

    print("\n=== WARMUP FIX EFFECT (real strategy, identical signal dates) ===")
    _real_lines(f"NO-WARMUP  (history truncated to {outcome.scored_window_start})", nw)
    _real_lines("WITH-WARMUP (full stock history back to 2001-2004)", ww)
    d_def = nw.real.defensive_periods - ww.real.defensive_periods
    print(f"  -> warmup changed real defensive_periods by {-d_def:+d} "
          f"(fewer starved quarters is the fix working)")

    print("\n=== PROXY vs REAL (WITH-WARMUP — the methodology-correct run) ===")
    print(f"{'metric':<28}{'proxy':>14}{'real':>14}")
    for name, pv, rv in (
        ("CAGR", ww.proxy.metrics.cagr, ww.real.metrics.cagr),
        ("Sharpe", ww.proxy.metrics.sharpe, ww.real.metrics.sharpe),
        ("annualized_vol", ww.proxy.metrics.annualized_volatility,
         ww.real.metrics.annualized_volatility),
        ("max_drawdown", ww.proxy.metrics.max_drawdown, ww.real.metrics.max_drawdown),
    ):
        print(f"{name:<28}{_fmt(pv):>14}{_fmt(rv):>14}")
    print(f"{'defensive_periods':<28}{ww.proxy.defensive_periods:>14}{ww.real.defensive_periods:>14}")
    print(f"{'forced_defensive_periods':<28}"
          f"{ww.proxy.forced_defensive_periods:>14}{ww.real.forced_defensive_periods:>14}")
    print(f"{'avg_holdings':<28}{ww.proxy.avg_holdings:>14.2f}{ww.real.avg_holdings:>14.2f}")

    print("\n=== BIAS NOTES (WITH-WARMUP run) ===")
    for note in ww.bias_notes:
        print(f"  - {note}")


def defensive_reason_breakdown(
    real_usd: pd.DataFrame,
    signal_dates: tuple[date, ...],
    parameters: HkChinaRealParameters,
) -> Counter[str]:
    """Per-quarter reason the real strategy is defensive (root-cause evidence)."""

    reasons: Counter[str] = Counter()
    for as_of in signal_dates:
        universe = tuple(e.ticker for e in load_real_universe(as_of=as_of))
        portfolio = build_real_portfolio(
            prices=real_usd, universe_tickers=universe, as_of=as_of, parameters=parameters
        )
        reasons[portfolio.reason] += 1
    return reasons


def calendar_misalignment_probe(
    real_usd: pd.DataFrame, as_of: date, *, ma_long: int = 200
) -> None:
    """Show WHY the 200D-MA is NaN on the multi-calendar frame vs an HK-only one.

    The real universe mixes HK / mainland-A / US(SGOV) trading calendars into one
    wide frame. ``above_200d_ma`` rolls a 200-ROW window with min_periods=200, so
    cross-market-only dates (NaN for a given ticker) starve the window below 200
    non-NaN observations → MA is NaN → the ticker reads 'below MA' forever."""

    wide = _wide_close(real_usd, as_of)
    last200 = wide.tail(ma_long)
    print(f"\n=== ROOT-CAUSE PROBE (as_of={as_of}, 200-row MA window) ===")
    print("  bellwether  non-NaN/200(union)  above_MA(union)  above_MA(HK-only)")
    hk_only = real_usd[real_usd["ticker"].str.endswith(".HK")]
    above_union = above_200d_ma(real_usd, as_of, ma_long)
    above_hk = above_200d_ma(hk_only, as_of, ma_long)
    for ticker in REAL_RISK_PROXIES:
        non_nan = int(last200[ticker].notna().sum()) if ticker in last200 else 0
        u_flag = bool(above_union.get(ticker, False))
        hk_flag = bool(above_hk.get(ticker, False)) if ticker in above_hk.index else "n/a"
        print(f"  {ticker:<11} {non_nan:>10}/200        {u_flag!s:<15}  {hk_flag}")
    print("  -> <200 non-NaN => MA=NaN => 'below MA' on the union frame regardless of "
          "warmup; the HK-only frame (single calendar) computes a valid MA.")


def _load_unified() -> pd.DataFrame:
    if not _UNIFIED_CSV.is_file():
        raise SystemExit(f"missing {_UNIFIED_CSV} — run b090_hk_china_fetch first")
    return pd.read_csv(_UNIFIED_CSV, dtype={"ticker": str})


def main() -> int:
    unified = _load_unified()
    converter = FxConverter.load(path=_FX_CSV)
    print(
        f"loaded {_UNIFIED_CSV.name}: {len(unified)} rows, "
        f"{unified['ticker'].nunique()} tickers; FX currencies={converter.currencies()}"
    )
    outcome = run_retest(unified, converter)
    _print_report(outcome)

    # Root-cause: why is real 100% defensive even WITH full warmup?
    _, real_usd = build_usd_frames(
        unified, converter, proxy_defensive_asset=_DEFENSIVE_ASSET,
        real_defensive_asset=_DEFENSIVE_ASSET,
    )
    reasons = defensive_reason_breakdown(
        real_usd, outcome.scored_signal_dates, HkChinaRealParameters()
    )
    print("\n=== REAL DEFENSIVE-REASON BREAKDOWN (with-warmup, per quarter) ===")
    for reason, count in reasons.most_common():
        print(f"  {reason}: {count}/{len(outcome.scored_signal_dates)}")
    # Illustrative date where Tencent was clearly uptrending, so union-frame
    # 'below MA' is unambiguously the calendar-NaN artefact, not a real downtrend.
    probe_date = date(2025, 6, 30)
    if probe_date not in outcome.scored_signal_dates:
        probe_date = outcome.scored_signal_dates[-1]
    calendar_misalignment_probe(real_usd, probe_date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
