"""B080 F002 — monitoring_metric table (L0 strategy-lifecycle metrics store).

One row per ``(strategy_id, as_of, metric)`` — the weekly monitoring job writes a
value + a ``meta`` blob (thresholds, partial-window / holdings-fidelity honesty
flags). Pure observation: written by the off-request-path monitoring timer, read
only by the ``/monitoring/metrics`` surface. ``value`` is nullable so a partial /
degraded metric can be recorded (``meta.partial=true``) without a fake number.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Float, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from workbench_api.db.models.base import Base

_Json = JSON().with_variant(JSONB(), "postgresql")


class MonitoringMetric(Base):
    __tablename__ = "monitoring_metric"
    __table_args__ = (
        UniqueConstraint(
            "strategy_id",
            "as_of",
            "metric",
            name="uq_monitoring_metric_strategy_as_of_metric",
        ),
        Index("ix_monitoring_metric_strategy_as_of", "strategy_id", "as_of"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(_Json, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"MonitoringMetric(strategy_id={self.strategy_id!r}, "
            f"as_of={self.as_of!r}, metric={self.metric!r}, value={self.value!r})"
        )
