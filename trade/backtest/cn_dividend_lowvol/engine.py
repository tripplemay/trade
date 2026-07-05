"""B082 F002 — single-asset monthly-rebalance backtest for the 红利低波 sleeve.

The dividend-lowvol sleeve holds ONE risky instrument (H20269 TR index in the primary
口径; the 512890 ETF in the implementability 口径) and cash, rebalancing MONTHLY to the
three-tier target weight (signal.py). This is far simpler than the cross-sectional CN
attack engine, so it carries its own small simulator rather than overloading that one.

Modelled honestly (B081 修真 discipline carried where it applies to a single ETF):
- **T+1 execution**: the target from month-end M's spread trades at the NEXT trading
  day's price (index layer: next close; ETF layer: next open when an ``open`` series is
  supplied). No look-ahead — the signal date's own bar is never traded on.
- **directional costs** (ETF 口径): commission 2.5bp + slippage 5bp on both sides,
  **no stamp duty** (ETF is exempt — the lone difference vs. the A-share equity model);
  ``CnCostModel(stamp_duty_bps=0)``.
- **100-share round lots** + a per-capital scan (10万 / 100万) — the B081 容量 lesson:
  at a small book, one lot of a ~1 CNY ETF is trivial, but the knob is on and reported.
- **management-fee drag** (~0.5%/yr) applied to the ETF holding as a daily NAV decay.
- **cash earns 0** (conservative): a real cash/short-bond leg would earn ≈ the 10Y,
  which would only HELP the defensive rule — so 0 biases AGAINST it, the honest choice.

All functions are pure (pandas/numpy) and unit-tested against hand-computed tiny series.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from trade.backtest.cn_attack_momentum_quality.costs import CnCostModel

TRADING_DAYS_PER_YEAR = 252
# Weight-change floor below which a "rebalance" is floating-point residual, not a real
# trade (a fully-invested single asset re-buys a ~0 sliver each month otherwise).
_WEIGHT_EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    """Summary metrics of a daily equity curve."""

    cagr: float
    sharpe: float
    max_drawdown: float
    total_return: float
    ending_value: float
    years: float


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """A single simulation run: daily equity + trade bookkeeping + metrics."""

    equity: pd.Series
    weights: pd.Series  # applied risky weight per day (post-rebalance)
    metrics: BacktestMetrics
    total_turnover: float  # one-way traded notional / initial capital
    n_rebalances: int  # execution dates that actually traded


def simulate_single_asset(
    prices: pd.Series,
    exec_targets: pd.Series,
    *,
    initial_capital: float = 1_000_000.0,
    cost_model: CnCostModel | None = None,
    lot_size: int | None = None,
    annual_fee: float = 0.0,
    min_rebalance_weight_delta: float = 0.0,
    exec_prices: pd.Series | None = None,
) -> BacktestResult:
    """Simulate the sleeve over ``prices`` with month-end ``exec_targets``.

    ``prices`` is the daily mark-to-market close of the risky asset (sorted, positive).
    ``exec_targets`` maps a SIGNAL date → target risky weight; each trades at the first
    price date strictly after it (T+1). ``exec_prices`` (optional, e.g. ETF opens) is
    used for the traded price at execution while ``prices`` still marks the book daily;
    omitted → execute at ``prices`` (index layer, no open/close split).

    ``cost_model`` None → frictionless (index 口径). ``lot_size`` None → fractional units.
    ``annual_fee`` decays the risky holding daily (management fee). Returns a
    :class:`BacktestResult`.
    """

    prices = _clean_prices(prices)
    if prices.empty:
        raise ValueError("prices series is empty")
    # Align the (optional) execution price series onto the mark index once, so a
    # per-day lookup is a plain, gap-free indexing (never a single-element ffill).
    if exec_prices is not None:
        exec_price_aligned = _clean_prices(exec_prices).reindex(prices.index).ffill().bfill()
    else:
        exec_price_aligned = prices
    exec_targets = exec_targets.sort_index()

    exec_map = _map_execution_dates(prices.index, exec_targets)
    fee_daily = _daily_fee(annual_fee)

    dates = list(prices.index)
    units = 0.0
    cash = float(initial_capital)
    equity_values: list[float] = []
    weight_values: list[float] = []
    total_traded = 0.0
    n_rebalances = 0

    for day in dates:
        price = float(prices.loc[day])
        # Management-fee NAV decay on the risky holding (before marking).
        if units > 0.0 and fee_daily > 0.0:
            units *= 1.0 - fee_daily
        portfolio_value = units * price + cash

        if day in exec_map:
            target_weight = exec_map[day]
            trade_price = float(exec_price_aligned.loc[day])
            if not math.isfinite(trade_price) or trade_price <= 0:
                trade_price = price
            desired_value = target_weight * portfolio_value
            desired_units = desired_value / trade_price
            if lot_size is not None and lot_size > 0:
                desired_units = _round_to_lot(desired_units, lot_size)
            delta_units = desired_units - units
            trade_notional = abs(delta_units) * trade_price
            current_weight = (units * trade_price) / portfolio_value \
                if portfolio_value > 0 else 0.0
            desired_weight_now = (desired_units * trade_price) / portfolio_value \
                if portfolio_value > 0 else 0.0
            # No-trade band: skip micro-adjustments (手数取整 noise below the band).
            # ``_WEIGHT_EPSILON`` also floors floating-point residual rebalances (a
            # 100%-invested single asset "re-buys" a ~0-notional sliver every month) so
            # they are neither executed nor counted — n_rebalances reflects REAL trades.
            weight_change = abs(desired_weight_now - current_weight)
            if weight_change >= max(min_rebalance_weight_delta, _WEIGHT_EPSILON) \
                    and trade_notional > 0:
                cost = 0.0
                if cost_model is not None:
                    buy_notional = trade_notional if delta_units > 0 else 0.0
                    sell_notional = trade_notional if delta_units < 0 else 0.0
                    cost = cost_model.trade_cost(buy_notional, sell_notional)
                units = desired_units
                cash = portfolio_value - units * price - cost
                total_traded += trade_notional
                n_rebalances += 1

        marked = units * price + cash
        equity_values.append(marked)
        weight_values.append((units * price) / marked if marked > 0 else 0.0)

    equity = pd.Series(equity_values, index=prices.index, name="equity")
    weights = pd.Series(weight_values, index=prices.index, name="weight")
    metrics = compute_metrics(equity)
    turnover = total_traded / initial_capital if initial_capital > 0 else 0.0
    return BacktestResult(
        equity=equity,
        weights=weights,
        metrics=metrics,
        total_turnover=turnover,
        n_rebalances=n_rebalances,
    )


def compute_metrics(equity: pd.Series) -> BacktestMetrics:
    """CAGR / annualised Sharpe (rf=0) / max drawdown from a daily equity curve."""

    equity = equity.dropna()
    if len(equity) < 2:
        ending = float(equity.iloc[-1]) if len(equity) else 0.0
        return BacktestMetrics(0.0, 0.0, 0.0, 0.0, ending, 0.0)
    start_value = float(equity.iloc[0])
    end_value = float(equity.iloc[-1])
    total_return = end_value / start_value - 1.0
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years > 0 and start_value > 0:
        cagr = (end_value / start_value) ** (1.0 / years) - 1.0
    else:
        cagr = 0.0
    daily = equity.pct_change().dropna()
    if len(daily) > 1 and daily.std() > 0:
        sharpe = float(daily.mean() / daily.std() * math.sqrt(TRADING_DAYS_PER_YEAR))
    else:
        sharpe = 0.0
    max_dd = _max_drawdown(equity)
    return BacktestMetrics(
        cagr=cagr,
        sharpe=sharpe,
        max_drawdown=max_dd,
        total_return=total_return,
        ending_value=end_value,
        years=years,
    )


def window_max_drawdown(
    equity: pd.Series, start: date, end: date
) -> float:
    """Max drawdown of ``equity`` restricted to ``[start, end]`` (rebased in-window).

    The peak is measured from within the window (a fresh cummax at ``start``), so it is
    the worst peak-to-trough loss an investor entering at ``start`` would have seen —
    the defensive-sleeve验收 metric (2022 full year / 2024-01~02 踩踏窗口).
    """

    window = equity[(equity.index >= pd.Timestamp(start)) & (equity.index <= pd.Timestamp(end))]
    return _max_drawdown(window)


def walk_forward_oos_metrics(
    result_equity: pd.Series, is_fraction: float = 0.70
) -> BacktestMetrics:
    """Metrics over the OOS tail (last ``1 - is_fraction`` of the calendar window).

    The equity curve is split by time at ``is_fraction`` of the day span; the OOS
    sub-curve is rebased to its own start so CAGR/Sharpe/DD describe the held-out
    period alone (WF 70/30, spec §0).
    """

    equity = result_equity.dropna()
    if len(equity) < 4:
        return compute_metrics(equity)
    span_days = (equity.index[-1] - equity.index[0]).days
    split_ts = equity.index[0] + pd.Timedelta(days=int(span_days * is_fraction))
    oos = equity[equity.index >= split_ts]
    if len(oos) < 2:
        return compute_metrics(equity)
    return compute_metrics(oos / float(oos.iloc[0]))


def cpcv_lite_fold_cagrs(
    equity: pd.Series, exec_targets: pd.Series, k: int = 4
) -> list[float]:
    """CPCV-lite: CAGR of each of ``k`` interleaved month blocks (非全 CPCV, 交错 split).

    The month-end rebalance points partition the timeline into contiguous monthly
    blocks; block ``i`` is assigned to fold ``i % k``. For each fold the daily returns
    of its blocks are geometrically chained and annualised. This probes robustness to
    WHICH interleaved subset of months you sample — it is NOT a fully combinatorial
    purged CV (no embargo / no train-side purge), and the report labels it as such.
    """

    equity = equity.dropna()
    daily = equity.pct_change().dropna()
    edges = [pd.Timestamp(d) for d in exec_targets.sort_index().index]
    if len(edges) < k + 1:
        return []
    fold_returns: list[list[float]] = [[] for _ in range(k)]
    for i in range(len(edges) - 1):
        block = daily[(daily.index > edges[i]) & (daily.index <= edges[i + 1])]
        fold_returns[i % k].extend(block.tolist())
    cagrs: list[float] = []
    for returns in fold_returns:
        if not returns:
            cagrs.append(0.0)
            continue
        growth = float(np.prod([1.0 + r for r in returns]))
        n_years = len(returns) / TRADING_DAYS_PER_YEAR
        cagrs.append(growth ** (1.0 / n_years) - 1.0 if n_years > 0 and growth > 0 else 0.0)
    return cagrs


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _clean_prices(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    numeric = numeric[numeric > 0]
    numeric = numeric[~numeric.index.duplicated(keep="last")]
    return numeric.sort_index()


def _map_execution_dates(
    price_index: pd.Index, exec_targets: pd.Series
) -> dict[pd.Timestamp, float]:
    """Signal date → first price date strictly after it (T+1), carrying the target."""

    exec_map: dict[pd.Timestamp, float] = {}
    price_ts = list(price_index)
    for signal_date, target in exec_targets.items():
        ts = pd.Timestamp(signal_date)
        pos = np.searchsorted([t.value for t in price_ts], ts.value, side="right")
        if pos < len(price_ts):
            exec_map[price_ts[pos]] = float(target)
    return exec_map


def _round_to_lot(units: float, lot_size: int) -> float:
    """Round DOWN to a whole lot (never over-invest past available notional)."""

    return math.floor(units / lot_size) * lot_size


def _daily_fee(annual_fee: float) -> float:
    if annual_fee <= 0.0:
        return 0.0
    return float(1.0 - (1.0 - annual_fee) ** (1.0 / TRADING_DAYS_PER_YEAR))


def _max_drawdown(equity: pd.Series) -> float:
    equity = equity.dropna()
    if len(equity) < 2:
        return 0.0
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    return float(drawdown.min())


__all__ = [
    "BacktestMetrics",
    "BacktestResult",
    "TRADING_DAYS_PER_YEAR",
    "compute_metrics",
    "cpcv_lite_fold_cagrs",
    "simulate_single_asset",
    "walk_forward_oos_metrics",
    "window_max_drawdown",
]
