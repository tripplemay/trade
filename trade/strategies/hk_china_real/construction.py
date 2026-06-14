"""B063 F002 — portfolio construction for the real-data HK-China research
strategy.

Reuses the proxy strategy's price-only factors verbatim
(:func:`trade.strategies.hk_china_momentum.factors.regional_risk_off`,
:func:`~trade.strategies.hk_china_momentum.factors.trend_pass`,
:func:`~trade.strategies.hk_china_momentum.factors.composite_momentum`) — those
are pure, universe-agnostic functions over a ``date / ticker / adj_close``
frame, so running them on real individual stocks (instead of four ETFs) is a
universe swap, not a logic fork. The prices frame handed in is expected to be
**USD-converted** already (B063 F002 :func:`trade.data.hk_china_real_universe.
to_usd_prices`), so momentum is FX-aware and same-caliber as the USD proxy.

Differences from the proxy construction (individual stocks, not ETFs):

* **Generic equal-weight top-N** — no KWEB sub-limit / per-ETF special case.
  Selected names are equal-weighted (``1/n`` each), each capped at
  ``max_position_weight``; whatever the cap frees rotates to the defensive
  asset so the weights always sum to ``1.0``.
* **Regional-risk-off** uses real-universe bellwethers
  (:data:`trade.data.hk_china_real_universe.REAL_RISK_PROXIES`) rather than
  KWEB/MCHI/FXI.

The rule order matches the proxy (design doc §8): risk-off → fully defensive;
else trend-filter → rank survivors by composite momentum → take top-N.

Pure: no IO, no globals — the caller hands in the (USD) prices frame + the
point-in-time universe ticker list.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from trade.data.hk_china_real_universe import REAL_RISK_PROXIES
from trade.strategies.hk_china_momentum.factors import (
    composite_momentum,
    regional_risk_off,
    trend_pass,
)
from trade.strategies.hk_china_real.parameters import HkChinaRealParameters

_WEIGHT_ROUND_DIGITS = 6


@dataclass(frozen=True, slots=True)
class RealPortfolio:
    """Sleeve-relative target weights + the decisions/provenance behind them."""

    weights: tuple[tuple[str, float], ...]
    selected: tuple[str, ...]
    regional_risk_off: bool
    reason: str
    # Provenance for honest reporting (spec §2): how many candidates were in the
    # PIT universe vs how many actually had enough history to be scored on the
    # date. A small ``scored`` early in the window flags that the basket is built
    # from few names — useful context for the B063 report.
    candidates: int
    scored: int

    def as_dict(self) -> dict[str, float]:
        return {ticker: weight for ticker, weight in self.weights}

    def tickers(self) -> tuple[str, ...]:
        return tuple(ticker for ticker, _ in self.weights)


def _defensive(
    asset: str,
    reason: str,
    *,
    risk_off: bool,
    candidates: int,
    scored: int,
) -> RealPortfolio:
    return RealPortfolio(
        weights=((asset, 1.0),),
        selected=(),
        regional_risk_off=risk_off,
        reason=reason,
        candidates=candidates,
        scored=scored,
    )


def build_real_portfolio(
    *,
    prices: pd.DataFrame,
    universe_tickers: tuple[str, ...],
    as_of: date,
    parameters: HkChinaRealParameters,
) -> RealPortfolio:
    """Build the real-data HK-China sleeve weights at ``as_of``.

    ``prices`` must be USD-converted long-format OHLCV and ``universe_tickers``
    the point-in-time membership (listing_date <= as_of). See module docstring
    for the rule order."""

    momentum = composite_momentum(
        prices,
        as_of,
        w3=parameters.momentum_weights.r3m,
        w6=parameters.momentum_weights.r6m,
        w12=parameters.momentum_weights.r12m,
    )
    # Candidates that actually have enough history to be scored on this date
    # (provenance for the report; the binding PIT gate is this NaN filter).
    scored = sum(
        1
        for ticker in universe_tickers
        if ticker in momentum.index and pd.notna(momentum.get(ticker))
    )
    candidates = len(universe_tickers)

    if regional_risk_off(
        prices, as_of, ma_long=parameters.ma_long, proxies=REAL_RISK_PROXIES
    ):
        return _defensive(
            parameters.defensive_asset,
            "regional_risk_off",
            risk_off=True,
            candidates=candidates,
            scored=scored,
        )

    passed = trend_pass(prices, as_of, ma_long=parameters.ma_long)
    eligible = [
        ticker
        for ticker in universe_tickers
        if bool(passed.get(ticker, False))
        and ticker in momentum.index
        and pd.notna(momentum.get(ticker))
    ]
    if not eligible:
        return _defensive(
            parameters.defensive_asset,
            "no_name_passed_trend",
            risk_off=False,
            candidates=candidates,
            scored=scored,
        )

    # Rank survivors by composite momentum (desc); ticker as a stable tiebreak.
    ranked = sorted(eligible, key=lambda t: (-float(momentum[t]), t))
    selected = tuple(ranked[: parameters.top_n])

    base_weight = 1.0 / len(selected)
    weights: dict[str, float] = {}
    for ticker in selected:
        capped = min(base_weight, parameters.max_position_weight)
        weights[ticker] = round(capped, _WEIGHT_ROUND_DIGITS)

    allocated = sum(weights.values())
    defensive_weight = round(1.0 - allocated, _WEIGHT_ROUND_DIGITS)
    if defensive_weight > 0:
        weights[parameters.defensive_asset] = round(
            weights.get(parameters.defensive_asset, 0.0) + defensive_weight,
            _WEIGHT_ROUND_DIGITS,
        )

    ordered = tuple(sorted(weights.items(), key=lambda kv: (-kv[1], kv[0])))
    return RealPortfolio(
        weights=ordered,
        selected=selected,
        regional_risk_off=False,
        reason="selected_top_n",
        candidates=candidates,
        scored=scored,
    )
