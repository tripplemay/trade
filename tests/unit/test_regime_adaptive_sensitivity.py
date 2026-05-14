import ast
import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from trade.backtest.monthly import BacktestParameters
from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.config import (
    ASSET_CATEGORY_DEFENSIVE,
    default_regime_adaptive_config,
)
from trade.strategies.regime_adaptive.sensitivity import (
    DEFAULT_SWEEP_SPECIFICATION,
    SensitivitySweepResult,
    SensitivityVariation,
    run_regime_adaptive_sensitivity_sweep,
)


def _bars(symbol: str, prices: list[float], start: date = date(2024, 1, 1)) -> list[PriceBar]:
    return [
        PriceBar(
            date=start + timedelta(days=index),
            symbol=symbol,
            open=price * 0.999,
            close=price,
            adjusted_close=price,
            volume=1_000,
        )
        for index, price in enumerate(prices)
    ]


def _rising(length: int, start: float = 100.0, step: float = 0.5) -> list[float]:
    return [start + step * index for index in range(length)]


def _records(length: int = 120) -> tuple[PriceBar, ...]:
    config = default_regime_adaptive_config()
    rows: list[PriceBar] = []
    for index, entry in enumerate(config.universe):
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            rows.extend(_bars(entry.symbol, _rising(length, start=100.0, step=0.0)))
            continue
        rows.extend(_bars(entry.symbol, _rising(length, start=100.0, step=0.1 + 0.02 * index)))
    return tuple(rows)


def _short_config() -> object:
    return replace(
        default_regime_adaptive_config(),
        trend_window_days=20,
        vol_lookback_days=60,
        regime_fast_vol_window_days=10,
        regime_slow_vol_window_days=40,
    )


def _short_sweep_specification() -> dict[str, tuple[float, ...]]:
    return {
        "target_volatility": (0.06, 0.08, 0.10),
        "regime_fast_vol_window_days": (5, 10, 15),
        "regime_slow_vol_window_days": (20, 40, 60),
        "regime_crisis_ratio": (1.3, 1.5, 1.8),
        "tolerance_band": (0.00, 0.03, 0.05),
        "trend_window_days": (15, 20, 25),
    }


def test_default_sweep_specification_covers_six_canonical_parameters() -> None:
    assert set(DEFAULT_SWEEP_SPECIFICATION) == {
        "target_volatility",
        "regime_fast_vol_window_days",
        "regime_slow_vol_window_days",
        "regime_crisis_ratio",
        "tolerance_band",
        "trend_window_days",
    }
    for values in DEFAULT_SWEEP_SPECIFICATION.values():
        assert len(values) == 3


def test_run_regime_adaptive_sensitivity_sweep_returns_variations(tmp_path: Path) -> None:
    records = _records()
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    result = run_regime_adaptive_sensitivity_sweep(
        records=records,
        signal_dates=signal_dates,
        base_config=_short_config(),
        backtest_parameters=BacktestParameters(starting_capital=100_000.0),
        sweep_specification=_short_sweep_specification(),
        output_dir=tmp_path,
        run_id="sweep-1",
    )

    assert isinstance(result, SensitivitySweepResult)
    assert all(isinstance(variation, SensitivityVariation) for variation in result.variations)
    assert len(result.variations) == sum(
        len(values) for values in _short_sweep_specification().values()
    )


def test_sensitivity_variations_carry_parameter_and_value() -> None:
    records = _records()
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    result = run_regime_adaptive_sensitivity_sweep(
        records=records,
        signal_dates=signal_dates,
        base_config=_short_config(),
        sweep_specification=_short_sweep_specification(),
    )

    by_parameter: dict[str, set[float]] = {}
    for variation in result.variations:
        by_parameter.setdefault(variation.parameter, set()).add(float(variation.value))
    for parameter, values in _short_sweep_specification().items():
        assert by_parameter[parameter] == set(float(value) for value in values)


def test_sensitivity_sweep_is_deterministic_across_runs(tmp_path: Path) -> None:
    records = _records()
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    first = run_regime_adaptive_sensitivity_sweep(
        records=records,
        signal_dates=signal_dates,
        base_config=_short_config(),
        sweep_specification=_short_sweep_specification(),
    )
    second = run_regime_adaptive_sensitivity_sweep(
        records=records,
        signal_dates=signal_dates,
        base_config=_short_config(),
        sweep_specification=_short_sweep_specification(),
    )

    assert [
        (variation.parameter, variation.value, variation.ending_value, variation.max_drawdown)
        for variation in first.variations
    ] == [
        (variation.parameter, variation.value, variation.ending_value, variation.max_drawdown)
        for variation in second.variations
    ]


def test_sensitivity_sweep_writes_json_and_markdown(tmp_path: Path) -> None:
    records = _records()
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    result = run_regime_adaptive_sensitivity_sweep(
        records=records,
        signal_dates=signal_dates,
        base_config=_short_config(),
        sweep_specification=_short_sweep_specification(),
        output_dir=tmp_path,
        run_id="sweep-out",
    )

    assert result.json_path is not None
    assert result.markdown_path is not None
    assert result.json_path.exists()
    assert result.markdown_path.exists()
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert payload["variations"]
    assert payload["base_config_hash"] == result.base_config_hash


def test_sensitivity_sweep_does_not_open_socket(tmp_path: Path, monkeypatch: Any) -> None:
    def _refuse_socket(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("network access is not allowed during sensitivity sweep")

    monkeypatch.setattr("socket.socket", _refuse_socket)
    records = _records()
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    result = run_regime_adaptive_sensitivity_sweep(
        records=records,
        signal_dates=signal_dates,
        base_config=_short_config(),
        sweep_specification=_short_sweep_specification(),
        output_dir=tmp_path,
        run_id="offline",
    )
    assert len(result.variations) > 0


def test_sensitivity_sweep_module_does_not_import_forbidden_dependencies() -> None:
    source_path = (
        Path(__file__).resolve().parents[2]
        / "trade"
        / "strategies"
        / "regime_adaptive"
        / "sensitivity.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    forbidden = {
        "alpaca",
        "alpaca_trade_api",
        "futu",
        "futu_api",
        "ib_insync",
        "openai",
        "anthropic",
        "google.generativeai",
        "langchain",
        "polygon",
        "requests",
        "socket",
        "tiger",
        "tiger_api",
        "tradier",
        "urllib.request",
        "yfinance",
    }
    assert forbidden.isdisjoint(imports)


def test_sensitivity_sweep_runs_quickly_on_synthetic_fixture() -> None:
    import time

    records = _records()
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    start = time.monotonic()
    result = run_regime_adaptive_sensitivity_sweep(
        records=records,
        signal_dates=signal_dates,
        base_config=_short_config(),
        sweep_specification=_short_sweep_specification(),
    )
    duration = time.monotonic() - start

    assert duration < 10.0
    assert len(result.variations) > 0


def test_sensitivity_sweep_uses_default_specification_when_none_supplied() -> None:
    """When no sweep_specification is passed, the default 6-knob grid drives the run."""

    records = _records()
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    short_default = {
        "target_volatility": (0.05, 0.08, 0.12),
        "regime_fast_vol_window_days": (5, 10, 20),
        "regime_slow_vol_window_days": (15, 40, 80),
        "regime_crisis_ratio": (1.2, 1.5, 2.0),
        "tolerance_band": (0.00, 0.04, 0.08),
        "trend_window_days": (15, 25, 35),
    }
    result = run_regime_adaptive_sensitivity_sweep(
        records=records,
        signal_dates=signal_dates,
        base_config=_short_config(),
        sweep_specification=short_default,
    )

    assert {variation.parameter for variation in result.variations} == set(short_default)


def test_sensitivity_sweep_handles_no_output_dir() -> None:
    """When output_dir is None, the sweep runs but writes nothing."""

    records = _records()
    signal_dates = (date(2024, 3, 20), date(2024, 4, 19))

    result = run_regime_adaptive_sensitivity_sweep(
        records=records,
        signal_dates=signal_dates,
        base_config=_short_config(),
        sweep_specification=_short_sweep_specification(),
        output_dir=None,
    )

    assert result.json_path is None
    assert result.markdown_path is None
    assert len(result.variations) > 0


def test_sensitivity_sweep_rejects_unknown_parameter_in_specification() -> None:
    records = _records()
    signal_dates = (date(2024, 3, 20),)

    with pytest.raises(ValueError, match="unknown"):
        run_regime_adaptive_sensitivity_sweep(
            records=records,
            signal_dates=signal_dates,
            base_config=_short_config(),
            sweep_specification={"unknown_parameter": (0.1, 0.2, 0.3)},
        )
