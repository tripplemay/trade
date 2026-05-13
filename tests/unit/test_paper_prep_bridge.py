from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from trade.backtest.master_portfolio import (
    MasterChildStrategyParameters,
    run_master_portfolio_quarterly_backtest,
)
from trade.backtest.monthly import BacktestParameters, run_multi_monthly_backtest
from trade.backtest.risk_parity import run_risk_parity_monthly_backtest
from trade.data.loader import PriceBar
from trade.paper_prep.bridge import (
    BridgeError,
    generate_target_positions_from_master,
    generate_target_positions_from_strategy,
)
from trade.paper_prep.mock_broker import default_account_state
from trade.paper_prep.target_positions import (
    DISCLAIMER,
    SCHEMA_VERSION,
    AccountState,
    validate_target_positions,
)
from trade.portfolio.master import (
    SLEEVE_TYPE_IMPLEMENTED,
    MasterPortfolioParameters,
    MasterSleeveConfig,
)
from trade.strategies.global_etf_momentum import MomentumParameters, MomentumWindow
from trade.strategies.risk_parity import RiskParityParameters

Q1_END = date(2024, 3, 31)
Q2_END = date(2024, 6, 30)
Q3_END = date(2024, 9, 30)
MULTI_QUARTER_DAYS = 275


def _short_momentum_params() -> MomentumParameters:
    return MomentumParameters(
        top_n=1,
        defensive_asset="AGG",
        momentum_windows=(MomentumWindow(periods=2, weight=1.0),),
        trend_window=2,
    )


def _short_risk_parity_params() -> RiskParityParameters:
    return RiskParityParameters(
        universe=("SPY", "VEA", "AGG", "GLD", "SGOV"),
        volatility_lookback=60,
        defensive_asset="SGOV",
        target_volatility=0.5,
    )


def _synthetic_daily_universe(
    symbols: tuple[str, ...], observations: int
) -> tuple[PriceBar, ...]:
    start = date(2024, 1, 1)
    records: list[PriceBar] = []
    for symbol_index, symbol in enumerate(symbols):
        price = 100.0 + symbol_index * 10.0
        for index in range(observations):
            if index:
                price *= 1.0 + (0.003 * (symbol_index + 1) if index % 2 else -0.002)
            records.append(
                PriceBar(
                    date=start + timedelta(days=index),
                    symbol=symbol,
                    open=price * 0.999,
                    close=price,
                    adjusted_close=price,
                    volume=1000,
                )
            )
    return tuple(records)


def _fixed_clock(value: datetime) -> Any:
    def clock() -> datetime:
        return value

    return clock


def _master_result() -> Any:
    records = _synthetic_daily_universe(
        ("SPY", "VEA", "AGG", "GLD", "SGOV"), MULTI_QUARTER_DAYS
    )
    return run_master_portfolio_quarterly_backtest(
        records,
        (Q1_END, Q2_END, Q3_END),
        child_parameters=MasterChildStrategyParameters(
            momentum=_short_momentum_params(),
            risk_parity=_short_risk_parity_params(),
        ),
        backtest_parameters=BacktestParameters(
            starting_capital=100_000.0, cost_bps=1.0, slippage_bps=2.0
        ),
    )


def _momentum_result() -> Any:
    records = _synthetic_daily_universe(
        ("SPY", "VEA", "AGG", "GLD", "SGOV"), MULTI_QUARTER_DAYS
    )
    return run_multi_monthly_backtest(
        records,
        (Q1_END, Q2_END, Q3_END),
        _short_momentum_params(),
    )


def _risk_parity_result() -> Any:
    records = _synthetic_daily_universe(
        ("SPY", "VEA", "AGG", "GLD", "SGOV"), MULTI_QUARTER_DAYS
    )
    return run_risk_parity_monthly_backtest(
        records,
        (Q1_END, Q2_END, Q3_END),
        _short_risk_parity_params(),
        BacktestParameters(starting_capital=100_000.0, cost_bps=1.0, slippage_bps=2.0),
    )


def test_bridge_from_master_defaults_to_latest_period() -> None:
    positions = generate_target_positions_from_master(
        _master_result(),
        account_state=default_account_state(),
        snapshot_id="fixture:master-test",
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    assert positions.signal_date == Q3_END
    assert positions.portfolio_id == "master_portfolio_mvp"
    assert positions.strategy_id is None
    assert positions.schema_version == SCHEMA_VERSION
    assert positions.disclaimer == DISCLAIMER
    validate_target_positions(positions, default_account_state())


def test_bridge_from_master_accepts_explicit_signal_date_matching_a_period() -> None:
    positions = generate_target_positions_from_master(
        _master_result(),
        account_state=default_account_state(),
        signal_date=Q1_END,
        snapshot_id="fixture:master-test",
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    assert positions.signal_date == Q1_END


def test_bridge_from_master_fails_closed_on_signal_date_not_in_backtest() -> None:
    with pytest.raises(BridgeError, match="signal_date"):
        generate_target_positions_from_master(
            _master_result(),
            account_state=default_account_state(),
            signal_date=date(2024, 5, 15),
            snapshot_id="fixture:master-test",
            clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
        )


def test_bridge_from_master_routes_defensive_residual_to_master_defensive_asset() -> None:
    positions = generate_target_positions_from_master(
        _master_result(),
        account_state=default_account_state(),
        snapshot_id="fixture:master-test",
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    assert positions.defensive_allocation.symbol == "SGOV"
    total_weight = (
        sum(entry.target_weight for entry in positions.entries)
        + positions.defensive_allocation.weight
    )
    assert round(total_weight, 8) == 1.0


def test_bridge_from_master_dollar_exposure_uses_account_capacity() -> None:
    account = AccountState(
        account_state_id="research-account-default",
        cash=400_000.0,
        equity_value=100_000.0,
        open_positions={},
    )
    positions = generate_target_positions_from_master(
        _master_result(),
        account_state=account,
        snapshot_id="fixture:master-test",
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    total_dollar = (
        sum(entry.target_dollar_exposure for entry in positions.entries)
        + positions.defensive_allocation.dollar_exposure
    )
    assert total_dollar == pytest.approx(500_000.0)


def test_bridge_from_master_target_positions_id_is_deterministic() -> None:
    clock = _fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC))
    first = generate_target_positions_from_master(
        _master_result(),
        account_state=default_account_state(),
        snapshot_id="fixture:master-test",
        clock=clock,
    )
    second = generate_target_positions_from_master(
        _master_result(),
        account_state=default_account_state(),
        snapshot_id="fixture:master-test",
        clock=clock,
    )
    assert first.target_positions_id == second.target_positions_id


def test_bridge_from_strategy_supports_momentum_result() -> None:
    positions = generate_target_positions_from_strategy(
        _momentum_result(),
        account_state=default_account_state(),
        snapshot_id="fixture:momentum-test",
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    assert positions.signal_date == Q3_END
    assert positions.strategy_id == "global_etf_momentum"
    assert positions.portfolio_id is None
    validate_target_positions(positions, default_account_state())


def test_bridge_from_strategy_supports_risk_parity_result() -> None:
    positions = generate_target_positions_from_strategy(
        _risk_parity_result(),
        account_state=default_account_state(),
        snapshot_id="fixture:rp-test",
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    assert positions.signal_date == Q3_END
    assert positions.strategy_id == "risk_parity_vol_target"
    assert positions.portfolio_id is None
    validate_target_positions(positions, default_account_state())


def test_bridge_from_strategy_fails_closed_on_signal_date_not_in_backtest() -> None:
    with pytest.raises(BridgeError, match="signal_date"):
        generate_target_positions_from_strategy(
            _risk_parity_result(),
            account_state=default_account_state(),
            signal_date=date(2024, 12, 31),
            snapshot_id="fixture:rp-test",
            clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
        )


def test_bridge_from_strategy_rejects_unsupported_result_type() -> None:
    with pytest.raises(BridgeError, match="unsupported"):
        generate_target_positions_from_strategy(
            object(),  # type: ignore[arg-type]
            account_state=default_account_state(),
            snapshot_id="x",
            clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
        )


def test_bridge_research_limitations_include_research_only_when_default() -> None:
    positions = generate_target_positions_from_master(
        _master_result(),
        account_state=default_account_state(),
        snapshot_id="fixture:master-test",
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    assert any("research-only" in entry.lower() for entry in positions.research_limitations)


def test_bridge_from_master_dollar_exposures_never_exceed_account_capacity() -> None:
    """Total dollar exposure equals account capacity exactly (no leverage)."""

    account = AccountState(
        account_state_id="research-account-default",
        cash=1_000.0,
        equity_value=0.0,
        open_positions={},
    )
    positions = generate_target_positions_from_master(
        _master_result(),
        account_state=account,
        snapshot_id="fixture:master-test",
        clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
    )

    total_dollar = (
        sum(entry.target_dollar_exposure for entry in positions.entries)
        + positions.defensive_allocation.dollar_exposure
    )
    assert total_dollar == pytest.approx(account.cash + account.equity_value)


def test_bridge_from_master_handles_empty_rebalance_results() -> None:
    """An empty master rebalance_results must fail closed instead of crashing."""
    records = _synthetic_daily_universe(("SPY", "AGG", "SGOV"), MULTI_QUARTER_DAYS)
    custom = MasterPortfolioParameters(
        sleeves=(
            MasterSleeveConfig(
                sleeve_id="rp",
                sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
                strategy_id="risk_parity_vol_target",
                planning_weight=1.0,
                role_label="core",
            ),
        ),
        defensive_asset="SGOV",
    )
    # Only run on Q3 so we have a single rebalance, then truncate via internal expectation.
    result = run_master_portfolio_quarterly_backtest(
        records,
        (Q1_END,),
        master_parameters=custom,
        child_parameters=MasterChildStrategyParameters(
            risk_parity=RiskParityParameters(
                universe=("SPY", "SGOV"),
                volatility_lookback=60,
                defensive_asset="SGOV",
                target_volatility=2.0,
            )
        ),
    )
    # Build a fake empty result to assert the closed-fail path.
    from dataclasses import replace as dc_replace

    empty_result = dc_replace(result, rebalance_results=())
    with pytest.raises(BridgeError, match="rebalance"):
        generate_target_positions_from_master(
            empty_result,
            account_state=default_account_state(),
            snapshot_id="fixture:master-test",
            clock=_fixed_clock(datetime(2026, 5, 13, 0, 0, 0, tzinfo=UTC)),
        )
