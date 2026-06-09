"""B047 F003 — async backtest request path (enqueue + read).

The request path is OFF the heavy ``trade`` stack (§12.10.2): ``run_backtest``
only validates the strategy + enqueues a ``backtest_run`` row and returns its
``run_id``; ``get_backtest`` only reads that row. The async worker
(``workbench_api/backtests/worker.py``) runs the real engine and writes the
result back — this module never imports ``trade``.

Replaces the B022 F008 ``_compute_synthetic_backtest`` deterministic stub.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from workbench_api.db.models.backtest_run import STATUS_QUEUED, BacktestRun
from workbench_api.db.repositories.backtest_data_window import (
    BacktestDataWindowRepository,
)
from workbench_api.db.repositories.backtest_run import BacktestRunRepository
from workbench_api.schemas.backtests import (
    AllocationBar,
    BacktestDataRangeResponse,
    BacktestMetrics,
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestTrade,
    EquitySample,
)
from workbench_api.services.strategies import get_strategy


class UnknownStrategyError(LookupError):
    """The supplied strategy_id is not in the registry."""


def run_backtest(session: Session, request: BacktestRunRequest) -> BacktestRunResponse:
    """Enqueue a backtest run and return ``{run_id, status: queued}``.

    Raises :class:`UnknownStrategyError` when the strategy_id is unknown. Does
    NOT import trade or run the engine — the worker picks the queued row up."""

    if get_strategy(request.strategy_id) is None:
        raise UnknownStrategyError(request.strategy_id)
    params: dict[str, Any] = {
        "snapshot_id": request.snapshot_id,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "parameters": request.parameters,
    }
    row = BacktestRunRepository(session).enqueue(
        strategy_id=request.strategy_id, params=params
    )
    session.commit()
    return BacktestRunResponse(run_id=row.run_id, status=STATUS_QUEUED)


def get_backtest(session: Session, run_id: str) -> BacktestRunResponse | None:
    """Read the current state of a backtest run; ``None`` when unknown.

    ``queued`` / ``running`` carry no result yet; ``done`` carries the mapped
    metrics/equity/allocations/trades + report; ``error`` carries the message."""

    row = BacktestRunRepository(session).get_by_run_id(run_id)
    if row is None:
        return None
    return _to_response(row)


def get_data_range(session: Session) -> BacktestDataRangeResponse:
    """Read the real data-coverage window (request-path, read-only).

    Reads the ``backtest_data_window`` singleton the data-refresh job writes —
    NEVER imports ``trade`` (§12.10.2). Returns all-``null`` fields when no
    data-refresh has run yet (empty state → frontend shows "run data refresh")."""

    window = BacktestDataWindowRepository(session).get_window()
    if window is None:
        return BacktestDataRangeResponse()
    return BacktestDataRangeResponse(
        data_start=window.data_start.isoformat(),
        data_end=window.data_end.isoformat(),
        min_usable_start=window.first_usable_signal_date.isoformat(),
    )


def _to_response(row: BacktestRun) -> BacktestRunResponse:
    metrics = BacktestMetrics(**row.metrics) if row.metrics else None
    return BacktestRunResponse(
        run_id=row.run_id,
        status=row.status,
        metrics=metrics,
        equity=[EquitySample(**s) for s in (row.equity or [])],
        allocations=[AllocationBar(**a) for a in (row.allocations or [])],
        trades=[BacktestTrade(**t) for t in (row.trades or [])],
        report_markdown=row.report_markdown,
        explanation=row.explanation,
        error=row.error,
        error_kind=row.error_kind,
    )
