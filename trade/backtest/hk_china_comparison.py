"""B063 F003 — proxy-vs-real HK-China backtest comparison harness.

Runs the two HK-China backtests over the **same signal dates, same USD caliber,
same friction** and produces a **bias-aware** comparison:

* proxy : :func:`trade.backtest.hk_china.run_hk_china_quarterly_backtest`
  (US-listed ETFs MCHI/FXI/KWEB/ASHR — already USD, a diversified basket).
* real  : :func:`trade.backtest.hk_china_real.run_real_hk_china_quarterly_backtest`
  (wide individual-stock universe, USD-converted, point-in-time rule selection).

This is the **tool**; B063 F004 (Codex) runs it on the VM with real data and
writes the decision report. The harness deliberately bakes in the spec's two
honesty requirements:

* **§2 — no hindsight.** It reports the real side's point-in-time provenance
  (universe size, average names *eligible by listing date*, average names
  actually *scored*, defensive-quarter count split into rule-driven vs
  data-gap-forced) and emits a residual-selection-bias caveat, so a favourable
  real result is never read as proof without that context.
* **§3 — concentration vs data-source.** Both sides' metrics come from a single
  quarterly metric function (identical annualization), and the harness measures
  the concentration gap — both the *parameter* (selection ``top_n``) and the
  *realized* average holdings (diversified ETFs vs single names) — and emits a
  note that any edge must be attributed to concentration AND data-source.

**Same-caliber guarantees (fairness).** Both sides take the SAME kind of input —
a USD long-format prices frame — and BOTH the signal and the execution of each
side run on that one frame (the proxy signal is pinned via ``signal_prices`` so
it no longer self-loads from disk independently of execution). Both sides share
signal dates, starting capital, and friction. Metrics are quarterly-annualized
(``sqrt(4)``), matching :mod:`trade.reporting.hk_china`; a guard rejects
non-quarterly cadences so that annualization can never silently mismatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt

import pandas as pd

from trade.backtest.hk_china import HkChinaBacktestResult, run_hk_china_quarterly_backtest
from trade.backtest.hk_china_real import (
    RealHkChinaBacktestResult,
    run_real_hk_china_quarterly_backtest,
)
from trade.backtest.monthly import BacktestError, BacktestParameters, EquityPoint
from trade.data.hk_china_real_universe import REAL_UNIVERSE_TICKERS, usd_price_bars
from trade.strategies.hk_china_momentum.parameters import HkChinaMomentumParameters
from trade.strategies.hk_china_real.parameters import HkChinaRealParameters

_QUARTERS_PER_YEAR = 4.0
# Proxy ETF universe (the diversified baskets the real single names stand against).
PROXY_TICKERS: tuple[str, ...] = ("MCHI", "FXI", "KWEB", "ASHR")


@dataclass(frozen=True, slots=True)
class ComparisonMetrics:
    """Quarterly-annualized performance of one backtest equity curve."""

    cagr: float
    annualized_volatility: float
    sharpe: float
    max_drawdown: float
    turnover: float
    transaction_costs: float
    n_periods: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "cagr": self.cagr,
            "annualized_volatility": self.annualized_volatility,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "turnover": self.turnover,
            "transaction_costs": self.transaction_costs,
            "n_periods": self.n_periods,
        }


@dataclass(frozen=True, slots=True)
class VersionSummary:
    """One side (proxy or real) of the comparison: metrics + concentration +
    point-in-time provenance."""

    label: str
    metrics: ComparisonMetrics
    selection_top_n: int  # the parameter cap (concentration knob, spec §3)
    avg_holdings: float  # realized avg non-defensive names per period
    defensive_periods: int
    forced_defensive_periods: int  # subset forced by data gaps, not strategy rules
    total_periods: int
    universe_size: int
    holding_kind: str  # "diversified_etf" | "single_name"
    avg_candidates: float | None = None  # real-only: avg names eligible by listing date
    avg_scored: float | None = None  # real-only: avg names with enough history

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "metrics": self.metrics.as_dict(),
            "selection_top_n": self.selection_top_n,
            "avg_holdings": self.avg_holdings,
            "defensive_periods": self.defensive_periods,
            "forced_defensive_periods": self.forced_defensive_periods,
            "total_periods": self.total_periods,
            "universe_size": self.universe_size,
            "holding_kind": self.holding_kind,
            "avg_candidates": self.avg_candidates,
            "avg_scored": self.avg_scored,
        }


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """The full proxy-vs-real comparison + honest bias attribution."""

    proxy: VersionSummary
    real: VersionSummary
    starting_capital: float
    n_signal_dates: int
    usd_caliber: bool
    bias_notes: tuple[str, ...]


def _period_returns(equity_curve: tuple[EquityPoint, ...]) -> list[float]:
    returns: list[float] = []
    for earlier, later in zip(equity_curve, equity_curve[1:], strict=False):
        if earlier.value > 0:
            returns.append(later.value / earlier.value - 1.0)
    return returns


def _annualized_volatility(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    return sqrt(variance) * sqrt(_QUARTERS_PER_YEAR)


def _cagr(starting_capital: float, ending_value: float, n_points: int) -> float:
    if starting_capital <= 0 or n_points < 2:
        return 0.0
    if ending_value <= 0:
        # Total wipeout: report an honest -100% rather than 0.0 (which would mask a
        # catastrophic loss as "flat") and avoid a complex result from a negative base.
        return -1.0
    periods = n_points - 1
    # float ** float is typed Any (could be complex) — pin to float, as the proxy
    # report's _cagr does.
    return float((ending_value / starting_capital) ** (_QUARTERS_PER_YEAR / periods) - 1.0)


def _sharpe(returns: list[float], annualized_volatility: float) -> float:
    if not returns or annualized_volatility == 0:
        return 0.0
    annualized_return = (sum(returns) / len(returns)) * _QUARTERS_PER_YEAR
    return annualized_return / annualized_volatility


def _max_drawdown(equity_curve: tuple[EquityPoint, ...]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0].value
    worst = 0.0
    for point in equity_curve:
        peak = max(peak, point.value)
        if peak > 0:
            worst = min(worst, point.value / peak - 1.0)
    return worst


def _metrics(
    *,
    equity_curve: tuple[EquityPoint, ...],
    starting_capital: float,
    ending_value: float,
    turnover: float,
    transaction_costs: float,
) -> ComparisonMetrics:
    """Quarterly-annualized metrics for ONE equity curve — applied identically to
    both sides so the comparison is same-caliber."""

    returns = _period_returns(equity_curve)
    vol = _annualized_volatility(returns)
    return ComparisonMetrics(
        cagr=_cagr(starting_capital, ending_value, len(equity_curve)),
        annualized_volatility=vol,
        sharpe=_sharpe(returns, vol),
        max_drawdown=_max_drawdown(equity_curve),
        turnover=turnover,
        transaction_costs=transaction_costs,
        n_periods=max(len(equity_curve) - 1, 0),
    )


def _non_defensive_holdings(weights: dict[str, float], defensive_asset: str) -> int:
    return sum(
        1 for ticker, weight in weights.items() if ticker != defensive_asset and weight > 0
    )


def _summarize_proxy(
    result: HkChinaBacktestResult, *, defensive_asset: str, top_n: int
) -> VersionSummary:
    periods = result.rebalance_results
    holdings = [
        _non_defensive_holdings(period.signal.target_weights, defensive_asset)
        for period in periods
    ]
    defensive = sum(1 for period in periods if period.signal.is_defensive)
    metrics = _metrics(
        equity_curve=result.equity_curve,
        starting_capital=result.starting_capital,
        ending_value=result.ending_value,
        turnover=result.turnover,
        transaction_costs=result.cost_amount,
    )
    return VersionSummary(
        label="proxy",
        metrics=metrics,
        selection_top_n=top_n,
        avg_holdings=(sum(holdings) / len(holdings)) if holdings else 0.0,
        defensive_periods=defensive,
        # The proxy executes on the same frame its signal loads (consistent data),
        # so proxy defensives are rule-driven; no data-gap forcing is attributed.
        forced_defensive_periods=0,
        total_periods=len(periods),
        universe_size=len(PROXY_TICKERS),
        holding_kind="diversified_etf",
    )


def _summarize_real(
    result: RealHkChinaBacktestResult, *, defensive_asset: str, top_n: int
) -> VersionSummary:
    periods = result.rebalance_results
    holdings = [
        _non_defensive_holdings(period.signal.target_weights, defensive_asset)
        for period in periods
    ]
    defensive = sum(1 for period in periods if period.signal.is_defensive)
    # A defensive period whose construction DID select names was forced defensive
    # by a price-coverage gap, not by the strategy's risk-off/trend rules. Keeping
    # the two apart stops a data gap from masquerading as a strategy decision.
    forced = sum(
        1 for period in periods if period.signal.is_defensive and period.portfolio.selected
    )
    candidates = [period.portfolio.candidates for period in periods]
    scored = [period.portfolio.scored for period in periods]
    metrics = _metrics(
        equity_curve=result.equity_curve,
        starting_capital=result.starting_capital,
        ending_value=result.ending_value,
        turnover=result.turnover,
        transaction_costs=result.cost_amount,
    )
    return VersionSummary(
        label="real",
        metrics=metrics,
        selection_top_n=top_n,
        avg_holdings=(sum(holdings) / len(holdings)) if holdings else 0.0,
        defensive_periods=defensive,
        forced_defensive_periods=forced,
        total_periods=len(periods),
        universe_size=len(REAL_UNIVERSE_TICKERS),
        holding_kind="single_name",
        avg_candidates=(sum(candidates) / len(candidates)) if candidates else 0.0,
        avg_scored=(sum(scored) / len(scored)) if scored else 0.0,
    )


def _bias_notes(proxy: VersionSummary, real: VersionSummary) -> tuple[str, ...]:
    """Honest attribution baked into every comparison (spec §2 / §3)."""

    avg_candidates = real.avg_candidates if real.avg_candidates is not None else 0.0
    avg_scored = real.avg_scored if real.avg_scored is not None else 0.0
    return (
        # §2 — point-in-time, no hand-picking; surface PIT universe evolution.
        f"point-in-time: the real side selected names by rule each quarter from a "
        f"{real.universe_size}-name candidate set (avg {avg_candidates:.1f} were listing-eligible "
        f"and avg {avg_scored:.1f} had enough history to score per quarter — the universe GROWS "
        f"over the window, unlike the fixed {proxy.universe_size}-ETF proxy, so early periods are "
        f"thinner). {real.defensive_periods}/{real.total_periods} quarters went fully defensive "
        f"({real.forced_defensive_periods} of those FORCED by a price-coverage gap, not strategy "
        f"rules — investigate as data quality, not signal). No name was hand-picked.",
        # §2 — residual selection bias that PIT cannot remove.
        "residual selection bias: the real candidate universe is names liquid TODAY; "
        "reconstructing historical index membership/liquidity is out of scope, so treat any "
        "real-vs-proxy edge as an UPPER BOUND (optimistic), not a clean estimate.",
        # §3 — concentration vs data-source (parameter AND realized).
        f"concentration differs: proxy selects up to top_n={proxy.selection_top_n} diversified "
        f"ETFs (realized avg {proxy.avg_holdings:.1f} baskets) while real selects up to "
        f"top_n={real.selection_top_n} single names (realized avg {real.avg_holdings:.1f} "
        "stocks); attribute any return/risk difference to concentration AND data-source, never "
        "data-source alone. To isolate data-source, re-run with matched top_n.",
        # caliber — FX is shared, not a differentiator.
        "USD caliber: both backtests are in USD (real prices converted at as-of FX) and BOTH the "
        "signal and execution of each side run on one shared frame; the FX path is identical on "
        "both sides, so it is not a source of the difference.",
    )


def compare_results(
    proxy_result: HkChinaBacktestResult,
    real_result: RealHkChinaBacktestResult,
    *,
    starting_capital: float,
    n_signal_dates: int,
    proxy_defensive_asset: str,
    real_defensive_asset: str,
    proxy_top_n: int,
    real_top_n: int,
) -> ComparisonResult:
    """Build a bias-aware comparison from two already-run backtest results."""

    proxy = _summarize_proxy(
        proxy_result, defensive_asset=proxy_defensive_asset, top_n=proxy_top_n
    )
    real = _summarize_real(
        real_result, defensive_asset=real_defensive_asset, top_n=real_top_n
    )
    return ComparisonResult(
        proxy=proxy,
        real=real,
        starting_capital=starting_capital,
        n_signal_dates=n_signal_dates,
        usd_caliber=True,
        bias_notes=_bias_notes(proxy, real),
    )


def run_proxy_vs_real_comparison(
    *,
    proxy_usd_prices: pd.DataFrame,
    real_usd_prices: pd.DataFrame,
    signal_dates: tuple[date, ...],
    proxy_parameters: HkChinaMomentumParameters | None = None,
    real_parameters: HkChinaRealParameters | None = None,
    backtest_parameters: BacktestParameters | None = None,
) -> ComparisonResult:
    """Run BOTH backtests over the same signal dates / USD caliber / friction and
    return the bias-aware comparison.

    Both ``*_usd_prices`` are USD-converted long-format OHLCV frames (the proxy's
    ETF rows are already USD; the real frame comes from
    :func:`trade.data.hk_china_real_universe.to_usd_prices`). Each must cover its
    universe + the defensive asset. For fairness BOTH the signal and the execution
    of each side run on its one frame: the proxy signal is pinned via
    ``signal_prices`` rather than self-loading from disk. F004 supplies real VM
    data; tests supply deterministic synthetic frames."""

    if proxy_parameters is None:
        proxy_parameters = HkChinaMomentumParameters()
    if real_parameters is None:
        real_parameters = HkChinaRealParameters()
    if backtest_parameters is None:
        backtest_parameters = BacktestParameters()

    # Metrics annualize by sqrt(4); reject any cadence that would make that wrong.
    if (
        proxy_parameters.rebalance_frequency != "quarterly"
        or real_parameters.rebalance_frequency != "quarterly"
    ):
        raise BacktestError(
            "comparison metrics assume quarterly cadence (sqrt(4) annualization); "
            "both strategies must have rebalance_frequency='quarterly'"
        )

    proxy_records = usd_price_bars(proxy_usd_prices)
    proxy_result = run_hk_china_quarterly_backtest(
        proxy_records,
        signal_dates,
        proxy_parameters,
        backtest_parameters,
        signal_prices=proxy_usd_prices,
    )
    real_result = run_real_hk_china_quarterly_backtest(
        real_usd_prices,
        signal_dates,
        real_parameters,
        backtest_parameters,
    )
    return compare_results(
        proxy_result,
        real_result,
        starting_capital=backtest_parameters.starting_capital,
        n_signal_dates=len(signal_dates),
        proxy_defensive_asset=proxy_parameters.defensive_asset,
        real_defensive_asset=real_parameters.defensive_asset,
        proxy_top_n=proxy_parameters.top_n,
        real_top_n=real_parameters.top_n,
    )


def build_comparison_payload(result: ComparisonResult) -> dict[str, object]:
    """Serialize a :class:`ComparisonResult` to a plain dict for the F004 report.

    Includes both sides' metrics, the real−proxy deltas, and the honesty bias
    notes so the decision report can render attribution directly."""

    proxy_m = result.proxy.metrics
    real_m = result.real.metrics
    return {
        "usd_caliber": result.usd_caliber,
        "starting_capital": result.starting_capital,
        "n_signal_dates": result.n_signal_dates,
        "proxy": result.proxy.as_dict(),
        "real": result.real.as_dict(),
        "deltas_real_minus_proxy": {
            "cagr": real_m.cagr - proxy_m.cagr,
            "annualized_volatility": real_m.annualized_volatility
            - proxy_m.annualized_volatility,
            "sharpe": real_m.sharpe - proxy_m.sharpe,
            "max_drawdown": real_m.max_drawdown - proxy_m.max_drawdown,
            "turnover": real_m.turnover - proxy_m.turnover,
        },
        "bias_notes": list(result.bias_notes),
    }


__all__ = [
    "ComparisonMetrics",
    "ComparisonResult",
    "PROXY_TICKERS",
    "VersionSummary",
    "build_comparison_payload",
    "compare_results",
    "run_proxy_vs_real_comparison",
]
