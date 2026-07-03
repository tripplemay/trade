"""B080 F001 — oos_verification_card table (DB-ized cn_attack red card).

The out-of-sample "red card" honesty disclosure for the research-state cn_attack
momentum modes was hardcoded in two places (``CN_ATTACK_RESEARCH_CAVEAT`` dict +
``registry.py`` mode descriptions). This table lifts the *card values* into the DB
so the frozen re-validation pipeline (F003) can update them (only ever more
conservative — there is no ``validated=False→True`` code path), while the precompute
producer reads the card at run time and **falls back byte-identically** to the
in-code constant when no row exists (zero regression).

One row per ``strategy_id`` (the two cn_attack modes). The 8 value columns map
1:1 onto the :class:`ResearchCaveat` schema fields, so a row is a drop-in for
``dict(CN_ATTACK_RESEARCH_CAVEAT)``. ``updated_at`` stamps provenance (seed vs a
later re-validation), mirroring ``symbol_name``. Deliberately isolated + read-only
on the request path (the producer/timer owns writes; §12.10.2).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base


class OosVerificationCard(Base):
    __tablename__ = "oos_verification_card"

    strategy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    validated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    oos_result: Mapped[str] = mapped_column(String(32), nullable=False)
    oos_cagr_range: Mapped[str] = mapped_column(String(64), nullable=False)
    headline_zh: Mapped[str] = mapped_column(String(512), nullable=False)
    headline_en: Mapped[str] = mapped_column(String(512), nullable=False)
    detail_zh: Mapped[str] = mapped_column(String(512), nullable=False)
    detail_en: Mapped[str] = mapped_column(String(512), nullable=False)
    backtest_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    # Provenance: "seed" (migration, mirrors the in-code constant) vs
    # "reverify_<date>" (a later frozen re-validation pipeline write, F003).
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"OosVerificationCard(strategy_id={self.strategy_id!r}, "
            f"validated={self.validated!r})"
        )
