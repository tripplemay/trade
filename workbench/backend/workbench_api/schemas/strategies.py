"""Schemas for ``GET /api/strategies`` and ``GET /api/strategies/{id}`` (F007)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StrategyProvenance(BaseModel):
    """Where the strategy's definition lives in the repo."""

    spec_path: str = Field(description="docs/specs/<batch>.md path that defines the strategy.")
    code_path: str = Field(description="trade/<module>.py path that implements the strategy.")
    last_sweep_path: str | None = Field(
        default=None,
        description="Most recent parameter-sweep report path under docs/test-reports/, if any.",
    )


class StrategySummary(BaseModel):
    """List-view row for a strategy."""

    id: str = Field(description="Stable strategy id, e.g. 'B013-quarterly'.")
    name: str
    sleeve: str = Field(description="Sleeve assignment, e.g. 'momentum' / 'value' / 'carry'.")
    status: str = Field(description="Free-form, e.g. 'active' / 'paused' / 'retired'.")
    last_sweep_date: str | None = Field(default=None, description="ISO-8601.")


class PerformancePoint(BaseModel):
    """One (date, value) sample on a time series."""

    date: str
    value: float


class TurnoverCell(BaseModel):
    """One cell on the strategy's turnover heatmap (week × month)."""

    period: str = Field(description="ISO-8601 period label, e.g. '2025-Q3'.")
    bucket: str = Field(description="Bucket label, e.g. 'month-of-year' index or 'rebalance #'.")
    turnover: float = Field(description="Turnover ratio in [0, 1].")


class StrategyDetail(StrategySummary):
    """Detail view: summary + config + provenance + performance data."""

    config: dict[str, object] = Field(
        description="Strategy-specific config bag (passed verbatim to trade.master)."
    )
    provenance: StrategyProvenance
    equity_curve: list[PerformancePoint] = Field(default_factory=list)
    drawdown_series: list[PerformancePoint] = Field(default_factory=list)
    turnover_heatmap: list[TurnoverCell] = Field(default_factory=list)


class StrategyListResponse(BaseModel):
    """Wrapper so the response stays a JSON object (extensible)."""

    strategies: list[StrategySummary]
