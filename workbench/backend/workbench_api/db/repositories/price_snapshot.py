"""B037 F001 — PriceSnapshotRepository.

Wraps the ``price_snapshot`` table with the operations the price
ingestion CLI (daily ``workbench-prices`` timer) and the Home
mark-to-market provider need:

- :meth:`save_if_new` — idempotent insert by ``(symbol, obs_date)``;
  returns ``None`` when that close already exists, so a timer retry /
  same-day re-run never duplicates.
- :meth:`latest_two_by_symbol` — the two most recent closes for one
  symbol (newest ``obs_date`` first). The Home Day P&L marks each
  position with ``latest`` vs the prior trading day's close, so it needs
  exactly the latest two stored observations for the symbol.

The repository never touches the network or disk — the ingestion loader
fetches the close and passes it in. That split keeps each layer
single-purpose and lets a test exercise the repo against in-memory
SQLite without any provider call (mirrors B035 MarketContextRepository).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from workbench_api.db.models.price_snapshot import PriceSnapshot
from workbench_api.db.repositories.base import Repository


class PriceSnapshotRepository(Repository[PriceSnapshot, UUID]):
    model = PriceSnapshot
    primary_key_attr = "id"

    def get_by_symbol_and_date(
        self, symbol: str, obs_date: date
    ) -> PriceSnapshot | None:
        stmt = select(PriceSnapshot).where(
            PriceSnapshot.symbol == symbol,
            PriceSnapshot.obs_date == obs_date,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def save_if_new(
        self,
        *,
        symbol: str,
        obs_date: date,
        close: float,
        source: str,
        fetched_at: datetime | None = None,
    ) -> PriceSnapshot | None:
        """Insert a close if absent; return ``None`` if a row with the same
        ``(symbol, obs_date)`` already exists.

        ``fetched_at`` defaults to ``datetime.now(timezone.utc)`` and is
        overridable so tests pin a deterministic timestamp.
        """

        if self.get_by_symbol_and_date(symbol, obs_date) is not None:
            return None
        row = PriceSnapshot(
            id=uuid4(),
            symbol=symbol,
            obs_date=obs_date,
            close=close,
            source=source,
            fetched_at=fetched_at or datetime.now(UTC),
        )
        self._session.add(row)
        self._session.flush()
        return row

    def latest_two_by_symbol(self, symbol: str) -> list[PriceSnapshot]:
        """Return up to the two most recent closes for ``symbol``,
        newest ``obs_date`` first. Day P&L marks ``[0]`` (latest) against
        ``[1]`` (prior trading day); fewer than two rows → no mark."""

        stmt = (
            select(PriceSnapshot)
            .where(PriceSnapshot.symbol == symbol)
            .order_by(PriceSnapshot.obs_date.desc())
            .limit(2)
        )
        return list(self._session.execute(stmt).scalars().all())
