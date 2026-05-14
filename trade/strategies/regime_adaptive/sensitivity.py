"""Lightweight parameter sensitivity sweep for the regime-adaptive research path.

Runs a deterministic, single-process, one-at-a-time sweep over six canonical parameter
knobs (target volatility, regime fast / slow vol windows, regime crisis ratio, tolerance
band, trend window) with three literature-aligned values each. Every variation re-runs the
regime-adaptive monthly backtest on the supplied (synthetic or research) records and
collects core summary metrics. No network, no environment variables, no AI / broker SDK
imports. The artifact is research-only and never authorizes any paper or production order
flow.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from pathlib import Path

from trade.backtest.monthly import BacktestParameters
from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.backtest import (
    run_regime_adaptive_monthly_backtest,
)
from trade.strategies.regime_adaptive.config import RegimeAdaptiveConfig

DEFAULT_SWEEP_SPECIFICATION: Mapping[str, tuple[float, ...]] = {
    "target_volatility": (0.06, 0.08, 0.10),
    "regime_fast_vol_window_days": (15, 20, 30),
    "regime_slow_vol_window_days": (90, 120, 180),
    "regime_crisis_ratio": (1.3, 1.5, 1.8),
    "tolerance_band": (0.00, 0.03, 0.05),
    "trend_window_days": (150, 200, 250),
}

SUPPORTED_PARAMETERS = frozenset(DEFAULT_SWEEP_SPECIFICATION.keys())

RESEARCH_ONLY_DISCLAIMER = (
    "research-only sensitivity sweep; not a trading instruction. The regime-adaptive "
    "strategy never authorizes any paper or production order flow."
)


@dataclass(frozen=True, slots=True)
class SensitivityVariation:
    parameter: str
    value: float
    ending_value: float
    max_drawdown: float
    cagr: float
    turnover: float
    total_cost: float
    rebalance_count: int


@dataclass(frozen=True, slots=True)
class SensitivitySweepResult:
    base_config_hash: str
    variations: tuple[SensitivityVariation, ...]
    generated_at: datetime
    json_path: Path | None
    markdown_path: Path | None
    sweep_specification: Mapping[str, tuple[float, ...]] = field(default_factory=dict)


def run_regime_adaptive_sensitivity_sweep(
    *,
    records: tuple[PriceBar, ...],
    signal_dates: tuple[date, ...],
    base_config: RegimeAdaptiveConfig,
    backtest_parameters: BacktestParameters | None = None,
    sweep_specification: Mapping[str, tuple[float, ...]] | None = None,
    output_dir: Path | None = None,
    run_id: str | None = None,
) -> SensitivitySweepResult:
    if sweep_specification is None:
        sweep_specification = DEFAULT_SWEEP_SPECIFICATION
    unknown = set(sweep_specification) - SUPPORTED_PARAMETERS
    if unknown:
        raise ValueError(f"unknown sweep parameters: {sorted(unknown)}")
    backtest_parameters = backtest_parameters or BacktestParameters()
    variations: list[SensitivityVariation] = []
    for parameter, values in sweep_specification.items():
        for value in values:
            variant_config = _replace_parameter(base_config, parameter, value)
            result = run_regime_adaptive_monthly_backtest(
                records,
                signal_dates,
                variant_config,
                backtest_parameters,
            )
            equity_values = tuple(point.value for point in result.equity_curve)
            max_drawdown = _max_drawdown(equity_values)
            cagr = (
                (result.ending_value / result.starting_capital)
                ** (12.0 / max(len(equity_values) - 1, 1))
                - 1.0
            )
            variations.append(
                SensitivityVariation(
                    parameter=parameter,
                    value=float(value),
                    ending_value=result.ending_value,
                    max_drawdown=max_drawdown,
                    cagr=cagr,
                    turnover=result.turnover,
                    total_cost=result.cost_amount,
                    rebalance_count=len(result.rebalance_results),
                )
            )

    generated_at = datetime.now(UTC).replace(microsecond=0)
    json_path: Path | None = None
    markdown_path: Path | None = None
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        run_label = run_id or generated_at.strftime("%Y%m%dT%H%M%S")
        json_path = output_dir / f"regime-adaptive-sensitivity-{run_label}.json"
        markdown_path = output_dir / f"regime-adaptive-sensitivity-{run_label}.md"
        payload = _serialize_payload(
            base_config=base_config,
            variations=variations,
            generated_at=generated_at,
            sweep_specification=sweep_specification,
        )
        json_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        markdown_path.write_text(_render_markdown(payload), encoding="utf-8")

    return SensitivitySweepResult(
        base_config_hash=base_config.parameter_hash(),
        variations=tuple(variations),
        generated_at=generated_at,
        json_path=json_path,
        markdown_path=markdown_path,
        sweep_specification=dict(sweep_specification),
    )


def _replace_parameter(
    config: RegimeAdaptiveConfig, parameter: str, value: float
) -> RegimeAdaptiveConfig:
    if parameter == "target_volatility":
        return replace(config, target_volatility=float(value))
    if parameter == "regime_fast_vol_window_days":
        return replace(config, regime_fast_vol_window_days=int(value))
    if parameter == "regime_slow_vol_window_days":
        return replace(config, regime_slow_vol_window_days=int(value))
    if parameter == "regime_crisis_ratio":
        return replace(config, regime_crisis_ratio=float(value))
    if parameter == "tolerance_band":
        return replace(config, tolerance_band=float(value))
    if parameter == "trend_window_days":
        return replace(config, trend_window_days=int(value))
    raise ValueError(f"unsupported parameter: {parameter}")


def _max_drawdown(values: tuple[float, ...]) -> float:
    if not values:
        return 0.0
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1.0)
    return max_drawdown


def _serialize_payload(
    *,
    base_config: RegimeAdaptiveConfig,
    variations: list[SensitivityVariation],
    generated_at: datetime,
    sweep_specification: Mapping[str, tuple[float, ...]],
) -> dict[str, object]:
    return {
        "base_config_hash": base_config.parameter_hash(),
        "base_config": {
            "strategy_id": base_config.strategy_id,
            "trend_window_days": base_config.trend_window_days,
            "vol_lookback_days": base_config.vol_lookback_days,
            "target_volatility": base_config.target_volatility,
            "regime_fast_vol_window_days": base_config.regime_fast_vol_window_days,
            "regime_slow_vol_window_days": base_config.regime_slow_vol_window_days,
            "regime_crisis_ratio": base_config.regime_crisis_ratio,
            "regime_crisis_exposure_scale": base_config.regime_crisis_exposure_scale,
            "tolerance_band": base_config.tolerance_band,
            "account_drawdown_threshold": base_config.account_drawdown_threshold,
            "max_exposure": base_config.max_exposure,
            "defensive_symbol": base_config.defensive_symbol,
        },
        "sweep_specification": {
            parameter: list(values) for parameter, values in sweep_specification.items()
        },
        "generated_at": generated_at.isoformat(),
        "variations": [
            {
                "parameter": variation.parameter,
                "value": variation.value,
                "ending_value": variation.ending_value,
                "max_drawdown": variation.max_drawdown,
                "cagr": variation.cagr,
                "turnover": variation.turnover,
                "total_cost": variation.total_cost,
                "rebalance_count": variation.rebalance_count,
            }
            for variation in variations
        ],
        "disclaimer": RESEARCH_ONLY_DISCLAIMER,
    }


def _render_markdown(payload: dict[str, object]) -> str:
    variations = payload["variations"]
    if not isinstance(variations, list):
        variations = []
    header = (
        "| Parameter | Value | Ending value | Max drawdown | CAGR | "
        "Turnover | Total cost | Rebalances |"
    )
    lines: list[str] = [
        "# Regime-Adaptive Sensitivity Sweep",
        "",
        f"- Generated at: {payload.get('generated_at')}",
        f"- Base config hash: {payload.get('base_config_hash')}",
        "",
        "## Variations",
        "",
        header,
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variation in variations:
        if not isinstance(variation, dict):
            continue
        lines.append(
            "| {parameter} | {value} | {ending_value} | {max_drawdown} | "
            "{cagr} | {turnover} | {total_cost} | {rebalance_count} |".format(**variation)
        )
    lines.extend(
        [
            "",
            "## Research Limitations",
            f"- {payload.get('disclaimer')}",
        ]
    )
    return "\n".join(lines)
