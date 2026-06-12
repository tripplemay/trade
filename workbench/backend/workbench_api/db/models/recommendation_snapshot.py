"""B044 F002 — recommendation_snapshot table.

One row per (as_of_date, symbol, strategy_id) target-weight entry of a
precomputed strategy mode. The daily recommendations precompute (F002) imports
the ``trade`` package, runs the real Master Portfolio scoring "as of today",
and writes the resulting per-symbol target weights here. ``GET
/api/recommendations/current`` (F003) reads the latest as_of_date and maps it
to the existing ``TargetPosition`` shape — the request path never imports
``trade`` (enforced by the §12.10 AST guard).

**B057 F001 — generalized to every strategy mode.** Before B057 every row
implicitly belonged to the Master Portfolio. B057 adds the ``strategy_id``
column (default ``"master_portfolio"`` — existing Master rows are unchanged)
so the *same* table holds each mode's current target: the regime precompute
writes its rows under ``"regime_adaptive"``, Master keeps writing under
``"master_portfolio"``. The generic target layer
(``strategy_modes.targets.get_target``) reads one strategy's rows; the unique
constraint and the repository's idempotent delete are now scoped by
``strategy_id`` so producers never trample each other's targets.

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
# B045 F003 — partial provenance: real prices were read but at least one
# implemented sleeve still stubbed to the defensive asset (its input data was
# unavailable on the host). Marked honestly, never passed off as full real.
DATA_SOURCE_MIXED = "mixed"

# B057 F001 — default strategy mode. Existing Master rows + any row written
# without an explicit strategy carry this id, so the column addition is
# backward compatible (the Master read path is unchanged).
DEFAULT_STRATEGY_ID = "master_portfolio"


class RecommendationSnapshot(Base):
    __tablename__ = "recommendation_snapshot"
    __table_args__ = (
        # B057 F001: the target set is now per (date, symbol, strategy_id) so
        # multiple modes share the table without colliding on the same date.
        UniqueConstraint(
            "as_of_date",
            "symbol",
            "strategy_id",
            name="uq_recommendation_snapshot_date_symbol_strategy",
        ),
        Index("ix_recommendation_snapshot_as_of_date", "as_of_date"),
        # B057 F001: the generic target layer reads the latest snapshot for one
        # strategy — index the lookup key.
        Index(
            "ix_recommendation_snapshot_strategy_as_of",
            "strategy_id",
            "as_of_date",
        ),
    )

    id: Mapped[UUID] = mapped_column(_UuidString(), primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    # B057 F001 — which strategy mode this target belongs to. Server default
    # keeps pre-B057 Master rows valid after the migration; the model default
    # keeps in-memory test rows (created from ORM metadata) Master by default.
    strategy_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=DEFAULT_STRATEGY_ID,
        server_default=DEFAULT_STRATEGY_ID,
    )
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
            f"strategy_id={self.strategy_id!r}, symbol={self.symbol!r}, "
            f"sleeve={self.sleeve!r}, target_weight={self.target_weight!r})"
        )
