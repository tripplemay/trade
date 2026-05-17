"""Schemas for the backtest endpoints (F008)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BacktestRunRequest(BaseModel):
    """POST /api/backtests/run body."""

    strategy_id: str
    snapshot_id: str = Field(description="SnapshotMeta.id from /api/snapshots.")
    start_date: str = Field(description="ISO-8601.")
    end_date: str = Field(description="ISO-8601.")
    parameters: dict[str, object] = Field(
        default_factory=dict,
        description="Strategy-specific overrides; merged into the locked spec defaults.",
    )


class BacktestMetrics(BaseModel):
    """Headline metrics for the result card stack."""

    cagr: float
    sharpe: float
    sortino: float | None = None
    max_drawdown: float
    turnover: float
    win_rate: float | None = None


class EquitySample(BaseModel):
    date: str
    nav: float
    benchmark_spy: float | None = None
    benchmark_6040: float | None = None


class AllocationBar(BaseModel):
    """One row in the allocation-history time series."""

    date: str
    weights: dict[str, float] = Field(description="Symbol → weight in [0, 1].")


class BacktestTrade(BaseModel):
    """One row in the trades AG Grid."""

    date: str
    symbol: str
    side: str = Field(description="'buy' or 'sell'.")
    quantity: float
    price: float
    notional: float


class BacktestRunResponse(BaseModel):
    """Full POST /api/backtests/run + GET /api/backtests/{run_id} payload."""

    run_id: str
    status: str = Field(description="'ok' / 'queued' / 'error'.")
    metrics: BacktestMetrics
    equity: list[EquitySample]
    allocations: list[AllocationBar]
    trades: list[BacktestTrade]
