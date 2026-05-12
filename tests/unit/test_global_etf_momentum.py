import pytest

from trade.data.loader import load_fixture_prices
from trade.strategies.global_etf_momentum import (
    MomentumParameters,
    MomentumWindow,
    generate_momentum_signal,
)


def test_signal_ranks_assets_by_weighted_momentum() -> None:
    snapshot = load_fixture_prices()
    signal = generate_momentum_signal(snapshot.records)

    ranked_symbols = [asset.symbol for asset in signal.ranked_assets]

    assert ranked_symbols == ["SPY", "EEM", "VEA"]


def test_trend_filter_excludes_negative_assets() -> None:
    snapshot = load_fixture_prices()
    signal = generate_momentum_signal(snapshot.records)

    by_symbol = {asset.symbol: asset for asset in signal.ranked_assets}


    assert by_symbol["SPY"].passed_trend_filter is True
    assert by_symbol["EEM"].passed_trend_filter is True
    assert by_symbol["VEA"].passed_trend_filter is False
    assert by_symbol["VEA"].trend_return < 0


def test_defensive_asset_gets_unfilled_top_n_slots() -> None:
    snapshot = load_fixture_prices()
    parameters = MomentumParameters(top_n=3)
    signal = generate_momentum_signal(snapshot.records, parameters)

    assert signal.selected_assets == ("SPY", "EEM")
    assert signal.target_weights == {
        "EEM": pytest.approx(1 / 3),
        "SPY": pytest.approx(1 / 3),
        "AGG": pytest.approx(1 / 3),
    }
    assert signal.defensive_weight == pytest.approx(1 / 3)


def test_parameters_are_recorded_with_stable_hash() -> None:
    snapshot = load_fixture_prices()
    parameters = MomentumParameters(
        top_n=1,
        defensive_asset="AGG",
        momentum_windows=(MomentumWindow(periods=3, weight=1.0),),
        trend_window=2,
    )
    first = generate_momentum_signal(snapshot.records, parameters)
    second = generate_momentum_signal(snapshot.records, parameters)

    assert first.parameters == parameters
    assert first.parameter_hash == second.parameter_hash
    assert len(first.parameter_hash) == 64
