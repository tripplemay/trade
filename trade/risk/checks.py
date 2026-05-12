"""Basic MVP risk checks for backtest outputs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DrawdownStats:
    max_drawdown: float
    ending_drawdown: float


@dataclass(frozen=True, slots=True)
class RiskCheckResult:
    risk_flags: tuple[str, ...]
    warning_flags: tuple[str, ...]
    expected_warning_flags: tuple[str, ...]
    unexpected_warning_flags: tuple[str, ...]
    drawdown: DrawdownStats
    defensive_switch: bool


def evaluate_risk(
    target_weights: dict[str, float],
    equity_curve: tuple[float, ...],
    defensive_asset: str,
    max_single_etf_weight: float = 0.35,
    existing_flags: tuple[str, ...] = (),
    expected_warning_prefixes: tuple[str, ...] = (),
) -> RiskCheckResult:
    """Evaluate basic target-weight and drawdown risk flags."""

    flags = list(existing_flags)
    warning_flags: list[str] = []
    for symbol, weight in sorted(target_weights.items()):
        if symbol != defensive_asset and weight > max_single_etf_weight:
            warning_flags.append(
                f"position_limit_violation:{symbol}:{weight:.4f}>{max_single_etf_weight:.4f}"
            )

    defensive_switch = target_weights.get(defensive_asset, 0.0) > 0
    if defensive_switch:
        flags.append(f"defensive_asset_active:{defensive_asset}")

    flags.extend(warning_flags)
    expected_warnings = tuple(
        flag
        for flag in warning_flags
        if any(flag.startswith(prefix) for prefix in expected_warning_prefixes)
    )
    unexpected_warnings = tuple(flag for flag in warning_flags if flag not in expected_warnings)

    drawdown = calculate_drawdown(equity_curve)
    return RiskCheckResult(
        risk_flags=tuple(flags),
        warning_flags=tuple(warning_flags),
        expected_warning_flags=expected_warnings,
        unexpected_warning_flags=unexpected_warnings,
        drawdown=drawdown,
        defensive_switch=defensive_switch,
    )


def calculate_drawdown(equity_curve: tuple[float, ...]) -> DrawdownStats:
    if not equity_curve:
        raise ValueError("equity_curve must not be empty")
    high_watermark = equity_curve[0]
    max_drawdown = 0.0
    ending_drawdown = 0.0
    for value in equity_curve:
        if value <= 0:
            raise ValueError("equity_curve values must be positive")
        high_watermark = max(high_watermark, value)
        ending_drawdown = value / high_watermark - 1.0
        max_drawdown = min(max_drawdown, ending_drawdown)
    return DrawdownStats(max_drawdown=max_drawdown, ending_drawdown=ending_drawdown)
