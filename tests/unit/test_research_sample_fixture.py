from pathlib import Path

from trade.backtest.monthly import run_multi_monthly_backtest
from trade.data.loader import load_fixture_prices
from trade.strategies.global_etf_momentum import MomentumParameters, MomentumWindow


def test_research_sample_fixture_covers_expanded_assets_and_drawdown() -> None:
    sample_path = Path("trade/data/fixtures/research_sample_prices.json")
    snapshot = load_fixture_prices(sample_path)

    assert snapshot.source == "synthetic-research-sample-v1"
    assert snapshot.symbols == ("AGG", "GLD", "QQQ", "SGOV", "SPY", "VEA")
    assert snapshot.start_date.isoformat() == "2024-01-31"
    assert snapshot.end_date.isoformat() == "2024-07-31"


def test_research_sample_backtest_has_non_monotonic_equity_curve_and_rotation() -> None:
    sample_path = Path("trade/data/fixtures/research_sample_prices.json")
    snapshot = load_fixture_prices(sample_path)
    parameters = MomentumParameters(
        top_n=2,
        defensive_asset="SGOV",
        momentum_windows=(MomentumWindow(periods=2, weight=1.0),),
        trend_window=2,
    )
    result = run_multi_monthly_backtest(
        snapshot.records,
        tuple(sorted({record.date for record in snapshot.records}))[2:5],
        parameters,
    )
    values = [point.value for point in result.equity_curve]
    selected_assets = {
        symbol
        for rebalance in result.rebalance_results
        for symbol in rebalance.signal.selected_assets
    }

    assert any(later < earlier for earlier, later in zip(values, values[1:], strict=False))
    assert len(selected_assets) >= 2
    assert {"GLD", "QQQ", "SPY", "SGOV"} & selected_assets
