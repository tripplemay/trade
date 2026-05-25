"""Portfolio construction for the B025 US Quality Momentum strategy.

Implements the 6-step pipeline from spec §F003:

1. Aggregate the 5 factor scores into a composite total per ticker.
2. Sort by composite score and keep the top N candidates.
3. Apply the earnings-blackout policy (3 scenarios — held, new, past).
4. Equal-weight the candidates that survive earnings filtering.
5. Cap any single position at ``max_position_weight`` (excess → cash buffer).
6. Cap any single sector at ``max_sector_weight`` (excess → cash buffer).

The function is pure: inputs are treated as read-only and outputs are a new
:class:`PortfolioWeights` instance. Cash buffer is implicit — anything not
allocated to a ticker after step 6 lives in ``1 - sum(weights)``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from trade.data.us_quality_universe import UniverseEntry
from trade.strategies.us_quality_momentum.parameters import (
    UsQualityMomentumParameters,
)
from trade.strategies.us_quality_momentum.ranking import percent_rank

WEIGHT_SUM_TOLERANCE = 1e-8
MAX_SECTOR_CAP_ITERATIONS = 12
EARNINGS_SCENARIO_NORMAL = "normal"
EARNINGS_SCENARIO_HELD_FROZEN = "held_through_earnings"
EARNINGS_SCENARIO_NEW_SKIPPED = "new_candidate_skipped"


class ConstructionError(ValueError):
    """Raised when construction inputs are inconsistent."""


@dataclass(frozen=True, slots=True)
class EarningsDecision:
    """Per-candidate earnings-window outcome for audit/observability."""

    ticker: str
    scenario: str
    next_earnings: date | None


@dataclass(frozen=True, slots=True)
class PortfolioWeights:
    """Target weights from the construction pipeline.

    Stored as an immutable tuple of ``(ticker, weight)`` pairs. Callers use
    :meth:`as_dict` when they need a mutable working copy.
    """

    weights: tuple[tuple[str, float], ...]
    cash_buffer: float
    earnings_decisions: tuple[EarningsDecision, ...]

    def as_dict(self) -> dict[str, float]:
        return dict(self.weights)

    def tickers(self) -> tuple[str, ...]:
        return tuple(ticker for ticker, _ in self.weights)

    def total_invested(self) -> float:
        return sum(weight for _, weight in self.weights)


def _sector_map_from_universe(universe: tuple[UniverseEntry, ...]) -> dict[str, str]:
    return {entry.ticker: entry.gics_sector for entry in universe}


def _aggregate_composite_score(
    factor_scores: Mapping[str, pd.Series],
    parameters: UsQualityMomentumParameters,
) -> pd.Series:
    """Step 1 — weighted sum of percent-ranked factor scores.

    Each factor is independently percent-ranked so the weighted total lives
    in ``[0, 1]``. Tickers with NaN in *any* factor are dropped: a missing
    factor means the cross-section cannot fairly score that ticker.
    """

    weights = parameters.factor_weights.as_mapping()
    missing = [factor for factor in weights if factor not in factor_scores]
    if missing:
        raise ConstructionError(f"factor_scores missing required keys: {missing}")
    ranked_components: list[pd.Series] = []
    for factor, weight in weights.items():
        ranked = percent_rank(factor_scores[factor]) * weight
        ranked_components.append(ranked)
    frame = pd.concat(ranked_components, axis=1)
    # Any NaN in any factor → drop ticker (sum on a row with NaN becomes NaN
    # and gets filtered downstream).
    total = frame.sum(axis=1, min_count=len(weights))
    return total.dropna()


def _top_n_candidates(scores: pd.Series, top_n: int) -> list[str]:
    """Step 2 — keep the top-N by composite score (ticker for stable tie-break)."""

    ordered = scores.sort_values(ascending=False, kind="mergesort")
    # Stable secondary sort by ticker for determinism on ties.
    ordered = ordered.reset_index()
    ordered.columns = pd.Index(["ticker", "score"])
    ordered = ordered.sort_values(
        ["score", "ticker"], ascending=[False, True], kind="mergesort"
    )
    return [str(ticker) for ticker in ordered["ticker"].head(top_n).tolist()]


def _next_earnings_per_ticker(
    earnings_dates: pd.DataFrame,
    as_of: date,
    window_days: int,
) -> dict[str, date]:
    """Lookup ticker → next earnings date strictly inside ``(as_of, as_of+window]``.

    Returns only tickers whose next announcement is *inside the blackout
    window*. Tickers without an upcoming earnings date inside the window
    are absent from the dict.
    """

    if "ticker" not in earnings_dates.columns or "earnings_date" not in earnings_dates.columns:
        raise ConstructionError(
            "earnings_dates must contain 'ticker' and 'earnings_date' columns"
        )
    start_cutoff = pd.Timestamp(as_of)
    end_cutoff = pd.Timestamp(as_of + timedelta(days=window_days))
    earnings = earnings_dates.copy()
    earnings["earnings_date"] = pd.to_datetime(earnings["earnings_date"])
    in_window = earnings[
        (earnings["earnings_date"] >= start_cutoff)
        & (earnings["earnings_date"] <= end_cutoff)
    ]
    # If a ticker has multiple announcements in window (synthetic edge), the
    # earliest one wins.
    earliest = in_window.sort_values("earnings_date").groupby("ticker").first()
    return {
        str(ticker): pd.Timestamp(row["earnings_date"]).date()
        for ticker, row in earliest.iterrows()
    }


def _classify_earnings_scenarios(
    candidates: list[str],
    upcoming_earnings: dict[str, date],
    current_holdings: Mapping[str, float] | None,
) -> tuple[list[str], dict[str, float], list[EarningsDecision]]:
    """Step 3 — apply the 3-scenario earnings policy.

    Returns ``(active_pool, frozen_weights, decisions)``:

    - ``active_pool`` — candidates that move on to equal weighting.
    - ``frozen_weights`` — held tickers whose existing weight is preserved
      (no new orders during their earnings blackout).
    - ``decisions`` — per-candidate audit trail.
    """

    held = dict(current_holdings or {})
    active_pool: list[str] = []
    frozen_weights: dict[str, float] = {}
    decisions: list[EarningsDecision] = []
    for ticker in candidates:
        announcement = upcoming_earnings.get(ticker)
        if announcement is None:
            active_pool.append(ticker)
            decisions.append(
                EarningsDecision(
                    ticker=ticker,
                    scenario=EARNINGS_SCENARIO_NORMAL,
                    next_earnings=None,
                )
            )
            continue
        if ticker in held and held[ticker] > 0.0:
            frozen_weights[ticker] = held[ticker]
            decisions.append(
                EarningsDecision(
                    ticker=ticker,
                    scenario=EARNINGS_SCENARIO_HELD_FROZEN,
                    next_earnings=announcement,
                )
            )
        else:
            decisions.append(
                EarningsDecision(
                    ticker=ticker,
                    scenario=EARNINGS_SCENARIO_NEW_SKIPPED,
                    next_earnings=announcement,
                )
            )
    return active_pool, frozen_weights, decisions


def _equal_weight_pool(
    active_pool: list[str],
    frozen_weights: dict[str, float],
    parameters: UsQualityMomentumParameters,
) -> dict[str, float]:
    """Step 4 — equal-weight the surviving active pool over the remaining capacity."""

    if not active_pool:
        return {}
    frozen_capacity = sum(frozen_weights.values())
    remaining_capacity = max(0.0, 1.0 - frozen_capacity)
    if remaining_capacity == 0.0:
        return {ticker: 0.0 for ticker in active_pool}
    equal_weight = remaining_capacity / len(active_pool)
    return {ticker: equal_weight for ticker in active_pool}


def _apply_position_cap(
    weights: dict[str, float], max_position_weight: float
) -> dict[str, float]:
    """Step 5 — clamp every position to ``max_position_weight`` (excess → cash)."""

    return {
        ticker: min(weight, max_position_weight)
        for ticker, weight in weights.items()
    }


def _apply_sector_cap(
    weights: dict[str, float],
    sector_map: Mapping[str, str],
    max_sector_weight: float,
) -> dict[str, float]:
    """Step 6 — iteratively scale down any over-cap sector (excess → cash).

    The simplification is documented in spec §F003: excess weight from an
    over-cap sector becomes cash buffer rather than being redistributed to
    other sectors. Redistribution would re-trigger the position cap and risk
    oscillating; cashing it out keeps the algorithm finite and predictable.
    """

    current = dict(weights)
    for _ in range(MAX_SECTOR_CAP_ITERATIONS):
        sector_totals: dict[str, float] = {}
        for ticker, weight in current.items():
            sector = sector_map.get(ticker)
            if sector is None:
                continue
            sector_totals[sector] = sector_totals.get(sector, 0.0) + weight
        over_sectors = {
            sector: total
            for sector, total in sector_totals.items()
            if total > max_sector_weight + WEIGHT_SUM_TOLERANCE
        }
        if not over_sectors:
            return current
        for sector, total in over_sectors.items():
            scale = max_sector_weight / total
            for ticker in list(current.keys()):
                if sector_map.get(ticker) == sector:
                    current[ticker] *= scale
    return current


def build_portfolio(
    scores: Mapping[str, pd.Series],
    universe: tuple[UniverseEntry, ...],
    sector_map: Mapping[str, str],
    earnings_dates: pd.DataFrame,
    as_of: date,
    parameters: UsQualityMomentumParameters,
    current_holdings: Mapping[str, float] | None = None,
) -> PortfolioWeights:
    """Run the 6-step construction pipeline. See module docstring for steps."""

    if not universe:
        raise ConstructionError("universe must contain at least one entry")
    eligible_tickers = {entry.ticker for entry in universe}

    composite = _aggregate_composite_score(scores, parameters)
    composite = composite.loc[composite.index.isin(eligible_tickers)]
    if composite.empty:
        return PortfolioWeights(weights=(), cash_buffer=1.0, earnings_decisions=())

    candidates = _top_n_candidates(composite, parameters.top_n)
    upcoming_earnings = _next_earnings_per_ticker(
        earnings_dates, as_of, parameters.earnings_window_days
    )
    active_pool, frozen_weights, decisions = _classify_earnings_scenarios(
        candidates, upcoming_earnings, current_holdings
    )
    equal_weights = _equal_weight_pool(active_pool, frozen_weights, parameters)
    after_position_cap = _apply_position_cap(
        equal_weights, parameters.max_position_weight
    )
    # Frozen weights bypass the position cap (existing holdings) but feed the
    # sector cap below — held tickers still count toward sector totals.
    combined = {**after_position_cap, **frozen_weights}
    after_sector_cap = _apply_sector_cap(
        combined, sector_map, parameters.max_sector_weight
    )

    # Stable sort: ticker for deterministic ordering.
    sorted_pairs = tuple(sorted(after_sector_cap.items(), key=lambda kv: kv[0]))
    invested = sum(weight for _, weight in sorted_pairs)
    cash_buffer = max(0.0, 1.0 - invested)
    return PortfolioWeights(
        weights=sorted_pairs,
        cash_buffer=cash_buffer,
        earnings_decisions=tuple(decisions),
    )


def compute_sector_exposure(
    weights: Mapping[str, float], sector_map: Mapping[str, str]
) -> dict[str, float]:
    """Aggregate portfolio weight per GICS sector for reporting / risk panel."""

    exposure: dict[str, float] = {}
    for ticker, weight in weights.items():
        sector = sector_map.get(ticker, "UNKNOWN")
        exposure[sector] = exposure.get(sector, 0.0) + weight
    return exposure


__all__ = [
    "ConstructionError",
    "EARNINGS_SCENARIO_HELD_FROZEN",
    "EARNINGS_SCENARIO_NEW_SKIPPED",
    "EARNINGS_SCENARIO_NORMAL",
    "EarningsDecision",
    "PortfolioWeights",
    "build_portfolio",
    "compute_sector_exposure",
]
