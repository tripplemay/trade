"""B016 F003 — HRP wired into the B010 monthly backtest dispatcher.

Tests cover:

- End-to-end HRP path on a 9-asset synthetic fixture (B013 universe size).
- Inverse-vol path equivalence: dispatching default ``weighting_method`` runs
  the same signal pipeline as before (existing tests in
  ``test_risk_parity_config`` and ``test_risk_parity_backtest`` provide the
  authoritative bit-for-bit guarantee; here we add a sanity assertion that
  switching methods on the same fixture produces *different* target weights
  with both summing to ~1.0).
- Per-period rebalance trace records ``weighting_method`` for downstream
  reporting attribution (both the strategy summary and per-period entry).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from trade.backtest.monthly import BacktestParameters
from trade.backtest.risk_parity import run_risk_parity_monthly_backtest
from trade.data.loader import DataSnapshot, PriceBar
from trade.reporting.risk_parity import generate_risk_parity_reports
from trade.strategies.risk_parity import (
    RiskParityDataError,
    RiskParityParameters,
    generate_risk_parity_signal,
)

# --------------------------------------------------------------------------- #
# 9-asset synthetic universe (B013-size)
# --------------------------------------------------------------------------- #

_NINE_ASSET_UNIVERSE: tuple[str, ...] = (
    "SPY",
    "VEA",
    "VWO",
    "AGG",
    "IEF",
    "GLD",
    "VNQ",
    "DBC",
    "SGOV",
)


def _amplitude_for(symbol: str) -> float:
    """Distinct return amplitude per symbol to ensure non-degenerate variances."""

    return {
        "SPY": 0.018,
        "VEA": 0.020,
        "VWO": 0.025,
        "AGG": 0.006,
        "IEF": 0.007,
        "GLD": 0.012,
        "VNQ": 0.022,
        "DBC": 0.024,
        "SGOV": 0.0008,
    }[symbol]


def _phase_for(symbol: str) -> int:
    """Phase offset to introduce correlation structure across asset groups."""

    return {
        "SPY": 0,
        "VEA": 0,
        "VWO": 0,
        "AGG": 1,
        "IEF": 1,
        "GLD": 0,
        "VNQ": 0,
        "DBC": 1,
        "SGOV": 0,
    }[symbol]


def _nine_asset_history(observations: int = 90) -> tuple[PriceBar, ...]:
    """Synthetic OHLC history covering ``_NINE_ASSET_UNIVERSE``."""

    start = date(2024, 1, 1)
    bars: list[PriceBar] = []
    for index, symbol in enumerate(_NINE_ASSET_UNIVERSE):
        price = 100.0 + index
        amplitude = _amplitude_for(symbol)
        phase = _phase_for(symbol)
        for day in range(observations):
            if day:
                step = amplitude if (day + phase) % 2 == 0 else -amplitude * 0.95
                price *= 1.0 + step
            bars.append(
                PriceBar(
                    date=start + timedelta(days=day),
                    symbol=symbol,
                    open=price * 0.999,
                    close=price,
                    adjusted_close=price,
                    volume=1000,
                )
            )
    return tuple(bars)


def _nine_asset_snapshot(observations: int = 90) -> DataSnapshot:
    records = _nine_asset_history(observations)
    dates = tuple(sorted({record.date for record in records}))
    return DataSnapshot(
        records=records,
        source="unit-hrp-fixture",
        adjusted_price_policy="unit_adjusted_close",
        data_snapshot_id="fixture:b016-hrp-unit",
        checksum="c" * 64,
        start_date=dates[0],
        end_date=dates[-1],
        symbols=tuple(sorted(_NINE_ASSET_UNIVERSE)),
        trading_calendar_gaps=(),
    )


def _nine_asset_parameters(weighting_method: str = "inverse_volatility") -> RiskParityParameters:
    # Use the same universe and a 60-day lookback so the 90-day fixture has
    # enough returns for both methods.
    return RiskParityParameters(
        universe=_NINE_ASSET_UNIVERSE,
        volatility_lookback=60,
        defensive_asset="SGOV",
        target_volatility=1.0,  # avoid de-risking so the comparison sees the
        max_asset_weight=1.0,   # full HRP allocation without L2 / cap clipping
        weighting_method=weighting_method,  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------------- #
# HRP path end-to-end
# --------------------------------------------------------------------------- #


def test_hrp_signal_end_to_end_on_nine_asset_universe() -> None:
    records = _nine_asset_history()
    parameters = _nine_asset_parameters(weighting_method="hrp")

    signal = generate_risk_parity_signal(records, parameters, date(2024, 3, 10))

    # All 8 risk assets receive positive weight; defensive (SGOV) routed
    # via the L2/exposure layer.
    risk_symbols = tuple(s for s in _NINE_ASSET_UNIVERSE if s != "SGOV")
    for symbol in risk_symbols:
        assert symbol in signal.target_weights
        assert signal.target_weights[symbol] >= 0
    assert round(sum(signal.target_weights.values()), 8) == 1.0
    assert signal.parameters.weighting_method == "hrp"


def test_hrp_monthly_backtest_runs_end_to_end() -> None:
    records = _nine_asset_history()
    parameters = _nine_asset_parameters(weighting_method="hrp")
    signal_dates = (date(2024, 3, 10), date(2024, 3, 20))

    result = run_risk_parity_monthly_backtest(
        records,
        signal_dates,
        parameters,
        BacktestParameters(starting_capital=100_000.0, cost_bps=1.0, slippage_bps=2.0),
    )

    assert result.starting_capital == 100_000.0
    assert result.ending_value > 0
    assert len(result.rebalance_results) == 2
    assert result.parameters.weighting_method == "hrp"
    for period in result.rebalance_results:
        assert period.signal.parameters.weighting_method == "hrp"
        assert round(sum(period.signal.target_weights.values()), 8) == 1.0


def test_hrp_and_inverse_vol_paths_produce_different_weights() -> None:
    records = _nine_asset_history()
    inverse_vol_signal = generate_risk_parity_signal(
        records,
        _nine_asset_parameters(weighting_method="inverse_volatility"),
        date(2024, 3, 10),
    )
    hrp_signal = generate_risk_parity_signal(
        records,
        _nine_asset_parameters(weighting_method="hrp"),
        date(2024, 3, 10),
    )

    # Both produce valid normalised target weights summing to 1.
    assert round(sum(inverse_vol_signal.target_weights.values()), 8) == 1.0
    assert round(sum(hrp_signal.target_weights.values()), 8) == 1.0
    # But HRP's correlation-aware allocation differs from naive inverse-vol.
    common = set(inverse_vol_signal.target_weights) & set(hrp_signal.target_weights)
    assert any(
        abs(inverse_vol_signal.target_weights[symbol] - hrp_signal.target_weights[symbol]) > 1e-6
        for symbol in common
    )


def test_hrp_path_respects_max_asset_weight_cap() -> None:
    records = _nine_asset_history()
    parameters = RiskParityParameters(
        universe=_NINE_ASSET_UNIVERSE,
        volatility_lookback=60,
        defensive_asset="SGOV",
        target_volatility=1.0,
        max_asset_weight=0.20,
        weighting_method="hrp",
    )

    signal = generate_risk_parity_signal(records, parameters, date(2024, 3, 10))

    for symbol, weight in signal.target_weights.items():
        if symbol == parameters.defensive_asset:
            continue
        assert weight <= 0.20 + 1e-9, f"{symbol} weight {weight} exceeds cap"


def test_hrp_path_respects_target_volatility_scaling() -> None:
    records = _nine_asset_history()
    parameters = RiskParityParameters(
        universe=_NINE_ASSET_UNIVERSE,
        volatility_lookback=60,
        defensive_asset="SGOV",
        target_volatility=0.01,  # tight target → expect heavy defensive routing
        max_asset_weight=1.0,
        weighting_method="hrp",
    )

    signal = generate_risk_parity_signal(records, parameters, date(2024, 3, 10))

    assert 0 < signal.exposure_scale < 1.0
    assert signal.target_weights["SGOV"] > 0.0
    assert round(sum(signal.target_weights.values()), 8) == 1.0


def test_hrp_path_propagates_data_error_when_lookback_short() -> None:
    # 30-day fixture but lookback=60 → not enough returns for HRP.
    records = _nine_asset_history(observations=30)
    parameters = _nine_asset_parameters(weighting_method="hrp")

    with pytest.raises(RiskParityDataError):
        generate_risk_parity_signal(records, parameters, date(2024, 1, 20))


# --------------------------------------------------------------------------- #
# Inverse-vol path equivalence sanity
# --------------------------------------------------------------------------- #


def test_inverse_vol_path_unchanged_by_hrp_dispatcher() -> None:
    """Dispatching on the default 'inverse_volatility' value runs the same
    pipeline as before — the existing B010 tests provide the authoritative
    bit-for-bit guarantee; this is a fixture-level sanity check.
    """

    records = _nine_asset_history()
    signal_default = generate_risk_parity_signal(
        records, RiskParityParameters(
            universe=_NINE_ASSET_UNIVERSE,
            volatility_lookback=60,
            defensive_asset="SGOV",
            target_volatility=1.0,
            max_asset_weight=1.0,
        ), date(2024, 3, 10)
    )
    signal_explicit = generate_risk_parity_signal(
        records,
        _nine_asset_parameters(weighting_method="inverse_volatility"),
        date(2024, 3, 10),
    )

    assert signal_default.target_weights == signal_explicit.target_weights
    assert signal_default.exposure_scale == signal_explicit.exposure_scale
    assert signal_default.defensive_weight == signal_explicit.defensive_weight
    assert signal_default.parameters.weighting_method == "inverse_volatility"


# --------------------------------------------------------------------------- #
# Per-period rebalance trace records the active weighting_method
# --------------------------------------------------------------------------- #


def test_report_rebalance_trace_records_weighting_method_inverse_vol(
    tmp_path: Path,
) -> None:
    snapshot = _nine_asset_snapshot()
    parameters = _nine_asset_parameters(weighting_method="inverse_volatility")
    signal_dates = (date(2024, 3, 10), date(2024, 3, 20))

    result = run_risk_parity_monthly_backtest(
        snapshot.records, signal_dates, parameters
    )
    artifacts = generate_risk_parity_reports(result, snapshot, tmp_path, run_id="rp-iv")
    trace = artifacts.report["execution"]["rebalance_trace"]  # type: ignore[index]

    assert isinstance(trace, list)
    assert len(trace) == 2
    for entry in trace:
        assert entry["weighting_method"] == "inverse_volatility"


def test_report_rebalance_trace_records_weighting_method_hrp(tmp_path: Path) -> None:
    snapshot = _nine_asset_snapshot()
    parameters = _nine_asset_parameters(weighting_method="hrp")
    signal_dates = (date(2024, 3, 10), date(2024, 3, 20))

    result = run_risk_parity_monthly_backtest(
        snapshot.records, signal_dates, parameters
    )
    artifacts = generate_risk_parity_reports(result, snapshot, tmp_path, run_id="rp-hrp")
    trace = artifacts.report["execution"]["rebalance_trace"]  # type: ignore[index]

    assert isinstance(trace, list)
    assert len(trace) == 2
    for entry in trace:
        assert entry["weighting_method"] == "hrp"


def test_report_strategy_block_exposes_active_weighting_method(tmp_path: Path) -> None:
    snapshot = _nine_asset_snapshot()
    parameters = _nine_asset_parameters(weighting_method="hrp")

    result = run_risk_parity_monthly_backtest(
        snapshot.records, (date(2024, 3, 10),), parameters
    )
    artifacts = generate_risk_parity_reports(result, snapshot, tmp_path, run_id="rp-hrp-2")

    assert artifacts.report["strategy"]["weighting_method"] == "hrp"  # type: ignore[index]
