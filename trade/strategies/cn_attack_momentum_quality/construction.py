"""B066 F001 — portfolio construction for the A-share attack engine.

Mirrors the relevant steps of the B025 US construction pipeline
(:mod:`trade.strategies.us_quality_momentum.construction`) over an A-share
universe, reusing the shared ``percent_rank`` primitive verbatim:

1. composite = weighted sum of percent-ranked active factors (a ticker with NaN
   in *any* active factor is dropped — for ``quality_momentum`` this is the soft
   quality filter; for ``pure_momentum`` only momentum can drop a name);
2. keep the top-N by composite (ticker tie-break, deterministic);
4. equal-weight the survivors;  *(US step 3 — earnings blackout — omitted)*
5. cap each position at ``max_position_weight`` (excess → implicit cash buffer).
   *(US step 6 — sector cap — omitted)*

The step numbers intentionally track the US pipeline's indices so the mapping is
obvious. Steps **3 (earnings blackout)** and **6 (sector cap)** of the US pipeline
are omitted on purpose: A-shares carry no earnings calendar and no GICS sector map in
this pipeline (spec §3 degradation), so reusing the US ``build_portfolio`` would
only feed it empty stand-ins. A focused CN construction keeps the engine honest
and the 2-variant factor logic clean while touching no US file (US zero-regression
is by construction).

The function is pure: inputs are read-only and the output is a fresh
:class:`CnPortfolioWeights`. Cash buffer is implicit — ``1 - sum(weights)``.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import pandas as pd

from trade.strategies.cn_attack_momentum_quality.parameters import (
    WEIGHTING_SCHEME_INVERSE_VOL,
    CnAttackParameters,
)
from trade.strategies.us_quality_momentum.ranking import percent_rank


class CnConstructionError(ValueError):
    """Raised when CN construction inputs are inconsistent."""


@dataclass(frozen=True, slots=True)
class CnPortfolioWeights:
    """Target weights from the CN attack construction pipeline (immutable)."""

    weights: tuple[tuple[str, float], ...]
    cash_buffer: float

    def as_dict(self) -> dict[str, float]:
        return dict(self.weights)

    def tickers(self) -> tuple[str, ...]:
        return tuple(ticker for ticker, _ in self.weights)

    def total_invested(self) -> float:
        return sum(weight for _, weight in self.weights)


def _aggregate_composite_score(
    factor_scores: Mapping[str, pd.Series],
    weight_mapping: Mapping[str, float],
) -> pd.Series:
    """Step 1 — weighted sum of percent-ranked factor scores.

    Each active factor is independently percent-ranked so the weighted total lives
    in ``[0, 1]``. A ticker with NaN in *any* active factor is dropped (a missing
    factor means the cross-section cannot fairly score that ticker).
    """

    missing = [factor for factor in weight_mapping if factor not in factor_scores]
    if missing:
        raise CnConstructionError(
            f"factor_scores missing required keys: {missing}"
        )
    ranked_components = [
        percent_rank(factor_scores[factor]) * weight
        for factor, weight in weight_mapping.items()
    ]
    frame = pd.concat(ranked_components, axis=1)
    total = frame.sum(axis=1, min_count=len(weight_mapping))
    return total.dropna()


def _top_n_candidates(scores: pd.Series, top_n: int) -> list[str]:
    """Step 2 — keep the top-N by composite score (ticker for stable tie-break)."""

    ordered = scores.reset_index()
    ordered.columns = pd.Index(["ticker", "score"])
    ordered = ordered.sort_values(
        ["score", "ticker"], ascending=[False, True], kind="mergesort"
    )
    return [str(ticker) for ticker in ordered["ticker"].head(top_n).tolist()]


def _equal_target_weights(candidates: list[str]) -> dict[str, float]:
    """Step 4a (default) — 1/N capital across the survivors (B066/B067 behaviour)."""

    equal_weight = 1.0 / len(candidates)
    return {ticker: equal_weight for ticker in candidates}


def _valid_sigma(
    candidates: list[str], volatilities: Mapping[str, float] | pd.Series | None
) -> dict[str, float]:
    """Per-candidate σ that is usable for ``1/σ`` (positive, finite)."""

    if volatilities is None:
        return {}
    valid: dict[str, float] = {}
    for ticker in candidates:
        sigma = volatilities.get(ticker)
        if sigma is None or pd.isna(sigma) or sigma <= 0:
            continue
        valid[ticker] = float(sigma)
    return valid


def _inverse_vol_target_weights(
    candidates: list[str],
    volatilities: Mapping[str, float] | pd.Series | None,
) -> dict[str, float]:
    """Step 4b (B068 F002) — pre-cap weight ∝ ``1/σ_i`` (risk-managed weighting).

    A name with a missing / non-positive σ keeps its place in the basket (so the
    name composition matches the equal-weight basket and the comparison isolates
    the *weighting* effect) but is imputed the cross-sectional **median** σ — a
    neutral, typical risk rather than a dropped name or an infinite weight. If NOT
    ONE candidate has a usable σ (e.g. the caller passed no volatilities), the
    scheme degrades honestly to equal weight."""

    valid = _valid_sigma(candidates, volatilities)
    if not valid:
        return _equal_target_weights(candidates)
    median_sigma = statistics.median(valid.values())
    inverse = {ticker: 1.0 / valid.get(ticker, median_sigma) for ticker in candidates}
    total = sum(inverse.values())
    return {ticker: value / total for ticker, value in inverse.items()}


def build_cn_portfolio(
    factor_scores: Mapping[str, pd.Series],
    eligible_tickers: Iterable[str],
    parameters: CnAttackParameters,
    *,
    volatilities: Mapping[str, float] | pd.Series | None = None,
) -> CnPortfolioWeights:
    """Run the composite → top-N → weight → position-cap pipeline.

    ``eligible_tickers`` is the point-in-time A-share universe at the as-of date;
    only those names can enter the portfolio (the composite is computed over the
    factor cross-section, then restricted to the universe). The survivors are then
    sized by ``parameters.weighting_scheme``:

    - ``equal`` (default) — 1/N capital (B066/B067 behaviour, unchanged);
    - ``inverse_vol`` — ``∝ 1/σ_i`` from ``volatilities`` (the trailing realized σ
      the caller computes point-in-time; see
      :func:`trade.strategies.us_quality_momentum.factors.trailing_volatility`).

    Both schemes share the same post-processing: cap each position at
    ``max_position_weight`` (excess → implicit cash buffer). ``volatilities`` is
    ignored for the equal scheme. See module docstring for the per-step semantics.
    """

    eligible = set(eligible_tickers)
    if not eligible:
        raise CnConstructionError("eligible_tickers must contain at least one ticker")

    # Restrict every factor series to the eligible universe BEFORE ranking, so the
    # cross-sectional percent-rank denominator is always the universe (candidates
    # rank against each other, not against out-of-universe names that may share
    # the factor frame). The wired signal path already pre-filters prices /
    # fundamentals to the universe, so this is a no-op there; it makes the rank
    # contract caller-independent rather than relying on the caller pre-filtering.
    restricted = {
        factor: series[series.index.isin(eligible)]
        for factor, series in factor_scores.items()
    }
    composite = _aggregate_composite_score(
        restricted, parameters.factor_weight_mapping()
    )
    if composite.empty:
        return CnPortfolioWeights(weights=(), cash_buffer=1.0)

    candidates = _top_n_candidates(composite, parameters.top_n)
    if not candidates:
        return CnPortfolioWeights(weights=(), cash_buffer=1.0)

    if parameters.weighting_scheme == WEIGHTING_SCHEME_INVERSE_VOL:
        target = _inverse_vol_target_weights(candidates, volatilities)
    else:
        target = _equal_target_weights(candidates)
    capped = {
        ticker: min(weight, parameters.max_position_weight)
        for ticker, weight in target.items()
    }
    sorted_pairs = tuple(sorted(capped.items(), key=lambda kv: kv[0]))
    invested = sum(weight for _, weight in sorted_pairs)
    cash_buffer = max(0.0, 1.0 - invested)
    return CnPortfolioWeights(weights=sorted_pairs, cash_buffer=cash_buffer)


__all__ = [
    "CnConstructionError",
    "CnPortfolioWeights",
    "build_cn_portfolio",
]
