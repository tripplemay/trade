"""B058 F003 — target_refresh_job queue + result table.

One row per on-demand "refresh this mode's target" request — the generic manual
target-refresh primitive. The request path
(``POST /api/strategy-modes/{strategy_id}/refresh-target``) writes a ``queued``
row and returns a ``job_id`` WITHOUT importing ``trade`` (§12.10.2). The
always-running worker daemon (the B047 backtest worker, extended to also drain
this queue) claims it, runs the mode's registered target producer — which imports
``trade`` off the request path and writes a fresh ``recommendation_snapshot`` —
then records the terminal state here. ``GET .../refresh-target/{job_id}`` polls.

Dispatch is by ``strategy_id`` through the registry's target producer, so Master,
regime and any future mode reuse the SAME endpoint + worker with no new wiring.
The result columns capture the produced target's signal date, the row count, and
the honest data_source (real / mixed / fixture) — the regime mode uses this to
generate its target on demand instead of waiting for the monthly timer (S1 fix).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_ERROR = "error"
VALID_STATUSES = frozenset({STATUS_QUEUED, STATUS_RUNNING, STATUS_DONE, STATUS_ERROR})


class TargetRefreshJob(Base):
    __tablename__ = "target_refresh_job"
    __table_args__ = (
        # The worker claims the oldest queued row — index (status, created_at).
        Index("ix_target_refresh_job_status_created", "status", "created_at"),
        # The enqueue dedup looks up an in-flight (queued) job per strategy.
        Index("ix_target_refresh_job_strategy_status", "strategy_id", "status"),
    )

    job_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)

    # Result (status == done): the produced target's signal date, the number of
    # snapshot rows written, and the honest data_source (real / mixed / fixture).
    as_of_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    saved_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Stable code the frontend i18n maps to a bilingual message
    # (producer_error / empty_target / interrupted).
    error_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"TargetRefreshJob(job_id={self.job_id!r}, "
            f"strategy_id={self.strategy_id!r}, status={self.status!r})"
        )
