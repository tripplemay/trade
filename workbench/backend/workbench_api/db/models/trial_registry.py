"""B080 F001 — trial_registry table (structured backtest-trial log).

Every strategy backtest / walk-forward evaluation ever run is one *trial*. The
count of trials per strategy is the denominator ``N`` a future Deflated Sharpe
Ratio needs (you cannot compute DSR without knowing how many configurations were
tried). ``backtest_run`` is a work-queue + result blob with no
parameter_hash / universe / window / verdict first-class fields, so this is a
separate, purpose-built table.

Rows arrive two ways: (1) the B050 backtest worker auto-registers one on every
completed run (``verdict="NA"``, ``parameter_hash`` from the engine); (2) a
one-time idempotent backfill seeds the historical B063–B077 trials from their
signoff reports (each ``source_ref`` points at the report file; numbers copied
verbatim). Read-only on the request path — advisory/research metadata only.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from workbench_api.db.models.base import Base

# Same JSON-with-JSONB-on-Postgres shape the other models use (backtest_run).
_Json = JSON().with_variant(JSONB(), "postgresql")

# verdict is a small closed set; kept as a plain String (no DB enum) so a future
# value never needs a migration. Validated at the repo/seed boundary.
TRIAL_VERDICTS = ("GO", "NO_GO", "INCONCLUSIVE", "NA")


class TrialRegistry(Base):
    __tablename__ = "trial_registry"
    __table_args__ = (
        Index("ix_trial_registry_strategy_id", "strategy_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    batch: Mapped[str] = mapped_column(String(32), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    parameter_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    params: Mapped[dict[str, Any]] = mapped_column(_Json, nullable=False)
    universe: Mapped[str | None] = mapped_column(String(256), nullable=True)
    window_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    window_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    oos_split: Mapped[str | None] = mapped_column(String(256), nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(_Json, nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)

    def __repr__(self) -> str:
        return (
            f"TrialRegistry(id={self.id!r}, batch={self.batch!r}, "
            f"strategy_id={self.strategy_id!r}, verdict={self.verdict!r})"
        )
