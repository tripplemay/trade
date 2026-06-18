"""B066 F001 — end-to-end signal pipeline for the A-share attack engine.

Wires the CN point-in-time universe loader → reused B025 factor primitives
(``momentum_12_1`` + ``quality_score``, as-of safe / PIT-aware) → CN construction
→ :class:`CnSignalResult`. A-share daily prices (B062) and CAS fundamentals (B065)
live in the **same unified CSVs** as the US data, so the US loaders are reused
verbatim and the frames are filtered to the CN universe **before** factor scoring
so every percent-rank is cross-sectional among A-share candidates only (not
polluted by the US names that share the file).

``generate_cn_attack_signal(parameters, as_of_date, current_holdings)`` is the
daily-as-of entry point F002's no-trade-band driver loops over; ``current_holdings``
is accepted here (the F002 contract) but the no-trade-band / exit logic that
consumes it is F002's daily driver, not this single-date signal.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

import pandas as pd

from trade.data.cn_attack_universe import load_cn_universe
from trade.data.us_quality_universe import load_fundamentals, load_prices
from trade.strategies.cn_attack_momentum_quality.construction import (
    CnPortfolioWeights,
    build_cn_portfolio,
)
from trade.strategies.cn_attack_momentum_quality.parameters import CnAttackParameters
from trade.strategies.us_quality_momentum.factors import momentum_12_1, quality_score
from trade.strategies.us_quality_momentum.ranking import percent_rank


@dataclass(frozen=True, slots=True)
class CnSignalResult:
    """All output recorded for a single ``as_of_date`` CN attack signal run."""

    as_of_date: date
    parameters_hash: str
    factor_variant: str
    universe_size: int
    portfolio: CnPortfolioWeights
    factor_contributions: tuple[tuple[str, tuple[tuple[str, float], ...]], ...]

    def weights_dict(self) -> dict[str, float]:
        return self.portfolio.as_dict()

    def tickers(self) -> tuple[str, ...]:
        return self.portfolio.tickers()

    def factor_contributions_dict(self) -> dict[str, dict[str, float]]:
        return {ticker: dict(rows) for ticker, rows in self.factor_contributions}


def _filter_to_universe(frame: pd.DataFrame, members: set[str]) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame.loc[frame["ticker"].isin(members)].reset_index(drop=True)


def _compute_factor_scores(
    weight_mapping: Mapping[str, float],
    cn_prices: pd.DataFrame,
    cn_fundamentals: pd.DataFrame,
    as_of_date: date,
) -> dict[str, pd.Series]:
    """Score only the active factors (so pure_momentum needs no fundamentals)."""

    scores: dict[str, pd.Series] = {}
    if "momentum" in weight_mapping:
        scores["momentum"] = momentum_12_1(cn_prices, as_of_date)
    if "quality" in weight_mapping:
        scores["quality"] = quality_score(cn_fundamentals, as_of_date)
    return scores


def _compute_factor_contributions(
    factor_scores: Mapping[str, pd.Series],
    weight_mapping: Mapping[str, float],
    selected_tickers: tuple[str, ...],
) -> tuple[tuple[str, tuple[tuple[str, float], ...]], ...]:
    """Per-ticker contribution = ``percent_rank(factor) * weight`` (selected only)."""

    ranked_components = {
        factor: percent_rank(factor_scores[factor]) * weight
        for factor, weight in weight_mapping.items()
    }
    contributions: list[tuple[str, tuple[tuple[str, float], ...]]] = []
    for ticker in selected_tickers:
        rows: list[tuple[str, float]] = []
        for factor in weight_mapping:
            value = ranked_components[factor].get(ticker)
            rows.append(
                (factor, 0.0 if value is None or pd.isna(value) else float(value))
            )
        contributions.append((ticker, tuple(rows)))
    return tuple(contributions)


def generate_cn_attack_signal(
    parameters: CnAttackParameters,
    as_of_date: date,
    current_holdings: Mapping[str, float] | None = None,
    *,
    prices: pd.DataFrame | None = None,
    fundamentals: pd.DataFrame | None = None,
    universe_members: tuple[str, ...] | None = None,
) -> CnSignalResult:
    """Run the full A-share attack pipeline at ``as_of_date``.

    Loads the point-in-time CN universe, scores the active factors over the
    CN-only price/fundamentals cross-section, and builds the equal-weighted top-N
    portfolio. ``current_holdings`` is accepted for the F002 daily-driver contract
    (no-trade band / exits); this single-date signal computes the unconditional
    target and does not itself apply a band.

    ``prices`` / ``fundamentals`` / ``universe_members`` are optional injected
    overrides. When omitted they are loaded from disk (the unified CSVs / CN
    universe CSV). F002's daily driver injects the once-loaded frames so the
    250-day backtest loop does not re-read the CSVs every day; tests inject
    synthetic A-share frames. The factor functions re-filter by ``as_of_date``
    defensively, so a full (all-dates) injected frame is point-in-time safe.
    """

    # F002 daily-driver hook: the unconditional target is band-agnostic here.
    del current_holdings

    members = (
        universe_members
        if universe_members is not None
        else load_cn_universe(as_of_date)
    )
    weight_mapping = parameters.factor_weight_mapping()
    if not members:
        return CnSignalResult(
            as_of_date=as_of_date,
            parameters_hash=parameters.parameter_hash(),
            factor_variant=parameters.factor_variant,
            universe_size=0,
            portfolio=CnPortfolioWeights(weights=(), cash_buffer=1.0),
            factor_contributions=(),
        )

    member_set = set(members)
    raw_prices = prices if prices is not None else load_prices(as_of=as_of_date)
    cn_prices = _filter_to_universe(raw_prices, member_set)
    if "quality" in weight_mapping:
        raw_fundamentals = (
            fundamentals
            if fundamentals is not None
            else load_fundamentals(as_of=as_of_date)
        )
        cn_fundamentals = _filter_to_universe(raw_fundamentals, member_set)
    else:
        cn_fundamentals = pd.DataFrame()
    factor_scores = _compute_factor_scores(
        weight_mapping, cn_prices, cn_fundamentals, as_of_date
    )
    portfolio = build_cn_portfolio(factor_scores, members, parameters)
    contributions = _compute_factor_contributions(
        factor_scores, weight_mapping, portfolio.tickers()
    )
    return CnSignalResult(
        as_of_date=as_of_date,
        parameters_hash=parameters.parameter_hash(),
        factor_variant=parameters.factor_variant,
        universe_size=len(members),
        portfolio=portfolio,
        factor_contributions=contributions,
    )


__all__ = ["CnSignalResult", "generate_cn_attack_signal"]
