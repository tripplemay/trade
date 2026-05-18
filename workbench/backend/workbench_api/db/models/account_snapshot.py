"""AccountSnapshot model — point-in-time account state (B023 F001).

Each material change to cash or positions writes one snapshot, so the
Recommendations page can always read the most recent state via
``latest()`` and slippage analytics can join through the snapshot
that immediately preceded a ticket's fills.

``positions`` is stored as JSON — a list of ``{symbol, shares,
avg_cost}`` dicts — to keep round-tripping identical to the
``accounts/me.json`` repo-root file. ``source`` records what produced
the snapshot: ``bootstrap`` (CLI seed), ``ui_edit`` (user form), or
``fill_reconcile`` (post-execution reconciliation).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base


class AccountSnapshot(Base):
    __tablename__ = "account_snapshot"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    cash: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    positions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self) -> str:
        return f"AccountSnapshot(id={self.id!r}, source={self.source!r})"
