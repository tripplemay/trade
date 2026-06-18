"""B067 F001 — live advisory target for the A-share attack engine.

The B057 multi-mode platform publishes each mode's *current* target into the
generic target layer (``recommendation_snapshot`` keyed by ``strategy_id``). This
module derives that current target for the CN attack engine from the **daily
no-trade-band driver** (not a raw single-date signal): it runs
:func:`run_cn_attack_backtest` over the warmed window ending at ``as_of`` so the
published target reflects the band-managed book the strategy actually holds, then
reproduces the *as_of-day* decision the backtest loop deliberately skips.

Why the as_of decision is reproduced here, not read off the last record: the
backtest decides at each close to execute at the *next* open (T+1), so it skips a
decision on the final day (there is no next open in the data). The advisory user,
however, wants exactly "given today's close, what should I hold tomorrow?". So we
take the engine's final held book (``CnAttackBacktestResult.final_holdings``) as
the current portfolio, compute today's signal, and apply the same no-trade-band
gate the engine uses:

- ``would-be turnover`` (``sum|signal_w − held_w|`` over invested names) ≤ band →
  **hold**: the published target is the current held book (winners run);
- ``> band`` → **rebalance**: the published target is today's signal; the names
  rotated out (held but no longer in the signal) are the profit-take / 获利了结 list.

The live default exit is ``momentum_decay`` (the P2 live variant, spec §1): names
leave only by dropping out of the top-N (natural rotation / profit-take). The
trailing-stop / hard-profit-target overlays are backtest research dimensions; they
need the engine's internal entry/peak state, so they are not reproduced here — the
producer always drives this with the momentum_decay base config.

Pure ``trade`` (no akshare / broker / workbench import): the workbench precompute
imports this lazily off the request path (§12.10.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from trade.backtest.cn_attack_momentum_quality.engine import (
    CnAttackBacktestConfig,
    _would_be_turnover,
    run_cn_attack_backtest,
)
from trade.data.cn_attack_universe import load_cn_universe_history, resolve_pit_members
from trade.data.us_quality_universe import load_fundamentals, load_prices
from trade.strategies.cn_attack_momentum_quality.parameters import CnAttackParameters
from trade.strategies.cn_attack_momentum_quality.signal import generate_cn_attack_signal

_WEIGHT_ROUND_DIGITS = 6


@dataclass(frozen=True, slots=True)
class CnAttackLiveTarget:
    """The CN attack engine's current published advisory target.

    ``target_weights`` are the invested names only (no cash row) — the producer
    appends the explicit cash row so the persisted snapshot sums to 1.0.
    """

    as_of_date: date
    signal_date: date
    factor_variant: str
    target_weights: dict[str, float]  # invested name → weight (excludes cash)
    cash_weight: float
    rebalanced: bool  # would-be turnover at as_of exceeds the no-trade band
    profit_take: tuple[str, ...]  # held names rotated out today (获利了结 / 跌出 top-N)
    would_be_turnover: float
    no_trade_band: float
    top_n: int


def compute_cn_attack_live_target(
    parameters: CnAttackParameters,
    config: CnAttackBacktestConfig | None = None,
    *,
    prices: pd.DataFrame | None = None,
    fundamentals: pd.DataFrame | None = None,
    universe_history: dict[date, tuple[str, ...]] | None = None,
    as_of: date | None = None,
) -> CnAttackLiveTarget:
    """Derive the current advisory target from the daily band driver.

    ``prices`` / ``fundamentals`` / ``universe_history`` default to the on-disk
    unified CSVs (the VM data root via ``WORKBENCH_DATA_ROOT``); tests inject
    synthetic frames. ``as_of`` defaults to the last trading day in ``prices``.
    The result is the band-managed book (hold) or today's signal (rebalance),
    plus the profit-take list — never a raw signal, per spec §1.
    """

    if config is None:
        config = CnAttackBacktestConfig()
    if universe_history is None:
        universe_history = load_cn_universe_history()
    if prices is None:
        prices = load_prices()
    needs_quality = "quality" in parameters.factor_weight_mapping()
    if needs_quality and fundamentals is None:
        fundamentals = load_fundamentals()

    result = run_cn_attack_backtest(
        parameters,
        config,
        end=as_of,
        prices=prices,
        fundamentals=fundamentals,
        universe_history=universe_history,
    )
    as_of_date = result.daily_records[-1].date
    held = result.final_holdings.as_dict()

    members = resolve_pit_members(universe_history, as_of_date)
    signal = generate_cn_attack_signal(
        parameters,
        as_of_date,
        prices=prices,
        fundamentals=fundamentals,
        universe_members=members,
    )
    signal_target = signal.weights_dict()

    would_be = _would_be_turnover(held, signal_target)
    rebalanced = would_be > config.no_trade_band
    if rebalanced:
        target_invested = dict(signal_target)
        # Names held today but absent from the new signal = rotated out (sold).
        profit_take = tuple(sorted(set(held) - set(signal_target)))
    else:
        # Hold day: the band keeps the current book (winners run); nothing sold.
        target_invested = dict(held)
        profit_take = ()

    rounded = {
        ticker: round(float(weight), _WEIGHT_ROUND_DIGITS)
        for ticker, weight in sorted(target_invested.items())
        if float(weight) > 0
    }
    cash_weight = round(1.0 - sum(rounded.values()), _WEIGHT_ROUND_DIGITS)
    if cash_weight < 0:
        cash_weight = 0.0

    return CnAttackLiveTarget(
        as_of_date=as_of_date,
        signal_date=as_of_date,
        factor_variant=parameters.factor_variant,
        target_weights=rounded,
        cash_weight=cash_weight,
        rebalanced=rebalanced,
        profit_take=profit_take,
        would_be_turnover=would_be,
        no_trade_band=config.no_trade_band,
        top_n=parameters.top_n,
    )


__all__ = ["CnAttackLiveTarget", "compute_cn_attack_live_target"]
