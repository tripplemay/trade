"""Liquidity filter for the B025 US Quality Momentum universe.

Applied after the Repository loaders to drop tickers that fail any of four
liquidity / quality gates as of a given decision date. Thresholds default to
the values fixed by the B025 spec §F001 but are kwargs to allow scenario
analysis from inside tests and notebooks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from trade.data.us_quality_universe import UniverseEntry

ADV_TRAILING_DAYS = 60
TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True, slots=True)
class LiquidityRejection:
    """Reason a ticker was dropped (one entry per failed gate)."""

    ticker: str
    reason: str
    observed: float


@dataclass(frozen=True, slots=True)
class LiquidityFilterResult:
    """Outcome of a single ``apply_liquidity_filter`` call."""

    accepted: tuple[UniverseEntry, ...]
    rejections: tuple[LiquidityRejection, ...]

    @property
    def accepted_tickers(self) -> tuple[str, ...]:
        return tuple(entry.ticker for entry in self.accepted)


class LiquidityFilterError(ValueError):
    """Raised when filter inputs are inconsistent (e.g. ``as_of`` before any prices)."""


def apply_liquidity_filter(
    universe: tuple[UniverseEntry, ...],
    prices: pd.DataFrame,
    as_of: date,
    *,
    market_cap_threshold: float = 10e9,
    adv60_threshold: float = 50e6,
    price_threshold: float = 10.0,
    listing_age_years: float = 2.0,
) -> LiquidityFilterResult:
    """Drop tickers that fail any of the four liquidity gates as of ``as_of``.

    Gates (ticker is rejected as soon as *one* fires):

    1. ``listing_date`` more recent than ``as_of - listing_age_years``.
    2. ``market_cap_initial`` strictly below ``market_cap_threshold`` (USD).
    3. Trailing-60-day average dollar volume strictly below ``adv60_threshold``.
    4. Latest available ``close`` price on/before ``as_of`` strictly below
       ``price_threshold``.

    ``prices`` must be the long-format frame returned by
    :func:`trade.data.us_quality_universe.load_prices`. Rows are filtered
    internally to ``date <= as_of`` so callers may pass the full (or point-in-time)
    price frame indifferently.
    """

    if prices.empty:
        raise LiquidityFilterError("price frame is empty; cannot evaluate liquidity")

    cutoff = pd.Timestamp(as_of)
    visible = prices[prices["date"] <= cutoff]
    if visible.empty:
        raise LiquidityFilterError(
            f"no price rows on or before {as_of.isoformat()}; check fixture range"
        )

    listing_cutoff = date(
        as_of.year, as_of.month, as_of.day
    )  # local copy; subtract via days math
    listing_min_days = int(listing_age_years * 365.25)

    accepted: list[UniverseEntry] = []
    rejections: list[LiquidityRejection] = []

    by_ticker = {ticker: group for ticker, group in visible.groupby("ticker", sort=False)}

    for entry in universe:
        listing_age_days = (listing_cutoff - entry.listing_date).days
        if listing_age_days < listing_min_days:
            rejections.append(
                LiquidityRejection(
                    ticker=entry.ticker,
                    reason="listing_age_below_threshold",
                    observed=listing_age_days / 365.25,
                )
            )
            continue

        if entry.market_cap_initial < market_cap_threshold:
            rejections.append(
                LiquidityRejection(
                    ticker=entry.ticker,
                    reason="market_cap_below_threshold",
                    observed=entry.market_cap_initial,
                )
            )
            continue

        ticker_prices = by_ticker.get(entry.ticker)
        if ticker_prices is None or ticker_prices.empty:
            rejections.append(
                LiquidityRejection(
                    ticker=entry.ticker,
                    reason="no_price_history_at_as_of",
                    observed=0.0,
                )
            )
            continue

        trailing = ticker_prices.sort_values("date").tail(ADV_TRAILING_DAYS)
        adv_dollars = float((trailing["close"] * trailing["volume"]).mean())
        if adv_dollars < adv60_threshold:
            rejections.append(
                LiquidityRejection(
                    ticker=entry.ticker,
                    reason="adv60_below_threshold",
                    observed=adv_dollars,
                )
            )
            continue

        latest_close = float(ticker_prices.sort_values("date").iloc[-1]["close"])
        if latest_close < price_threshold:
            rejections.append(
                LiquidityRejection(
                    ticker=entry.ticker,
                    reason="price_below_threshold",
                    observed=latest_close,
                )
            )
            continue

        accepted.append(entry)

    return LiquidityFilterResult(
        accepted=tuple(accepted),
        rejections=tuple(rejections),
    )
