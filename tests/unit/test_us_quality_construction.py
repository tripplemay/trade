"""Unit tests for the B025 portfolio construction pipeline."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from trade.data.us_quality_universe import UniverseEntry
from trade.strategies.us_quality_momentum.construction import (
    EARNINGS_SCENARIO_HELD_FROZEN,
    EARNINGS_SCENARIO_NEW_SKIPPED,
    EARNINGS_SCENARIO_NORMAL,
    ConstructionError,
    PortfolioWeights,
    _sector_map_from_universe,
    build_portfolio,
    compute_sector_exposure,
)
from trade.strategies.us_quality_momentum.parameters import (
    FactorWeights,
    UsQualityMomentumParameters,
)


def _make_universe(entries: list[tuple[str, str]]) -> tuple[UniverseEntry, ...]:
    """Compact helper: ``[(ticker, sector), ...]``."""

    return tuple(
        UniverseEntry(
            ticker=ticker,
            name=ticker,
            exchange="NYSE",
            gics_sector=sector,
            gics_industry="Test",
            listing_date=date(2010, 1, 1),
            market_cap_initial=50e9,
        )
        for ticker, sector in entries
    )


def _flat_factor_scores(
    rankings: dict[str, float],
) -> dict[str, pd.Series]:
    """Same per-ticker raw score across all 5 factors → composite == score."""

    series = pd.Series(rankings)
    factors = ("momentum", "quality", "low_vol", "value", "trend")
    return {factor: series.copy() for factor in factors}


def _empty_earnings_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": pd.Series([], dtype=str),
            "earnings_date": pd.Series([], dtype="datetime64[ns]"),
        }
    )


# ---------------------------------------------------------------------------
# Composite score + Top N
# ---------------------------------------------------------------------------


def test_build_portfolio_selects_top_n_by_composite_score() -> None:
    rankings = {f"T{i:02d}": float(i) for i in range(20)}
    universe = _make_universe(
        [(ticker, f"Sector{i % 4}") for i, ticker in enumerate(rankings)]
    )
    scores = _flat_factor_scores(rankings)
    params = UsQualityMomentumParameters(top_n=15)
    result = build_portfolio(
        scores=scores,
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=_empty_earnings_frame(),
        as_of=date(2024, 1, 2),
        parameters=params,
    )
    # Top 15 (by ascending T00…T19, the top 15 = T05..T19, descending score).
    expected_top = {f"T{i:02d}" for i in range(5, 20)}
    assert set(result.tickers()) == expected_top


def test_build_portfolio_drops_tickers_with_nan_in_any_factor() -> None:
    rankings = {f"T{i:02d}": float(i) for i in range(20)}
    scores = _flat_factor_scores(rankings)
    # Punch a NaN into momentum for T19 — the would-be top pick.
    scores["momentum"]["T19"] = float("nan")
    universe = _make_universe(
        [(ticker, f"Sector{i % 4}") for i, ticker in enumerate(rankings)]
    )
    params = UsQualityMomentumParameters(top_n=15)
    result = build_portfolio(
        scores=scores,
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=_empty_earnings_frame(),
        as_of=date(2024, 1, 2),
        parameters=params,
    )
    assert "T19" not in result.tickers()


def test_build_portfolio_equal_weights_active_pool_within_position_cap() -> None:
    rankings = {f"T{i:02d}": float(i) for i in range(20)}
    universe = _make_universe(
        [(ticker, f"Sector{i % 5}") for i, ticker in enumerate(rankings)]
    )
    params = UsQualityMomentumParameters(top_n=15)
    result = build_portfolio(
        scores=_flat_factor_scores(rankings),
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=_empty_earnings_frame(),
        as_of=date(2024, 1, 2),
        parameters=params,
    )
    weights = result.as_dict()
    expected = 1.0 / params.top_n  # 1/15 ≈ 0.0667 < 0.07 cap
    np.testing.assert_allclose(list(weights.values()), [expected] * params.top_n)


def test_build_portfolio_sum_of_weights_within_tolerance_of_one() -> None:
    rankings = {f"T{i:02d}": float(i) for i in range(20)}
    universe = _make_universe(
        [(ticker, f"Sector{i % 5}") for i, ticker in enumerate(rankings)]
    )
    result = build_portfolio(
        scores=_flat_factor_scores(rankings),
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=_empty_earnings_frame(),
        as_of=date(2024, 1, 2),
        parameters=UsQualityMomentumParameters(top_n=15),
    )
    assert result.total_invested() == pytest.approx(1.0, abs=1e-8)
    assert result.cash_buffer == pytest.approx(0.0, abs=1e-8)


# ---------------------------------------------------------------------------
# Position cap
# ---------------------------------------------------------------------------


def test_position_cap_triggers_when_equal_weight_exceeds_max() -> None:
    # top_n=20 × max=0.05 = 1.00 (cap is reachable). Equal weight 1/20 = 0.05,
    # exactly at the cap, so total invested = 1.0 with no cash buffer.
    rankings = {f"T{i:02d}": float(i) for i in range(20)}
    universe = _make_universe(
        [(ticker, f"Sector{i % 5}") for i, ticker in enumerate(rankings)]
    )
    params = UsQualityMomentumParameters(top_n=20, max_position_weight=0.05)
    result = build_portfolio(
        scores=_flat_factor_scores(rankings),
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=_empty_earnings_frame(),
        as_of=date(2024, 1, 2),
        parameters=params,
    )
    weights = result.as_dict()
    assert max(weights.values()) == pytest.approx(0.05, abs=1e-9)
    assert result.total_invested() == pytest.approx(1.0, abs=1e-8)


def test_position_cap_clamps_when_pool_smaller_than_top_n() -> None:
    # NaN-driven pool shrinkage: 10 valid tickers, top_n=15, equal_weight = 0.1
    # which exceeds 0.07 cap. Each position should clamp to 0.07.
    rankings = {f"T{i:02d}": float(i) for i in range(10)}
    scores = _flat_factor_scores(rankings)
    universe = _make_universe(
        [(ticker, f"Sector{i % 5}") for i, ticker in enumerate(rankings)]
    )
    params = UsQualityMomentumParameters(top_n=15, max_position_weight=0.07)
    result = build_portfolio(
        scores=scores,
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=_empty_earnings_frame(),
        as_of=date(2024, 1, 2),
        parameters=params,
    )
    weights = result.as_dict()
    assert all(weight <= 0.07 + 1e-9 for weight in weights.values())
    # 10 tickers × 0.07 = 0.70 invested, 0.30 cash.
    assert result.total_invested() == pytest.approx(0.70, abs=1e-9)
    assert result.cash_buffer == pytest.approx(0.30, abs=1e-9)


# ---------------------------------------------------------------------------
# Sector cap
# ---------------------------------------------------------------------------


def _concentrated_universe_15() -> tuple[
    dict[str, float], dict[str, str], tuple[UniverseEntry, ...]
]:
    """15-ticker shape: 6 Tech + 3 Health + 3 Energy + 3 Fin.

    Equal weighting at 1/15 ≈ 0.0667 gives Tech = 0.40 (over 30% cap) while
    the other three sectors land at 0.20 each (under cap). This lets a single
    sector exceed the cap without dragging others over too.
    """

    rankings: dict[str, float] = {}
    sectors: dict[str, str] = {}
    for i in range(6):
        ticker = f"TECH{i}"
        rankings[ticker] = 100.0 + i
        sectors[ticker] = "Tech"
    for prefix, sector in (("HLTH", "Health"), ("ENER", "Energy"), ("FIN", "Fin")):
        for i in range(3):
            ticker = f"{prefix}{i}"
            rankings[ticker] = 50.0 + i
            sectors[ticker] = sector
    universe = _make_universe([(ticker, sectors[ticker]) for ticker in rankings])
    return rankings, sectors, universe


def test_sector_cap_scales_down_concentrated_sector() -> None:
    rankings, sectors, universe = _concentrated_universe_15()
    result = build_portfolio(
        scores=_flat_factor_scores(rankings),
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=_empty_earnings_frame(),
        as_of=date(2024, 1, 2),
        parameters=UsQualityMomentumParameters(top_n=15),
    )
    exposure = compute_sector_exposure(result.as_dict(), sectors)
    assert exposure["Tech"] <= 0.30 + 1e-8
    # Under-cap sectors stay at their pre-cap weights (≈ 0.20 each).
    assert exposure["Health"] == pytest.approx(0.20, abs=1e-8)
    assert exposure["Energy"] == pytest.approx(0.20, abs=1e-8)
    assert exposure["Fin"] == pytest.approx(0.20, abs=1e-8)


def test_sector_cap_excess_becomes_cash() -> None:
    rankings, _sectors, universe = _concentrated_universe_15()
    result = build_portfolio(
        scores=_flat_factor_scores(rankings),
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=_empty_earnings_frame(),
        as_of=date(2024, 1, 2),
        parameters=UsQualityMomentumParameters(top_n=15),
    )
    # Pre-cap totals: Tech 0.40, Health/Energy/Fin 0.20 each → 1.00. After
    # cap: Tech 0.30, others unchanged 0.60 → invested 0.90, cash 0.10.
    assert result.total_invested() == pytest.approx(0.90, abs=1e-8)
    assert result.cash_buffer == pytest.approx(0.10, abs=1e-8)


def test_sector_cap_respects_min_two_per_sector_universe() -> None:
    # 15 tickers, sectors balanced (3 each across 5 sectors). 0.20 per sector
    # ≤ 0.30, no cap should trigger.
    rankings = {f"T{i:02d}": float(i) for i in range(15)}
    sectors = {ticker: f"Sector{i % 5}" for i, ticker in enumerate(rankings)}
    universe = _make_universe([(ticker, sectors[ticker]) for ticker in rankings])
    result = build_portfolio(
        scores=_flat_factor_scores(rankings),
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=_empty_earnings_frame(),
        as_of=date(2024, 1, 2),
        parameters=UsQualityMomentumParameters(top_n=15),
    )
    exposure = compute_sector_exposure(result.as_dict(), sectors)
    assert all(weight <= 0.30 + 1e-8 for weight in exposure.values())


# ---------------------------------------------------------------------------
# Earnings blackout — 3 scenarios
# ---------------------------------------------------------------------------


def test_earnings_blackout_skips_new_candidate_in_window() -> None:
    rankings = {f"T{i:02d}": float(i) for i in range(15)}
    universe = _make_universe(
        [(ticker, f"Sector{i % 5}") for i, ticker in enumerate(rankings)]
    )
    # T14 has an upcoming earnings inside the 5-day blackout window.
    as_of = date(2024, 1, 2)
    earnings = pd.DataFrame(
        {
            "ticker": ["T14"],
            "earnings_date": [as_of + timedelta(days=2)],
        }
    )
    earnings["earnings_date"] = pd.to_datetime(earnings["earnings_date"])
    result = build_portfolio(
        scores=_flat_factor_scores(rankings),
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=earnings,
        as_of=as_of,
        parameters=UsQualityMomentumParameters(top_n=15),
        current_holdings=None,
    )
    assert "T14" not in result.tickers()
    decisions = {d.ticker: d.scenario for d in result.earnings_decisions}
    assert decisions["T14"] == EARNINGS_SCENARIO_NEW_SKIPPED


def test_earnings_blackout_freezes_existing_holding_at_current_weight() -> None:
    rankings = {f"T{i:02d}": float(i) for i in range(15)}
    universe = _make_universe(
        [(ticker, f"Sector{i % 5}") for i, ticker in enumerate(rankings)]
    )
    as_of = date(2024, 1, 2)
    earnings = pd.DataFrame(
        {
            "ticker": ["T14"],
            "earnings_date": [as_of + timedelta(days=2)],
        }
    )
    earnings["earnings_date"] = pd.to_datetime(earnings["earnings_date"])
    # T14 is held at 5% from the previous rebalance.
    result = build_portfolio(
        scores=_flat_factor_scores(rankings),
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=earnings,
        as_of=as_of,
        parameters=UsQualityMomentumParameters(top_n=15),
        current_holdings={"T14": 0.05},
    )
    assert result.as_dict().get("T14") == pytest.approx(0.05, abs=1e-9)
    decisions = {d.ticker: d.scenario for d in result.earnings_decisions}
    assert decisions["T14"] == EARNINGS_SCENARIO_HELD_FROZEN


def test_earnings_blackout_normal_when_past_earnings_or_window() -> None:
    rankings = {f"T{i:02d}": float(i) for i in range(15)}
    universe = _make_universe(
        [(ticker, f"Sector{i % 5}") for i, ticker in enumerate(rankings)]
    )
    as_of = date(2024, 1, 2)
    # All earnings dates are well past — should not trigger blackout.
    earnings = pd.DataFrame(
        {
            "ticker": list(rankings.keys()),
            "earnings_date": [as_of - timedelta(days=30)] * len(rankings),
        }
    )
    earnings["earnings_date"] = pd.to_datetime(earnings["earnings_date"])
    result = build_portfolio(
        scores=_flat_factor_scores(rankings),
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=earnings,
        as_of=as_of,
        parameters=UsQualityMomentumParameters(top_n=15),
    )
    decisions = {d.ticker: d.scenario for d in result.earnings_decisions}
    assert all(scenario == EARNINGS_SCENARIO_NORMAL for scenario in decisions.values())


# ---------------------------------------------------------------------------
# Misc invariants
# ---------------------------------------------------------------------------


def test_build_portfolio_returns_no_duplicate_tickers() -> None:
    rankings = {f"T{i:02d}": float(i) for i in range(20)}
    universe = _make_universe(
        [(ticker, f"Sector{i % 5}") for i, ticker in enumerate(rankings)]
    )
    result = build_portfolio(
        scores=_flat_factor_scores(rankings),
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=_empty_earnings_frame(),
        as_of=date(2024, 1, 2),
        parameters=UsQualityMomentumParameters(top_n=15),
    )
    tickers = result.tickers()
    assert len(tickers) == len(set(tickers))


def test_build_portfolio_is_deterministic_for_same_inputs() -> None:
    rankings = {f"T{i:02d}": float(i) for i in range(20)}
    universe = _make_universe(
        [(ticker, f"Sector{i % 5}") for i, ticker in enumerate(rankings)]
    )
    args = dict(
        scores=_flat_factor_scores(rankings),
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=_empty_earnings_frame(),
        as_of=date(2024, 1, 2),
        parameters=UsQualityMomentumParameters(top_n=15),
    )
    a = build_portfolio(**args)  # type: ignore[arg-type]
    b = build_portfolio(**args)  # type: ignore[arg-type]
    assert a == b


def test_build_portfolio_rejects_empty_universe() -> None:
    with pytest.raises(ConstructionError, match="universe"):
        build_portfolio(
            scores=_flat_factor_scores({"T01": 1.0}),
            universe=(),
            sector_map={},
            earnings_dates=_empty_earnings_frame(),
            as_of=date(2024, 1, 2),
            parameters=UsQualityMomentumParameters(),
        )


def test_build_portfolio_returns_cash_only_when_no_eligible_tickers() -> None:
    # Universe has T00..T04 but scores cover U00..U04 — no overlap.
    universe = _make_universe([(f"T{i:02d}", "Tech") for i in range(5)])
    scores = _flat_factor_scores({f"U{i:02d}": float(i) for i in range(5)})
    result = build_portfolio(
        scores=scores,
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=_empty_earnings_frame(),
        as_of=date(2024, 1, 2),
        parameters=UsQualityMomentumParameters(top_n=15),
    )
    assert result.tickers() == ()
    assert result.cash_buffer == pytest.approx(1.0, abs=1e-9)


def test_compute_sector_exposure_aggregates_per_sector() -> None:
    weights = {"A": 0.10, "B": 0.20, "C": 0.05}
    sector_map = {"A": "Tech", "B": "Tech", "C": "Health"}
    exposure = compute_sector_exposure(weights, sector_map)
    assert exposure == {"Tech": pytest.approx(0.30), "Health": pytest.approx(0.05)}


def test_factor_weights_can_be_overridden() -> None:
    # Custom weights that still sum to 1.0 — used to A/B test sensitivities.
    rankings = {f"T{i:02d}": float(i) for i in range(20)}
    universe = _make_universe(
        [(ticker, f"Sector{i % 5}") for i, ticker in enumerate(rankings)]
    )
    custom = UsQualityMomentumParameters(
        factor_weights=FactorWeights(
            momentum=0.50, quality=0.20, low_vol=0.10, value=0.10, trend=0.10
        ),
    )
    result = build_portfolio(
        scores=_flat_factor_scores(rankings),
        universe=universe,
        sector_map=_sector_map_from_universe(universe),
        earnings_dates=_empty_earnings_frame(),
        as_of=date(2024, 1, 2),
        parameters=custom,
    )
    assert isinstance(result, PortfolioWeights)
    assert len(result.tickers()) == custom.top_n
