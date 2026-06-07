"""B048 F001 — PriceHistoryRepository.

Wraps the deep ``price_history`` table with the operations the backfill
job and the risk layer's NAV-history reconstruction (B048 F003) need:

- :meth:`save_if_new` — idempotent insert by ``(symbol, obs_date)``;
  returns ``None`` when that close already exists, so a backfill re-run
  never duplicates (same contract as ``PriceSnapshotRepository``).
- :meth:`close_on_or_before` — the close for ``symbol`` on the latest
  ``obs_date <= as_of``. This is the mark-to-market lookup F003 uses to
  value a historical ``AccountSnapshot`` taken on date ``D``: it tolerates
  non-trading days / sparse history by falling back to the most recent
  prior close, and returns ``None`` when no close at or before ``as_of``
  exists (the caller then degrades that point rather than fabricating a
  value — v0.9.21).
- :meth:`closes_by_symbol_since` — all ``(obs_date, close)`` for ``symbol``
  on ``obs_date >= since``, oldest first, for building a per-symbol close
  series.

The repository never touches the network or disk — the backfill job reads
the CSV and passes closes in. That split keeps each layer single-purpose
and lets a test exercise the repo against in-memory SQLite without any
file read (mirrors ``PriceSnapshotRepository``).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from workbench_api.db.models.price_history import PriceHistory
from workbench_api.db.repositories.base import Repository


class PriceHistoryRepository(Repository[PriceHistory, UUID]):
    model = PriceHistory
    primary_key_attr = "id"

    def get_by_symbol_and_date(
        self, symbol: str, obs_date: date
    ) -> PriceHistory | None:
        stmt = select(PriceHistory).where(
            PriceHistory.symbol == symbol,
            PriceHistory.obs_date == obs_date,
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
    ) -> PriceHistory | None:
        """Insert a close if absent; return ``None`` if a row with the same
        ``(symbol, obs_date)`` already exists.

        ``fetched_at`` defaults to ``datetime.now(timezone.utc)`` and is
        overridable so tests pin a deterministic timestamp.
        """

        if self.get_by_symbol_and_date(symbol, obs_date) is not None:
            return None
        row = PriceHistory(
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

    def close_on_or_before(self, symbol: str, as_of: date) -> float | None:
        """Return ``symbol``'s close on the latest ``obs_date <= as_of``.

        Falls back to the most recent prior close so a valuation date that
        lands on a weekend / holiday (or a date with no stored row) still
        resolves. Returns ``None`` when no close at or before ``as_of``
        exists — the caller degrades that point (does not fabricate)."""

        stmt = (
            select(PriceHistory.close)
            .where(
                PriceHistory.symbol == symbol,
                PriceHistory.obs_date <= as_of,
            )
            .order_by(PriceHistory.obs_date.desc())
            .limit(1)
        )
        result = self._session.execute(stmt).scalar_one_or_none()
        return None if result is None else float(result)

    def closes_by_symbol_since(
        self, symbol: str, since: date
    ) -> list[tuple[date, float]]:
        """Return ``(obs_date, close)`` for ``symbol`` on ``obs_date >=
        since``, oldest first — a per-symbol close series for NAV-history
        reconstruction."""

        stmt = (
            select(PriceHistory.obs_date, PriceHistory.close)
            .where(
                PriceHistory.symbol == symbol,
                PriceHistory.obs_date >= since,
            )
            .order_by(PriceHistory.obs_date.asc())
        )
        return [
            (row_date, float(row_close))
            for row_date, row_close in self._session.execute(stmt).all()
        ]
