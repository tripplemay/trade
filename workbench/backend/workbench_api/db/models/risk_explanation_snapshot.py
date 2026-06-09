"""B043 F003 — risk_explanation_snapshot table.

One row per ``as_of_date`` carrying the grounded LLM "why" for the current risk
state. A daily precompute job (``services.risk_explanation``) computes the risk
grounding (master drawdown / per-sleeve DD / state / kill-switch threshold) and
asks the LLM for a short explanation off the request path; the risk-panel
request path (``services.risk_panel.get_risk_panel``) reads only the latest row.

This split is the §12.10.2 architecture point: the risk panel is a read-only
request path and must never make an LLM call, so the explanation is precomputed
into this table and the panel just surfaces it.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base
from workbench_api.db.models.news import _UuidString


class RiskExplanationSnapshot(Base):
    __tablename__ = "risk_explanation_snapshot"
    __table_args__ = (
        UniqueConstraint("as_of_date", name="uq_risk_explanation_snapshot_as_of_date"),
    )

    id: Mapped[UUID] = mapped_column(_UuidString(), primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    master_dd: Mapped[float] = mapped_column(nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    # Nullable: the explanation is an enhancement — a refused / over-budget /
    # LLM-down run still records the row (with NULL) so the panel degrades
    # gracefully (shows no explanation block) rather than missing the row.
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return (
            f"RiskExplanationSnapshot(as_of_date={self.as_of_date!r}, "
            f"state={self.state!r})"
        )
