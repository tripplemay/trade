"""End-to-end signal pipeline for B025 US Quality Momentum.

Wires Repository loaders → 5 factor functions → construction pipeline →
``SignalResult`` recording the parameter hash, target weights, sector
exposure, factor contributions, and earnings decisions for the artifact
trail consumed by F004 (backtest) and F005 (workbench UI).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

import pandas as pd

from trade.data.us_quality_universe import (
    load_earnings_calendar,
    load_fundamentals,
    load_prices,
    load_universe,
)
from trade.strategies.us_quality_momentum.construction import (
    EarningsDecision,
    PortfolioWeights,
    _sector_map_from_universe,
    build_portfolio,
    compute_sector_exposure,
)
from trade.strategies.us_quality_momentum.factors import (
    low_vol_score,
    momentum_12_1,
    quality_score,
    trend_score,
    value_score,
)
from trade.strategies.us_quality_momentum.parameters import (
    UsQualityMomentumParameters,
)
from trade.strategies.us_quality_momentum.ranking import percent_rank


@dataclass(frozen=True, slots=True)
class SignalResult:
    """All output recorded for a single ``as_of_date`` signal run."""

    as_of_date: date
    parameters_hash: str
    portfolio: PortfolioWeights
    sector_exposure: tuple[tuple[str, float], ...]
    factor_contributions: tuple[tuple[str, tuple[tuple[str, float], ...]], ...]

    def weights_dict(self) -> dict[str, float]:
        return self.portfolio.as_dict()

    def sector_exposure_dict(self) -> dict[str, float]:
        return dict(self.sector_exposure)

    def factor_contributions_dict(self) -> dict[str, dict[str, float]]:
        return {ticker: dict(rows) for ticker, rows in self.factor_contributions}

    def earnings_decisions(self) -> tuple[EarningsDecision, ...]:
        return self.portfolio.earnings_decisions


def _compute_factor_contributions(
    factor_scores: Mapping[str, pd.Series],
    parameters: UsQualityMomentumParameters,
    selected_tickers: tuple[str, ...],
) -> tuple[tuple[str, tuple[tuple[str, float], ...]], ...]:
    """Per-ticker contribution map = ``percent_rank(factor) * factor_weight``.

    Only the selected (in-portfolio) tickers are emitted to keep the audit
    artifact compact; sum of contributions per ticker equals its composite
    score before the position / sector caps were applied.
    """

    weight_map = parameters.factor_weights.as_mapping()
    ranked_components = {
        factor: percent_rank(factor_scores[factor]) * weight
        for factor, weight in weight_map.items()
    }
    contributions: list[tuple[str, tuple[tuple[str, float], ...]]] = []
    for ticker in selected_tickers:
        rows: list[tuple[str, float]] = []
        for factor, weight in weight_map.items():
            value = ranked_components[factor].get(ticker)
            if value is None or pd.isna(value):
                rows.append((factor, 0.0))
            else:
                rows.append((factor, float(value)))
            # weight unused beyond keying — already baked into `value`.
            del weight
        contributions.append((ticker, tuple(rows)))
    return tuple(contributions)


def generate_signal(
    parameters: UsQualityMomentumParameters,
    as_of_date: date,
    current_holdings: Mapping[str, float] | None = None,
) -> SignalResult:
    """Run the full pipeline at ``as_of_date`` and return a signed result.

    Uses the default fixture path for prices / fundamentals / universe /
    earnings calendar. Callers passing a custom fixture must use the lower-
    level :func:`build_portfolio` directly with hand-loaded frames.
    """

    universe = load_universe(as_of=as_of_date)
    prices = load_prices(as_of=as_of_date)
    fundamentals = load_fundamentals(as_of=as_of_date)
    earnings = load_earnings_calendar()  # forward-looking; no as_of filter
    factor_scores = {
        "momentum": momentum_12_1(prices, as_of_date),
        "quality": quality_score(fundamentals, as_of_date),
        "low_vol": low_vol_score(prices, as_of_date),
        "value": value_score(fundamentals, as_of_date),
        "trend": trend_score(prices, as_of_date),
    }
    sector_map = _sector_map_from_universe(universe)
    portfolio = build_portfolio(
        scores=factor_scores,
        universe=universe,
        sector_map=sector_map,
        earnings_dates=earnings,
        as_of=as_of_date,
        parameters=parameters,
        current_holdings=current_holdings,
    )
    sector_exposure = compute_sector_exposure(portfolio.as_dict(), sector_map)
    contributions = _compute_factor_contributions(
        factor_scores, parameters, portfolio.tickers()
    )
    return SignalResult(
        as_of_date=as_of_date,
        parameters_hash=parameters.parameter_hash(),
        portfolio=portfolio,
        sector_exposure=tuple(sorted(sector_exposure.items(), key=lambda kv: kv[0])),
        factor_contributions=contributions,
    )


__all__ = ["SignalResult", "generate_signal"]
