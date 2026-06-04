"""B035 F001 — MarketContextRepository.

Wraps the ``market_context_observation`` table with the operations the
F001 loaders, the F002 daily CLI, and the F003 ``/market-context`` route
need:

- :meth:`save_if_new` — idempotent insert by ``(series_id, obs_date)``;
  returns ``None`` when that data point already exists. The daily
  systemd-timer fetch re-runs over the full series each day, so this
  keeps a re-fetch of an already-stored observation a no-op.
- :meth:`latest_by_series` — the most recent observation for one series
  (newest ``obs_date`` first); the Home card renders one latest value
  per series.
- :meth:`list_by_series` — history for one series with ``since`` +
  ``limit`` knobs, newest-first.

The repository never touches the network or disk — the loader writes the
raw snapshot and passes ``snapshot_path`` in. That split keeps each
layer single-purpose and lets a test exercise the repo against in-memory
SQLite without any provider call.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from workbench_api.db.models.market_context import MarketContextObservation
from workbench_api.db.repositories.base import Repository


class MarketContextRepository(Repository[MarketContextObservation, UUID]):
    model = MarketContextObservation
    primary_key_attr = "id"

    def get_by_series_and_date(
        self, series_id: str, obs_date: date
    ) -> MarketContextObservation | None:
        stmt = select(MarketContextObservation).where(
            MarketContextObservation.series_id == series_id,
            MarketContextObservation.obs_date == obs_date,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def save_if_new(
        self,
        *,
        series_id: str,
        source: str,
        obs_date: date,
        value: float,
        snapshot_path: str,
        fetched_at: datetime | None = None,
    ) -> MarketContextObservation | None:
        """Insert an observation if absent; return ``None`` if a row with
        the same ``(series_id, obs_date)`` already exists.

        ``fetched_at`` defaults to ``datetime.now(timezone.utc)`` and is
        overridable so tests pin a deterministic timestamp.
        """

        if self.get_by_series_and_date(series_id, obs_date) is not None:
            return None
        row = MarketContextObservation(
            id=uuid4(),
            series_id=series_id,
            source=source,
            obs_date=obs_date,
            value=value,
            snapshot_path=snapshot_path,
            fetched_at=fetched_at or datetime.now(UTC),
        )
        self._session.add(row)
        self._session.flush()
        return row

    def latest_by_series(self, series_id: str) -> MarketContextObservation | None:
        stmt = (
            select(MarketContextObservation)
            .where(MarketContextObservation.series_id == series_id)
            .order_by(MarketContextObservation.obs_date.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def list_by_series(
        self,
        series_id: str,
        *,
        since: date | None = None,
        limit: int = 100,
    ) -> list[MarketContextObservation]:
        stmt = select(MarketContextObservation).where(
            MarketContextObservation.series_id == series_id
        )
        if since is not None:
            stmt = stmt.where(MarketContextObservation.obs_date >= since)
        stmt = stmt.order_by(MarketContextObservation.obs_date.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars().all())
