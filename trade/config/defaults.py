"""Local/CI-safe default workflow configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trade.backtest.monthly import BacktestParameters
from trade.strategies.global_etf_momentum import MomentumParameters, MomentumWindow


@dataclass(frozen=True, slots=True)
class WorkflowConfig:
    environment: str
    strategy_budget: float
    strategy_parameters: MomentumParameters
    backtest_parameters: BacktestParameters
    snapshot_path: Path | None = None


def default_fixture_workflow_config() -> WorkflowConfig:
    return WorkflowConfig(
        environment="local",
        strategy_budget=0.4,
        strategy_parameters=MomentumParameters(
            top_n=2,
            momentum_windows=(
                MomentumWindow(periods=3, weight=0.4),
                MomentumWindow(periods=6, weight=0.3),
                MomentumWindow(periods=9, weight=0.3),
            ),
            trend_window=3,
        ),
        # B111 F004 fix-round — the fixture workflow deliberately pins the
        # LEGACY caliber (1bp+2bp) so its frozen CI outputs stay byte-identical
        # (provenance: these fixture artifacts predate the unified caliber in
        # trade/backtest/execution_caliber.py). Forward-looking runs use the
        # BacktestParameters defaults (5bp+5bp, unified).
        backtest_parameters=BacktestParameters(
            starting_capital=100_000.0,
            cost_bps=1.0,
            slippage_bps=2.0,
        ),
    )
