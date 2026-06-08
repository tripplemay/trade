"""Portfolio construction for the BL-B011-S2 HK-China Momentum satellite.

Turns the price-only factors into sleeve-relative target weights summing to
``1.0`` (design doc §8). The rules, in order:

1. **Regional-risk gate (§7.3 / §8.1)** — if :func:`regional_risk_off`, the
   sleeve goes fully defensive: ``{defensive_asset: 1.0}``.
2. **Trend filter (§7.2)** — keep only ETFs with ``close > 200D MA`` AND
   ``r6m > 0`` and a computable momentum score. None pass → fully defensive.
3. **Top 1-2 selection (§8.2)** — rank survivors by composite momentum, take
   ``top_n`` (1 or 2).
4. **Weighting (§8.2)** — Top-1 fills the sleeve; Top-2 equal-weight (0.5
   each). Apply caps: per-ETF ≤ ``max_position_weight``; KWEB ≤
   ``kweb_sublimit`` (both sleeve-relative — see parameters module). Whatever
   the caps free up rotates to the defensive asset, so the result always
   sums to ``1.0``.

Pure: no IO, no globals — the caller hands in a prices frame + universe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from trade.strategies.hk_china_momentum.factors import (
    composite_momentum,
    regional_risk_off,
    trend_pass,
)
from trade.strategies.hk_china_momentum.parameters import (
    KWEB_TICKER,
    HkChinaMomentumParameters,
)

_WEIGHT_ROUND_DIGITS = 6


@dataclass(frozen=True, slots=True)
class HkChinaPortfolio:
    """Sleeve-relative target weights + the decisions that produced them."""

    weights: tuple[tuple[str, float], ...]
    selected: tuple[str, ...]
    regional_risk_off: bool
    reason: str

    def as_dict(self) -> dict[str, float]:
        return {ticker: weight for ticker, weight in self.weights}

    def tickers(self) -> tuple[str, ...]:
        return tuple(ticker for ticker, _ in self.weights)


def _defensive(asset: str, reason: str, *, risk_off: bool) -> HkChinaPortfolio:
    return HkChinaPortfolio(
        weights=((asset, 1.0),),
        selected=(),
        regional_risk_off=risk_off,
        reason=reason,
    )


def _cap_for(ticker: str, parameters: HkChinaMomentumParameters) -> float:
    """Sleeve-relative cap for one ETF — KWEB gets the tighter sub-limit."""

    if ticker == KWEB_TICKER:
        return min(parameters.max_position_weight, parameters.kweb_sublimit)
    return parameters.max_position_weight


def build_portfolio(
    *,
    prices: pd.DataFrame,
    universe_tickers: tuple[str, ...],
    as_of: date,
    parameters: HkChinaMomentumParameters,
) -> HkChinaPortfolio:
    """Build the HK-China sleeve weights at ``as_of`` (see module docstring)."""

    if regional_risk_off(prices, as_of, ma_long=parameters.ma_long):
        return _defensive(
            parameters.defensive_asset, "regional_risk_off", risk_off=True
        )

    passed = trend_pass(prices, as_of, ma_long=parameters.ma_long)
    momentum = composite_momentum(
        prices,
        as_of,
        w3=parameters.momentum_weights.r3m,
        w6=parameters.momentum_weights.r6m,
        w12=parameters.momentum_weights.r12m,
    )

    eligible = [
        ticker
        for ticker in universe_tickers
        if bool(passed.get(ticker, False))
        and ticker in momentum.index
        and pd.notna(momentum.get(ticker))
    ]
    if not eligible:
        return _defensive(
            parameters.defensive_asset, "no_etf_passed_trend", risk_off=False
        )

    # Rank survivors by composite momentum (desc); ticker as a stable tiebreak.
    ranked = sorted(eligible, key=lambda t: (-float(momentum[t]), t))
    selected = tuple(ranked[: parameters.top_n])

    base_weight = 1.0 / len(selected)
    weights: dict[str, float] = {}
    for ticker in selected:
        capped = min(base_weight, _cap_for(ticker, parameters))
        weights[ticker] = round(capped, _WEIGHT_ROUND_DIGITS)

    allocated = sum(weights.values())
    defensive_weight = round(1.0 - allocated, _WEIGHT_ROUND_DIGITS)
    if defensive_weight > 0:
        # Fold the cap-freed remainder into the defensive asset (it may also be
        # a selected ETF in the unlikely degenerate case — sum stays 1.0).
        weights[parameters.defensive_asset] = round(
            weights.get(parameters.defensive_asset, 0.0) + defensive_weight,
            _WEIGHT_ROUND_DIGITS,
        )

    ordered = tuple(sorted(weights.items(), key=lambda kv: (-kv[1], kv[0])))
    return HkChinaPortfolio(
        weights=ordered,
        selected=selected,
        regional_risk_off=False,
        reason="selected_top_n",
    )
