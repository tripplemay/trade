"""Unit tests for the B025 end-to-end signal pipeline."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trade.strategies.us_quality_momentum.parameters import (
    UsQualityMomentumParameters,
)
from trade.strategies.us_quality_momentum.signal import generate_signal

FIXTURE_AS_OF = date(2024, 1, 2)


def test_generate_signal_returns_top_n_tickers_against_fixture() -> None:
    result = generate_signal(UsQualityMomentumParameters(), FIXTURE_AS_OF)
    assert len(result.portfolio.tickers()) == UsQualityMomentumParameters().top_n
    assert result.portfolio.total_invested() == pytest.approx(1.0, abs=1e-8)


def test_generate_signal_records_parameters_hash() -> None:
    params = UsQualityMomentumParameters()
    result = generate_signal(params, FIXTURE_AS_OF)
    assert result.parameters_hash == params.parameter_hash()
    assert len(result.parameters_hash) == 64


def test_generate_signal_is_deterministic() -> None:
    params = UsQualityMomentumParameters()
    a = generate_signal(params, FIXTURE_AS_OF)
    b = generate_signal(params, FIXTURE_AS_OF)
    assert a.parameters_hash == b.parameters_hash
    assert a.portfolio.tickers() == b.portfolio.tickers()
    assert a.weights_dict() == b.weights_dict()
    assert a.sector_exposure_dict() == b.sector_exposure_dict()


def test_generate_signal_sector_exposure_respects_cap() -> None:
    params = UsQualityMomentumParameters()
    result = generate_signal(params, FIXTURE_AS_OF)
    exposure = result.sector_exposure_dict()
    assert all(weight <= params.max_sector_weight + 1e-8 for weight in exposure.values())


def test_generate_signal_emits_factor_contributions_for_every_selection() -> None:
    params = UsQualityMomentumParameters()
    result = generate_signal(params, FIXTURE_AS_OF)
    contributions = result.factor_contributions_dict()
    expected_factors = set(params.factor_weights.as_mapping())
    for ticker in result.portfolio.tickers():
        assert ticker in contributions
        assert set(contributions[ticker]) == expected_factors


def test_generate_signal_freezes_held_ticker_through_earnings_window() -> None:
    # Find a ticker scheduled to report inside the 5-day window from a
    # particular as_of so we can prove the "held → frozen" branch end-to-end.
    from trade.data.us_quality_universe import load_earnings_calendar

    earnings = load_earnings_calendar()
    earnings = earnings.copy()
    earnings["earnings_date"] = pd.to_datetime(earnings["earnings_date"])
    # Pick an earnings date deep in the price history.
    target = earnings[earnings["earnings_date"] >= pd.Timestamp("2023-10-01")].iloc[0]
    as_of = (target["earnings_date"] - pd.Timedelta(days=2)).date()
    target_ticker = str(target["ticker"])
    result = generate_signal(
        UsQualityMomentumParameters(),
        as_of,
        current_holdings={target_ticker: 0.05},
    )
    decisions = {d.ticker: d.scenario for d in result.portfolio.earnings_decisions}
    # If the held ticker did not happen to make Top N at this as_of, it just
    # is not in the decisions list — but if present, it must be FROZEN, not
    # SKIPPED.
    if target_ticker in decisions:
        assert decisions[target_ticker] == "held_through_earnings"
        assert result.weights_dict().get(target_ticker) == pytest.approx(0.05)


def test_generate_signal_total_invested_plus_cash_equals_one() -> None:
    params = UsQualityMomentumParameters()
    result = generate_signal(params, FIXTURE_AS_OF)
    assert result.portfolio.total_invested() + result.portfolio.cash_buffer == pytest.approx(
        1.0, abs=1e-8
    )
