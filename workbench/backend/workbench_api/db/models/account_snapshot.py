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

from sqlalchemy import JSON, DateTime, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base

# B057 F004 — default strategy mode. Existing (pre-B057) account snapshots + any
# snapshot written without an explicit mode carry this id, so the column
# addition is backward compatible (the Master execution path is unchanged).
DEFAULT_STRATEGY_ID = "master_portfolio"


class AccountSnapshot(Base):
    __tablename__ = "account_snapshot"
    # B057 F004 — per-mode latest() lookup (each mode has its own real account).
    __table_args__ = (
        Index(
            "ix_account_snapshot_strategy_snapshot_at",
            "strategy_id",
            "snapshot_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    # B057 F004 — which strategy mode's real account this snapshot belongs to.
    # Server default keeps pre-B057 Master rows valid after the migration; the
    # model default keeps in-memory test rows Master by default.
    strategy_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=DEFAULT_STRATEGY_ID,
        server_default=DEFAULT_STRATEGY_ID,
    )
    cash: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    positions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self) -> str:
        return (
            f"AccountSnapshot(id={self.id!r}, strategy_id={self.strategy_id!r}, "
            f"source={self.source!r})"
        )
