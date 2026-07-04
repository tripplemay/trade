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

import math
from collections.abc import Callable, Mapping
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
from trade.strategies.cn_attack_momentum_quality.parameters import (
    SIZE_FACTOR_KEY,
    CnAttackParameters,
)
from trade.strategies.cn_attack_momentum_quality.signal import generate_cn_attack_signal
from trade.strategies.cn_attack_momentum_quality.size import DATE_COLUMN as _MCAP_DATE_COLUMN

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
    # B081 F001(2) — A-share round-lot (100 股/手) realism: buy quantities are floored
    # to whole lots, the rounding remainder returns to cash, and a name whose target
    # cannot afford even one lot is skipped (its notional stays cash). Default True
    # (the honest/更保守口径); set False to bit-level reproduce the pre-B081 engine.
    lot_rounding: bool = True
    # B081 F001(3) — band partial rebalance (user-adjudicated Option A): the aggregate
    # no_trade_band is BYPASSED; the per-name threshold is the sole churn filter. A
    # rebalance fires whenever a name is entering/exiting or drifts more than
    # per_name_rebalance_threshold from its open weight — and ONLY those names trade
    # (every other held name keeps its exact shares). Default True; False bit-level
    # reproduces the pre-B081 full-band engine.
    partial_rebalance: bool = True
    per_name_rebalance_threshold: float = 0.005  # 0.5% |Δw|
    # B081 F002 — 停牌/退市 realism (修复 #1, the heaviest overestimation source).
    # suspension_halt: a held name with NO real bar on the execution day is halted — it
    # is frozen (exact shares kept, no buy, no sell, its target deferred), and the OTHER
    # names rebalance within the remaining tradeable pool (you can't sell a halted name
    # to fund others — realistic). delist_liquidation: a name with no real bar for
    # delist_confirm_days (past its final bar) is force-liquidated at close ×
    # delist_recovery_rate. Both default True (更保守/honest); False bit-level reproduces
    # the pre-B081 ffill口径 (which lets halted/delisted names trade at stale prices).
    suspension_halt: bool = True
    delist_liquidation: bool = True
    delist_recovery_rate: float = 1.0  # liquidation haircut; 0.5 sensitivity per spec
    delist_confirm_days: int = 10
    # B081 F003 — 涨跌停 executability (修复 #2): a name whose OPEN is at its price limit
    # vs the prior close (板幅 20% for 300xxx/688xxx, else 10%) can't trade in the locked
    # direction — 涨停 禁买, 跌停 禁卖 (放弃留现金). Detected purely from open-vs-prev-close
    # (no new data). Restricted like a halt this day (frozen if held, excluded from the
    # target), re-evaluated next rebalance. Default True (更保守); False bit-level
    # reproduces the pre-B081口径 (trades through the limit at the open price).
    price_limit_gating: bool = True

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
        if self.per_name_rebalance_threshold < 0.0:
            raise CnBacktestError("per_name_rebalance_threshold must be >= 0")
        if not 0.0 <= self.delist_recovery_rate <= 1.0:
            raise CnBacktestError("delist_recovery_rate must be in [0, 1]")
        if self.delist_confirm_days < 1:
            raise CnBacktestError("delist_confirm_days must be >= 1")
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
class CnAttackHoldings:
    """The portfolio actually HELD at the backtest's final day, close-valued.

    B067 F001 — the live advisory producer needs the band-managed book the
    strategy *currently holds* (not a fresh signal): in a no-trade-band strategy
    the held book IS the recommendation on a hold day. ``weights`` are the
    invested names' market-value weights at the last day's close; ``cash_weight``
    is the residual cash fraction. ``sum(weights) + cash_weight == 1.0`` (a value
    decomposition of equity), so appending a cash row yields a fully-allocated
    snapshot that passes the ``save_batch`` weight-sum guard.
    """

    weights: tuple[tuple[str, float], ...]
    cash_weight: float

    def as_dict(self) -> dict[str, float]:
        return dict(self.weights)


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
    # B067 F001 — the held book at the final day's close (for the live advisory
    # producer). Default empty so existing constructors / pickles stay valid.
    final_holdings: CnAttackHoldings = CnAttackHoldings(weights=(), cash_weight=1.0)


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


def _limit_hit_names(open_row: pd.Series, prev_close_row: pd.Series) -> frozenset[str]:
    """B081 F003 — names locked at their price limit at THIS open (vs the prior close):
    open >= +band (涨停) or <= -band (跌停). Band is 20% for 创业板/科创板 (300xxx /
    688xxx) else 10%. Pure price inference — no new data. Both directions are returned
    (the caller restricts the locked name from trading in the direction it can't)."""

    hit: set[str] = set()
    for ticker in open_row.index:
        o = _price(open_row, str(ticker))
        pc = _price(prev_close_row, str(ticker))
        if o <= 0 or pc <= 0:
            continue
        band = 0.20 if str(ticker).startswith(("300", "688")) else 0.10
        ratio = o / pc - 1.0
        if ratio >= band - 1e-9 or ratio <= -band + 1e-9:
            hit.add(str(ticker))
    return frozenset(hit)


def _real_bar_mask(prices: pd.DataFrame) -> pd.DataFrame:
    """B081 F002 — which (date, ticker) had a REAL bar (True) vs would be an ffill
    carry (False). The pre-``_wide``-ffill pivot's ``notna`` — this is what separates
    a genuine trading day from a halted / delisted stale mark."""

    return (
        prices.pivot_table(index="date", columns="ticker", values="adj_close", aggfunc="last")
        .sort_index()
        .notna()
    )


def _delist_confirmations(
    prices: pd.DataFrame, trading_dates: list[date], confirm_days: int
) -> dict[date, set[str]]:
    """B081 F002 — the delist-confirmation date for each name: ``confirm_days`` trading
    days after its FINAL real bar (a name with no bar for that long, and never
    recovering, is treated as delisted). Returns {date: names to force-liquidate that
    day}. A name still trading near the data end never confirms (its window runs off
    the end) → not delisted."""

    real = _real_bar_mask(prices)
    date_pos = {d: i for i, d in enumerate(trading_dates)}
    out: dict[date, set[str]] = {}
    for name in real.columns:
        col = real[name]
        positions = [date_pos[ts.date()] for ts, v in col.items() if v and ts.date() in date_pos]
        if not positions:
            continue
        confirm_pos = max(positions) + confirm_days
        if confirm_pos < len(trading_dates):
            out.setdefault(trading_dates[confirm_pos], set()).add(name)
    return out


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


def _partial_would_be_turnover(
    current_weights: Mapping[str, float], target: Mapping[str, float], threshold: float
) -> float:
    """B081 F001(3) — the turnover a PARTIAL rebalance would actually execute: only
    names entering/exiting or drifting > ``threshold`` count. Option A gates the
    rebalance on this being > 0 (any significant name), bypassing the aggregate band."""

    total = 0.0
    for name in set(current_weights) | set(target):
        tw = target.get(name, 0.0)
        cw = current_weights.get(name, 0.0)
        entering = tw > 0 and cw == 0.0
        exiting = tw == 0.0 and cw > 0
        if entering or exiting or abs(tw - cw) > threshold:
            total += abs(tw - cw)
    return total


def _partial_rebalance_open(
    shares: Mapping[str, float],
    current_notional: Mapping[str, float],
    equity_open: float,
    priced_target: Mapping[str, float],
    price: Callable[[str], float],
    cost_model: CnCostModel,
    threshold: float,
    lot_rounding: bool,
) -> tuple[dict[str, float], float, float, float, float]:
    """B081 F001(3) — shares-preserving partial rebalance at the OPEN.

    Classifies each name by its weight vs the EXECUTION-open weight (not the close
    decision, which would churn on the overnight drift): a name entering, exiting, or
    drifting more than ``threshold`` trades to its signal weight; every other held
    name KEEPS ITS EXACT CURRENT SHARES (no re-target → no trade, no cost-reserve
    shrink). Cost is charged only on the traded buys + the exiting/trim sells; cash
    reconciles so equity is conserved. Returns (new_shares, cash, buy, sell, cost)."""

    current_open_w = {t: n / equity_open for t, n in current_notional.items()}
    kept: dict[str, float] = {}
    traded_w: dict[str, float] = {}
    for name in set(priced_target) | set(current_notional):
        tw = priced_target.get(name, 0.0)
        cw = current_open_w.get(name, 0.0)
        held = name in current_notional
        trade = (tw > 0 and not held) or (tw == 0.0 and held) or abs(tw - cw) > threshold
        if trade:
            if tw > 0:  # exiting (tw==0) is simply omitted → sold below
                traded_w[name] = tw
        elif held:
            kept[name] = shares[name]  # preserve exact shares → no trade

    traded_desired = {t: equity_open * w for t, w in traded_w.items()}
    buy = sum(max(0.0, traded_desired[t] - current_notional.get(t, 0.0)) for t in traded_w)
    exiting = [n for n in current_notional if n not in kept and n not in traded_w]
    sell = sum(current_notional[n] for n in exiting) + sum(
        max(0.0, current_notional.get(t, 0.0) - traded_desired[t]) for t in traded_w
    )
    cost = cost_model.trade_cost(buy, sell)

    new_shares: dict[str, float] = dict(kept)
    for t, target_notional in traded_desired.items():
        if lot_rounding:
            lots = math.floor(target_notional / price(t) / 100.0) * 100.0
            if lots >= 100.0:
                new_shares[t] = lots
        else:
            new_shares[t] = target_notional / price(t)
    new_cash = max(
        0.0, equity_open - cost - sum(q * price(t) for t, q in new_shares.items())
    )
    return new_shares, new_cash, buy, sell, cost


def _execute_open(
    shares: dict[str, float],
    cash: float,
    open_row: pd.Series,
    pending: _Pending,
    cost_model: CnCostModel,
    entry_price: dict[str, float],
    peak_price: dict[str, float],
    lot_rounding: bool = False,
    partial_rebalance: bool = False,
    per_name_threshold: float = 0.0,
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
        priced_target = {
            ticker: weight for ticker, weight in pending.target.items() if price(ticker) > 0
        }
        if partial_rebalance:
            (
                new_shares, new_cash, buy_notional, sell_notional, cost
            ) = _partial_rebalance_open(
                shares, current_notional, equity_open, priced_target, price,
                cost_model, per_name_threshold, lot_rounding,
            )
        else:
            # Full rebalance: re-target every name. Cost is reserved out of equity so
            # the book invests (equity - cost); cash never goes negative. Cost is on
            # the pre-reserve deltas (the ~cost^2 difference is immaterial).
            desired = {t: equity_open * w for t, w in priced_target.items()}
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
            if lot_rounding:
                # Floor each buy to whole 100-share lots; the rounding remainder (and
                # any name too small for one lot) stays in cash. 余额守恒: invested +
                # cash == investable, so equity is conserved as in the else branch.
                invested = 0.0
                for ticker, weight in priced_target.items():
                    if weight > 0:
                        lots = (
                            math.floor(investable * weight / price(ticker) / 100.0) * 100.0
                        )
                        if lots >= 100.0:
                            new_shares[ticker] = lots
                            invested += lots * price(ticker)
                new_cash = investable - invested
            else:
                # Pre-B081 path — fractional shares. Byte-identical for old口径.
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
    marketcap: pd.DataFrame | None = None,
    universe_history: Mapping[date, tuple[str, ...]] | None = None,
) -> CnAttackBacktestResult:
    """Run the daily-monitor / no-trade-band backtest over ``[start, end]``.

    ``prices`` / ``fundamentals`` / ``marketcap`` / ``universe_history`` default to disk
    loads (the unified CSVs + cn_pit_universe.csv); the daily loop resolves
    point-in-time membership in memory. Decisions at each close execute at the next
    open (T+1). ``marketcap`` (B076 F001) is required only when ``size_tilt_weight > 0``
    activates the size factor; the daily signal reads its latest PIT cap per name.
    """

    if config is None:
        config = CnAttackBacktestConfig()
    if prices is None:
        prices = load_prices()
    if prices.empty:
        raise CnBacktestError("prices frame is empty")
    weight_mapping = parameters.factor_weight_mapping()
    needs_quality = "quality" in weight_mapping
    if needs_quality and fundamentals is None:
        fundamentals = load_fundamentals()
    # Size factor (size_tilt_weight > 0): the market-cap frame must be injected — there
    # is no production disk loader yet (F002, GO-gated). Fail fast at entry rather than
    # raise per-day deep in the loop. Pre-convert the date column once so the per-day
    # PIT lookup does not re-parse date strings on every trading day.
    if SIZE_FACTOR_KEY in weight_mapping:
        if marketcap is None or marketcap.empty:
            raise CnBacktestError(
                "size_tilt_weight > 0 requires a non-empty marketcap frame "
                "(inject `marketcap=`)"
            )
        marketcap = marketcap.copy()
        marketcap[_MCAP_DATE_COLUMN] = pd.to_datetime(marketcap[_MCAP_DATE_COLUMN])
    if universe_history is None:
        universe_history = load_cn_universe_history()

    wide_close = _wide(prices, "adj_close")
    wide_open = _wide(prices, "open")
    trading_dates = [ts.date() for ts in wide_close.index]
    delist_confirmations = (
        _delist_confirmations(prices, trading_dates, config.delist_confirm_days)
        if config.delist_liquidation
        else {}
    )
    real_bar = _real_bar_mask(prices) if config.suspension_halt else None

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
    prev_close_row: pd.Series | None = None  # B081 F003 — for 涨跌停 open-vs-prev-close

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
            # B081 F002 — 停牌: names with NO real bar at this open are halted. Freeze
            # held halted names (exact shares + entry/peak set aside) and drop them from
            # the target so _execute_open can neither buy nor sell them; the non-halted
            # book rebalances within the remaining tradeable pool, then halted names are
            # restored. suspension_halt=False → real_bar is None → old ffill口径.
            # B081 F002 halt (no real bar) ∪ F003 涨跌停 (open locked at limit): both
            # restrict a name from trading at this open, re-evaluated next rebalance.
            restricted_today: frozenset[str] = frozenset()
            if real_bar is not None:
                row = real_bar.loc[ts]
                restricted_today |= frozenset(str(t) for t in row.index if not bool(row[t]))
            if config.price_limit_gating and prev_close_row is not None:
                restricted_today |= _limit_hit_names(open_row, prev_close_row)
            frozen_shares: dict[str, float] = {}
            frozen_entry: dict[str, float] = {}
            frozen_peak: dict[str, float] = {}
            exec_pending = pending
            if restricted_today:
                for t in [n for n in shares if n in restricted_today and shares[n] > 0]:
                    frozen_shares[t] = shares.pop(t)
                    if t in entry_price:
                        frozen_entry[t] = entry_price.pop(t)
                    if t in peak_price:
                        frozen_peak[t] = peak_price.pop(t)
                exec_pending = _Pending(
                    kind=pending.kind,
                    target={k: v for k, v in pending.target.items() if k not in restricted_today},
                    exits=frozenset(e for e in pending.exits if e not in restricted_today),
                )
            shares, cash, executed_turnover, executed_cost = _execute_open(
                shares, cash, open_row, exec_pending, config.cost_model, entry_price,
                peak_price, config.lot_rounding, config.partial_rebalance,
                config.per_name_rebalance_threshold,
            )
            shares.update(frozen_shares)  # restore frozen halted names (untraded)
            entry_price.update(frozen_entry)
            peak_price.update(frozen_peak)
            total_turnover += executed_turnover
            total_cost += executed_cost
            pending = None

        # B081 F002 — force-liquidate any name confirmed delisted today at
        # close × recovery_rate (else the ffill would keep marking it forever at its
        # stale last price — the overestimation this fixes). Charges the sell cost.
        delist_today = delist_confirmations.get(day)
        if delist_today:
            equity_before = cash + _mark_to_market(shares, close_row)
            for name in [n for n in shares if n in delist_today]:
                gross = shares[name] * _price(close_row, name)
                proceeds = gross * config.delist_recovery_rate
                liq_cost = config.cost_model.trade_cost(0.0, proceeds)
                cash += proceeds - liq_cost
                total_cost += liq_cost
                if equity_before > 0:
                    total_turnover += gross / equity_before
                del shares[name]
                entry_price.pop(name, None)
                peak_price.pop(name, None)

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
                    marketcap=marketcap,
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
                # B081 F001(3) Option A — partial rebalance bypasses the aggregate band:
                # rebalance iff some name is entering/exiting or drifts > the per-name
                # threshold (partial would-be turnover > 0). Full mode keeps the band.
                if config.partial_rebalance:
                    should_rebalance = (
                        _partial_would_be_turnover(
                            current_w, target, config.per_name_rebalance_threshold
                        )
                        > 0.0
                    )
                else:
                    should_rebalance = (
                        _would_be_turnover(current_w, target) > config.no_trade_band
                    )
                if should_rebalance:
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
        prev_close_row = close_row  # B081 F003 — next day's 涨跌停 reference close

    # Final held book (close-valued) — the live advisory producer publishes this as
    # "what the band-managed strategy holds today". ``close_row`` / ``equity`` /
    # ``shares`` / ``cash`` hold the last iteration's state (the loop ran >= 2 days).
    if equity > 0:
        held = _current_weights(shares, close_row, equity)
        final_holdings = CnAttackHoldings(
            weights=tuple(sorted(held.items())),
            cash_weight=max(0.0, cash / equity),
        )
    else:
        final_holdings = CnAttackHoldings(weights=(), cash_weight=1.0)

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
        final_holdings=final_holdings,
    )


__all__ = [
    "EXIT_HARD_PROFIT_TARGET",
    "EXIT_MOMENTUM_DECAY",
    "EXIT_TRAILING_STOP",
    "EXIT_VARIANTS",
    "CnAttackBacktestConfig",
    "CnAttackBacktestResult",
    "CnAttackDailyRecord",
    "CnAttackHoldings",
    "CnBacktestError",
    "run_cn_attack_backtest",
]
