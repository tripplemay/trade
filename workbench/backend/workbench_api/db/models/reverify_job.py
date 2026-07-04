"""B080 F003 — reverify_job table (frozen re-validation async job status).

Mirrors ``target_refresh_job``: a POST enqueues one row (``queued``), the reverify
worker claims it (``running``), and lands ``done`` (with the report ref + verdict) or
``error``. The heavy, long baostock-fetch + frozen-backtest run cannot go on the
request path — the request only writes the queued row and the frontend polls.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_ERROR = "error"
VALID_STATUSES = frozenset({STATUS_QUEUED, STATUS_RUNNING, STATUS_DONE, STATUS_ERROR})


class ReverifyJob(Base):
    __tablename__ = "reverify_job"
    __table_args__ = (
        Index("ix_reverify_job_status_created", "status", "created_at"),
        Index("ix_reverify_job_strategy_status", "strategy_id", "status"),
    )

    job_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    # Target end date for the re-validation window (None → data end).
    as_of: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Result: the md report path + the double-gate verdict.
    report_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"ReverifyJob(job_id={self.job_id!r}, strategy_id={self.strategy_id!r}, "
            f"status={self.status!r})"
        )
