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
    """POST /api/backtests/run + GET /api/backtests/{run_id} payload (B047 async).

    ``POST /run`` enqueues a ``backtest_run`` and returns ``202`` with
    ``status='queued'`` and no result yet; the frontend polls ``GET /{run_id}``
    until ``status='done'`` (result populated) or ``'error'`` (``error`` set).
    The heavy result fields are nullable / empty while ``queued`` / ``running``.
    """

    run_id: str
    status: str = Field(description="'queued' / 'running' / 'done' / 'error'.")
    metrics: BacktestMetrics | None = None
    equity: list[EquitySample] = Field(default_factory=list)
    allocations: list[AllocationBar] = Field(default_factory=list)
    trades: list[BacktestTrade] = Field(default_factory=list)
    report_markdown: str | None = None
    explanation: str | None = Field(
        default=None,
        description=(
            "B043 — grounded LLM 'why this Sharpe/drawdown' explanation generated "
            "off the request path; null when the LLM refused / was over budget / "
            "unavailable (the frontend then shows the report only)."
        ),
    )
    error: str | None = None
    error_kind: str | None = Field(
        default=None,
        description=(
            "B047-OPS2 — structured failure code (insufficient_history / "
            "no_signal_dates / data_unavailable / unknown); the frontend maps it "
            "to a bilingual friendly message instead of showing ``error``."
        ),
    )


class BacktestDataRangeResponse(BaseModel):
    """GET /api/backtests/data-range payload (B047-OPS2 F001).

    The real backtest data-coverage window the data-refresh job recorded. The
    frontend uses it to pick a valid default range (``end=data_end``,
    ``start=max(min_usable_start, data_end−1y)``) and clamp the date picker. All
    fields are ``null`` when no data-refresh has run yet (empty state)."""

    data_start: str | None = Field(default=None, description="Earliest ISO date in coverage.")
    data_end: str | None = Field(default=None, description="Latest ISO date in coverage.")
    min_usable_start: str | None = Field(
        default=None,
        description="Earliest ISO start a backtest may use (lookback-safe floor).",
    )
