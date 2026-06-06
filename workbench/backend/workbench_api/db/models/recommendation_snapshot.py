"""B044 F002 — recommendation_snapshot table.

One row per (as_of_date, symbol) target-weight entry of the precomputed
Master Portfolio. The daily recommendations precompute (F002) imports the
``trade`` package, runs the real Master Portfolio scoring "as of today", and
writes the resulting per-symbol target weights here. ``GET
/api/recommendations/current`` (F003) reads the latest as_of_date and maps it
to the existing ``TargetPosition`` shape — the request path never imports
``trade`` (enforced by the §12.10 AST guard).

``master_meta`` (JSON) carries the run-level metadata shared by every row of a
batch: the sleeve ``planning_weights`` and — critically — ``data_source``
(``real`` / ``fixture``). The scoring CODE is real, but the price DATA may be
the bundled fixture when real market data is unavailable on the VM; the marker
keeps that honest (never fixture-as-real; framework v0.9.21). These are
HISTORICAL/configuration weights, never a forward return prediction
(positioning §1.1).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Date, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from workbench_api.db.models.base import Base
from workbench_api.db.models.news import _UuidString

DATA_SOURCE_REAL = "real"
DATA_SOURCE_FIXTURE = "fixture"


class RecommendationSnapshot(Base):
    __tablename__ = "recommendation_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "as_of_date", "symbol", name="uq_recommendation_snapshot_date_symbol"
        ),
        Index("ix_recommendation_snapshot_as_of_date", "as_of_date"),
    )

    id: Mapped[UUID] = mapped_column(_UuidString(), primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    sleeve: Mapped[str] = mapped_column(String(64), nullable=False)
    target_weight: Mapped[float] = mapped_column(nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    master_meta: Mapped[Any] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"RecommendationSnapshot(as_of_date={self.as_of_date!r}, "
            f"symbol={self.symbol!r}, sleeve={self.sleeve!r}, "
            f"target_weight={self.target_weight!r})"
        )
