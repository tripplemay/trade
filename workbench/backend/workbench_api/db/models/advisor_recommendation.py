"""B036 F001 — advisor_recommendation table.

One row per (sleeve, generation) advisory result. Stores the structured
advice JSON + the citation set + the status (``ok`` or
``insufficient_grounding``). The daily precompute (F002) writes here; the
``GET /advisor`` route (F003) reads the latest per sleeve.

``quant_signal_sha`` is denormalised onto the row (also inside
``references_json``) so a future audit can answer "which quant signal did
this advice cite?" without parsing the JSON. ``status`` lets the frontend
render the ``INSUFFICIENT_GROUNDING`` fallback without inspecting the
advice body.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from workbench_api.db.models.base import Base
from workbench_api.db.models.news import _UuidString

STATUS_OK = "ok"
STATUS_INSUFFICIENT_GROUNDING = "insufficient_grounding"


class AdvisorRecommendation(Base):
    __tablename__ = "advisor_recommendation"
    __table_args__ = (
        Index("ix_advisor_recommendation_sleeve", "sleeve"),
        Index("ix_advisor_recommendation_generated_at", "generated_at"),
    )

    id: Mapped[UUID] = mapped_column(_UuidString(), primary_key=True)
    sleeve: Mapped[str] = mapped_column(String(64), nullable=False)
    advice_json: Mapped[Any] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    quant_signal_sha: Mapped[str] = mapped_column(Text, nullable=False)
    references_json: Mapped[Any] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"AdvisorRecommendation(sleeve={self.sleeve!r}, "
            f"status={self.status!r}, model={self.model!r})"
        )
