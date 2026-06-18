"""B066 F002 — daily-monitor / no-trade-band backtest engine for the CN attack strategy.

Simulates the spec's "每日监控 + 不动区" cadence: every trading day the target is
recomputed (``generate_cn_attack_signal``), but the portfolio only rebalances when
the would-be turnover exceeds a band — so most days hold and the realised turnover
/ cost emerge honestly from the loop. Three exit variants overlay the band:

- ``momentum_decay`` (base) — a held name leaves only when enough names drop out of
  the top-N target to push the would-be turnover past the band (the rank buffer is
  the band itself; winners run);
- ``trailing_stop`` — additionally sell a held name down > X% from its post-entry
  peak;
- ``hard_profit_target`` — additionally sell a held name up > X% from entry.

Execution is **T+1 open** (decisions at day ``d``'s close execute at ``d+1``'s
open — A-shares settle T+1), with daily close mark-to-market for a daily equity
curve. Costs are directional (:class:`~trade.backtest.cn_attack_momentum_quality.costs.CnCostModel`)
— stamp duty on sells only. Performance metrics reuse the shared US metrics module.

Pure pandas / numpy; no US-engine import (US zero-regression).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from trade.backtest.cn_attack_momentum_quality.costs import CnCostModel
from trade.backtest.us_quality_momentum.metrics import (
    PerformanceMetrics,
    compute_performance_metrics,
)
from trade.data.cn_attack_universe import load_cn_universe_history, resolve_pit_members
from trade.data.us_quality_universe import load_fundamentals, load_prices
from trade.strategies.cn_attack_momentum_quality.parameters import CnAttackParameters
from trade.strategies.cn_attack_momentum_quality.signal import generate_cn_attack_signal

DEFAULT_STARTING_CAPITAL = 100_000.0
DEFAULT_NO_TRADE_BAND = 0.20  # L1 would-be turnover (sum|Δw|) that triggers a rebalance
DEFAULT_TRAILING_STOP_PCT = 0.20
DEFAULT_PROFIT_TARGET_PCT = 0.30
DEFAULT_WARMUP_MONTHS = 14  # 12-1 momentum needs ~13 months of history

EXIT_MOMENTUM_DECAY = "momentum_decay"
EXIT_TRAILING_STOP = "trailing_stop"
EXIT_HARD_PROFIT_TARGET = "hard_profit_target"
EXIT_VARIANTS: frozenset[str] = frozenset(
    {EXIT_MOMENTUM_DECAY, EXIT_TRAILING_STOP, EXIT_HARD_PROFIT_TARGET}
)


class CnBacktestError(ValueError):
    """Raised when CN backtest inputs are inconsistent."""


@dataclass(frozen=True, slots=True)
class CnAttackBacktestConfig:
    """Top-level backtest controls — separate from the strategy factor parameters."""

    starting_capital: float = DEFAULT_STARTING_CAPITAL
    cost_model: CnCostModel = field(default_factory=CnCostModel)
    no_trade_band: float = DEFAULT_NO_TRADE_BAND
    exit_variant: str = EXIT_MOMENTUM_DECAY
    trailing_stop_pct: float = DEFAULT_TRAILING_STOP_PCT
    profit_target_pct: float = DEFAULT_PROFIT_TARGET_PCT

    def __post_init__(self) -> None:
        if self.starting_capital <= 0:
            raise CnBacktestError("starting_capital must be positive")
        # sum|target_w - current_w| maxes out near 2.0 (fully-disjoint books), so a
        # band >= 2.0 silently disables all rebalancing — reject it up front.
        if not 0.0 <= self.no_trade_band < 2.0:
            raise CnBacktestError("no_trade_band must be in [0, 2)")
        if self.exit_variant not in EXIT_VARIANTS:
            raise CnBacktestError(
                f"exit_variant must be one of {sorted(EXIT_VARIANTS)}; "
                f"got {self.exit_variant!r}"
            )
        # Validate BOTH exit thresholds unconditionally so a typo on the inactive
        # variant fails fast rather than lurking until that variant is selected.
        if not 0.0 < self.trailing_stop_pct < 1.0:
            raise CnBacktestError("trailing_stop_pct must be in (0, 1)")
        if self.profit_target_pct <= 0.0:
            raise CnBacktestError("profit_target_pct must be > 0")


@dataclass(frozen=True, slots=True)
class CnAttackDailyRecord:
    """One trading day's decision + realised execution (no-trade-band observability)."""

    date: date
    equity: float
    target_tickers: tuple[str, ...]
    rebalanced: bool  # a rebalance was DECIDED at this close (executes next open)
    forced_exits: tuple[str, ...]  # exit-rule sells decided at this close
    executed_turnover: float  # turnover EXECUTED at this day's open (prior decision)
    executed_cost: float  # cost EXECUTED at this day's open


@dataclass(frozen=True, slots=True)
class CnAttackBacktestResult:
    """Container for CN attack backtest outputs consumed by the F003 report."""

    parameters: CnAttackParameters
    config: CnAttackBacktestConfig
    starting_capital: float
    ending_value: float
    equity_curve: pd.DataFrame  # columns: date, equity
    daily_returns: pd.Series
    total_turnover: float
    total_cost: float
    rebalance_count: int  # days a band-driven rebalance was decided
    exit_count: int  # days ANY exit rule fired (a day-count, not a per-position count)
    trading_days: int
    metrics: PerformanceMetrics
    daily_records: tuple[CnAttackDailyRecord, ...]


# --------------------------------------------------------------------------- #
# Pending action (decided at close[d], executed at open[d+1])
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _Pending:
    """A T+1 instruction: either a full rebalance to ``target`` or a set of exits."""

    kind: str  # "rebalance" | "exit"
    target: dict[str, float] = field(default_factory=dict)  # rebalance target weights
    exits: frozenset[str] = field(default_factory=frozenset)  # names to sell to cash


def _wide(prices: pd.DataFrame, value_col: str) -> pd.DataFrame:
    # Forward-fill so a name halted (停牌) for a day — a NaN in the pivot — carries
    # its last-known price rather than poisoning valuation/execution with NaN. This
    # is the standard research-backtest halt treatment: a halted holding keeps its
    # value (no leak) and is, as a P1 simplification, rebalanced at its last price.
    # Leading NaN (a name not yet listed) stays NaN → _price() reads it as 0.
    return (
        prices.pivot_table(index="date", columns="ticker", values=value_col, aggfunc="last")
        .sort_index()
        .ffill()
    )


def _price(row: pd.Series, ticker: str) -> float:
    """One ticker's price from a wide row — NaN-safe. Returns 0.0 for no usable price.

    NaN is truthy in Python, so the ``value or 0.0`` idiom would NOT coerce a NaN
    close/open to 0 and would poison every downstream sum; this guards explicitly.
    """

    value = row.get(ticker)
    if value is None or pd.isna(value) or value <= 0:
        return 0.0
    return float(value)


def _mark_to_market(shares: Mapping[str, float], close_row: pd.Series) -> float:
    return float(sum(qty * _price(close_row, ticker) for ticker, qty in shares.items()))


def _current_weights(
    shares: Mapping[str, float], close_row: pd.Series, equity: float
) -> dict[str, float]:
    if equity <= 0:
        return {}
    return {
        ticker: (qty * _price(close_row, ticker)) / equity
        for ticker, qty in shares.items()
        if qty > 0
    }


def _forced_exits(
    config: CnAttackBacktestConfig,
    shares: Mapping[str, float],
    close_row: pd.Series,
    entry_price: Mapping[str, float],
    peak_price: Mapping[str, float],
) -> frozenset[str]:
    """Exit-variant sells at ``close``. momentum_decay adds none (band handles it)."""

    held = [ticker for ticker, qty in shares.items() if qty > 0]
    if config.exit_variant == EXIT_TRAILING_STOP:
        stop = 1.0 - config.trailing_stop_pct
        return frozenset(
            ticker
            for ticker in held
            if (close := float(close_row.get(ticker, 0.0) or 0.0)) > 0
            and ticker in peak_price
            and close <= peak_price[ticker] * stop
        )
    if config.exit_variant == EXIT_HARD_PROFIT_TARGET:
        gain = 1.0 + config.profit_target_pct
        return frozenset(
            ticker
            for ticker in held
            if (close := float(close_row.get(ticker, 0.0) or 0.0)) > 0
            and ticker in entry_price
            and entry_price[ticker] > 0
            and close >= entry_price[ticker] * gain
        )
    return frozenset()


def _would_be_turnover(
    current_weights: Mapping[str, float], target: Mapping[str, float]
) -> float:
    names = set(current_weights) | set(target)
    return sum(
        abs(target.get(ticker, 0.0) - current_weights.get(ticker, 0.0)) for ticker in names
    )


def _execute_open(
    shares: dict[str, float],
    cash: float,
    open_row: pd.Series,
    pending: _Pending,
    cost_model: CnCostModel,
    entry_price: dict[str, float],
    peak_price: dict[str, float],
) -> tuple[dict[str, float], float, float, float]:
    """Apply a pending T+1 instruction at the open. Returns (shares, cash, turnover, cost).

    Trades are computed as notional deltas vs the current open-valued holdings, so a
    position already at its target incurs no trade / no cost. Costs are directional.
    """

    def price(ticker: str) -> float:
        return _price(open_row, ticker)

    current_notional = {
        ticker: qty * price(ticker) for ticker, qty in shares.items() if qty > 0
    }
    equity_open = cash + sum(current_notional.values())
    if equity_open <= 0:
        return shares, cash, 0.0, 0.0

    new_shares: dict[str, float] = {}
    if pending.kind == "rebalance":
        # Full rebalance: re-target every name. Cost is reserved out of equity so the
        # book invests (equity - cost); cash never goes negative. Cost is computed on
        # the pre-reserve deltas (the ~cost^2 difference is immaterial).
        priced_target = {
            ticker: weight for ticker, weight in pending.target.items() if price(ticker) > 0
        }
        desired = {ticker: equity_open * weight for ticker, weight in priced_target.items()}
        names = set(current_notional) | set(desired)
        buy_notional = sum(
            max(0.0, desired.get(t, 0.0) - current_notional.get(t, 0.0)) for t in names
        )
        sell_notional = sum(
            max(0.0, current_notional.get(t, 0.0) - desired.get(t, 0.0)) for t in names
        )
        cost = cost_model.trade_cost(buy_notional, sell_notional)
        investable = max(0.0, equity_open - cost)
        invested_fraction = sum(priced_target.values())
        for ticker, weight in priced_target.items():
            if weight > 0:
                new_shares[ticker] = investable * weight / price(ticker)
        new_cash = investable * max(0.0, 1.0 - invested_fraction)
        # Defensive invariant (belt-and-suspenders to the ffill in _wide): never let
        # a held name silently vanish. One unpriced even after forward-fill (a
        # never-listed edge) cannot be sold this open, so carry its shares forward.
        for ticker, qty in shares.items():
            if qty > 0 and ticker not in new_shares and price(ticker) <= 0:
                new_shares[ticker] = qty
    else:
        # Exit-only: sell the exited names to cash, keep the rest UNCHANGED (the cost
        # comes from the sale proceeds, not from trimming held positions).
        sell_notional = sum(
            notional for ticker, notional in current_notional.items() if ticker in pending.exits
        )
        buy_notional = 0.0
        cost = cost_model.trade_cost(buy_notional, sell_notional)
        for ticker, qty in shares.items():
            if qty > 0 and ticker not in pending.exits:
                new_shares[ticker] = qty
        new_cash = cash + sell_notional - cost

    turnover = (buy_notional + sell_notional) / equity_open

    # Maintain entry / peak: new positions stamp entry=peak=open; closed positions
    # are forgotten; existing positions keep their original entry (conservative).
    for ticker in list(entry_price):
        if ticker not in new_shares:
            entry_price.pop(ticker, None)
            peak_price.pop(ticker, None)
    for ticker in new_shares:
        if ticker not in entry_price:
            entry_price[ticker] = price(ticker)
            peak_price[ticker] = price(ticker)

    return new_shares, new_cash, turnover, cost


def _default_window(prices: pd.DataFrame) -> tuple[date, date]:
    first = pd.Timestamp(prices["date"].min())
    last = pd.Timestamp(prices["date"].max())
    start = (first + pd.DateOffset(months=DEFAULT_WARMUP_MONTHS)).date()
    return start, last.date()


def run_cn_attack_backtest(
    parameters: CnAttackParameters,
    config: CnAttackBacktestConfig | None = None,
    start: date | None = None,
    end: date | None = None,
    *,
    prices: pd.DataFrame | None = None,
    fundamentals: pd.DataFrame | None = None,
    universe_history: Mapping[date, tuple[str, ...]] | None = None,
) -> CnAttackBacktestResult:
    """Run the daily-monitor / no-trade-band backtest over ``[start, end]``.

    ``prices`` / ``fundamentals`` / ``universe_history`` default to disk loads
    (the unified CSVs + cn_pit_universe.csv); the daily loop resolves point-in-time
    membership in memory. Decisions at each close execute at the next open (T+1).
    """

    if config is None:
        config = CnAttackBacktestConfig()
    if prices is None:
        prices = load_prices()
    if prices.empty:
        raise CnBacktestError("prices frame is empty")
    needs_quality = "quality" in parameters.factor_weight_mapping()
    if needs_quality and fundamentals is None:
        fundamentals = load_fundamentals()
    if universe_history is None:
        universe_history = load_cn_universe_history()

    wide_close = _wide(prices, "adj_close")
    wide_open = _wide(prices, "open")
    trading_dates = [ts.date() for ts in wide_close.index]

    if start is None or end is None:
        default_start, default_end = _default_window(prices)
        start = start or default_start
        end = end or default_end
    window = [day for day in trading_dates if start <= day <= end]
    if len(window) < 2:
        raise CnBacktestError(f"need >= 2 trading days inside [{start}, {end}]")

    shares: dict[str, float] = {}
    cash = config.starting_capital
    entry_price: dict[str, float] = {}
    peak_price: dict[str, float] = {}
    pending: _Pending | None = None

    equity_rows: list[dict[str, object]] = []
    records: list[CnAttackDailyRecord] = []
    total_turnover = 0.0
    total_cost = 0.0
    rebalance_count = 0
    exit_count = 0

    for index, day in enumerate(window):
        ts = pd.Timestamp(day)
        open_row = wide_open.loc[ts]
        close_row = wide_close.loc[ts]

        executed_turnover = 0.0
        executed_cost = 0.0
        if pending is not None:
            shares, cash, executed_turnover, executed_cost = _execute_open(
                shares, cash, open_row, pending, config.cost_model, entry_price, peak_price
            )
            total_turnover += executed_turnover
            total_cost += executed_cost
            pending = None

        # Daily close mark-to-market + peak update.
        for ticker in list(peak_price):
            close = float(close_row.get(ticker, 0.0) or 0.0)
            if close > 0:
                peak_price[ticker] = max(peak_price[ticker], close)
        equity = cash + _mark_to_market(shares, close_row)
        equity_rows.append({"date": ts, "equity": equity})

        # Decide at this close → pending for next open (skip on the last day).
        target_tickers: tuple[str, ...] = ()
        rebalanced = False
        forced_exits: frozenset[str] = frozenset()
        if index < len(window) - 1:
            members = resolve_pit_members(universe_history, day)
            if members:
                signal = generate_cn_attack_signal(
                    parameters,
                    day,
                    prices=prices,
                    fundamentals=fundamentals,
                    universe_members=members,
                )
                forced_exits = _forced_exits(
                    config, shares, close_row, entry_price, peak_price
                )
                # An exit rule firing is counted independently of how the trade is
                # realised: when many names exit at once the target shrinks enough
                # that the band rebalance executes the sells, but the exit rule
                # still fired (so it must count toward exit_count, not be masked).
                if forced_exits:
                    exit_count += 1
                target = {
                    ticker: weight
                    for ticker, weight in signal.weights_dict().items()
                    if ticker not in forced_exits
                }
                target_tickers = tuple(sorted(target))
                # Band gate uses close[d]-valued current weights vs the close[d]
                # target; the realised turnover is re-priced at open[d+1] on
                # execution (T+1). The close-vs-open basis is by design, not a leak.
                current_w = _current_weights(shares, close_row, equity)
                if _would_be_turnover(current_w, target) > config.no_trade_band:
                    pending = _Pending(kind="rebalance", target=target)
                    rebalanced = True
                    rebalance_count += 1
                elif forced_exits:
                    pending = _Pending(kind="exit", exits=forced_exits)

        records.append(
            CnAttackDailyRecord(
                date=day,
                equity=equity,
                target_tickers=target_tickers,
                rebalanced=rebalanced,
                forced_exits=tuple(sorted(forced_exits)),
                executed_turnover=executed_turnover,
                executed_cost=executed_cost,
            )
        )

    equity_curve = pd.DataFrame(equity_rows)
    daily_returns = equity_curve.set_index("date")["equity"].pct_change().dropna()
    ending_value = float(equity_curve["equity"].iloc[-1])
    metrics = compute_performance_metrics(equity_curve, daily_returns, total_turnover)

    return CnAttackBacktestResult(
        parameters=parameters,
        config=config,
        starting_capital=config.starting_capital,
        ending_value=ending_value,
        equity_curve=equity_curve,
        daily_returns=daily_returns,
        total_turnover=total_turnover,
        total_cost=total_cost,
        rebalance_count=rebalance_count,
        exit_count=exit_count,
        trading_days=len(window),
        metrics=metrics,
        daily_records=tuple(records),
    )


__all__ = [
    "EXIT_HARD_PROFIT_TARGET",
    "EXIT_MOMENTUM_DECAY",
    "EXIT_TRAILING_STOP",
    "EXIT_VARIANTS",
    "CnAttackBacktestConfig",
    "CnAttackBacktestResult",
    "CnAttackDailyRecord",
    "CnBacktestError",
    "run_cn_attack_backtest",
]
