"""B047 F001 — backtest_run queue + result table.

One row per on-demand backtest request. The table is BOTH the work queue and
the result store: a request enqueues a ``queued`` row, the async worker (B047
F002) atomically claims it (``queued → running``), runs the real
``master_portfolio`` backtest + report generation, and writes the result back
(``running → done`` with metrics/equity/allocations/trades/report_markdown) or
the failure (``running → error`` with ``error``).

This keeps the request path off the heavy ``trade`` stack: ``POST
/api/backtests/run`` only writes a queued row and returns a ``run_id``; ``GET
/api/backtests/{run_id}`` only reads this table (§12.10.2 — the request path
never imports ``trade``; only the worker does).

JSON columns use the same ``JSON().with_variant(JSONB)`` shape as
``recommendation_snapshot`` (SQLite on the VM, Postgres-ready). Results are
HISTORICAL backtest output, never a forward return prediction (positioning
§1.1).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from workbench_api.db.models.base import Base

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_ERROR = "error"
VALID_STATUSES = frozenset({STATUS_QUEUED, STATUS_RUNNING, STATUS_DONE, STATUS_ERROR})


class BacktestRun(Base):
    __tablename__ = "backtest_run"
    __table_args__ = (
        # The worker claims the oldest queued row — index the (status, created_at)
        # the claim query orders by so the poll stays cheap as history grows.
        Index("ix_backtest_run_status_created", "status", "created_at"),
    )

    run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    params: Mapped[Any] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)

    # Populated when status == done (the worker maps MasterPortfolioBacktestResult).
    metrics: Mapped[Any | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    equity: Mapped[Any | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    allocations: Mapped[Any | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    trades: Mapped[Any | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    report_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"BacktestRun(run_id={self.run_id!r}, strategy_id={self.strategy_id!r}, "
            f"status={self.status!r})"
        )
