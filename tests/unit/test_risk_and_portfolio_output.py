from datetime import date

from trade.backtest.monthly import run_monthly_backtest
from trade.data.loader import load_fixture_prices
from trade.portfolio.output import build_portfolio_output
from trade.risk.checks import calculate_drawdown, evaluate_risk
from trade.strategies.global_etf_momentum import MomentumParameters, MomentumWindow


def test_position_limit_violation_is_flagged() -> None:
    result = evaluate_risk(
        {"SPY": 0.5, "AGG": 0.5},
        (100.0, 105.0),
        defensive_asset="AGG",
        max_single_etf_weight=0.35,
    )

    assert "position_limit_violation:SPY:0.5000>0.3500" in result.risk_flags


def test_defensive_switch_is_marked() -> None:
    result = evaluate_risk({"SPY": 0.5, "AGG": 0.5}, (100.0, 101.0), "AGG")

    assert result.defensive_switch is True
    assert "defensive_asset_active:AGG" in result.risk_flags


def test_drawdown_stats_are_calculated() -> None:
    drawdown = calculate_drawdown((100.0, 120.0, 90.0, 110.0))

    assert round(drawdown.max_drawdown, 6) == -0.25
    assert round(drawdown.ending_drawdown, 6) == round(110.0 / 120.0 - 1.0, 6)


def test_portfolio_output_contains_pm_compatible_fields() -> None:
    parameters = MomentumParameters(
        top_n=1,
        momentum_windows=(MomentumWindow(periods=2, weight=1.0),),
        trend_window=2,
    )
    backtest = run_monthly_backtest(
        load_fixture_prices().records,
        parameters,
        signal_date=date(2024, 10, 31),
    )
    output = build_portfolio_output(backtest, strategy_budget=0.4)

    assert output.strategy_id == "global_etf_momentum"
    assert output.strategy_budget == 0.4
    assert output.target_weights == {"SPY": 1.0}
    assert output.drawdown <= 0
    assert "position_limit_violation:SPY:1.0000>0.3500" in output.risk_flags
