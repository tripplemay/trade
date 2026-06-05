"""B037 F001 — PriceSnapshotRepository.

Pins idempotent ``save_if_new`` by ``(symbol, obs_date)`` and the
two-most-recent-closes read the Home Day P&L mark-to-market depends on.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.price_snapshot import PriceSnapshotRepository

_FETCHED = datetime(2026, 6, 5, tzinfo=UTC)


def test_save_if_new_inserts_then_dedupes(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = PriceSnapshotRepository(session)
        row = repo.save_if_new(
            symbol="AAPL", obs_date=date(2026, 6, 4), close=195.0,
            source="tiingo", fetched_at=_FETCHED,
        )
        assert row is not None
        # Same (symbol, obs_date) → no duplicate, returns None.
        dup = repo.save_if_new(
            symbol="AAPL", obs_date=date(2026, 6, 4), close=999.0,
            source="tiingo", fetched_at=_FETCHED,
        )
        assert dup is None
        session.commit()
        assert repo.count() == 1


def test_latest_two_by_symbol_newest_first(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = PriceSnapshotRepository(session)
        for d, c in [
            (date(2026, 6, 2), 190.0),
            (date(2026, 6, 3), 192.0),
            (date(2026, 6, 4), 195.0),
        ]:
            repo.save_if_new(
                symbol="AAPL", obs_date=d, close=c, source="tiingo", fetched_at=_FETCHED
            )
        session.commit()
        rows = repo.latest_two_by_symbol("AAPL")
        assert [r.obs_date for r in rows] == [date(2026, 6, 4), date(2026, 6, 3)]
        assert [float(r.close) for r in rows] == [195.0, 192.0]


def test_latest_two_by_symbol_single_row(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = PriceSnapshotRepository(session)
        repo.save_if_new(
            symbol="MSFT", obs_date=date(2026, 6, 4), close=410.0,
            source="tiingo", fetched_at=_FETCHED,
        )
        session.commit()
        rows = repo.latest_two_by_symbol("MSFT")
        assert len(rows) == 1
