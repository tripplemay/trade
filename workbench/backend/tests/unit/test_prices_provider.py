"""B037 F001 — DbPriceProvider.

The Home Day P&L resolves marks through this provider. A symbol is marked
only when two closes exist (latest + prior trading day); fewer → omitted.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.price_snapshot import PriceSnapshotRepository
from workbench_api.services.prices_provider import DbPriceProvider, PriceMark

_FETCHED = datetime(2026, 6, 5, tzinfo=UTC)


def _seed(session: Session, symbol: str, rows: list[tuple[date, float]]) -> None:
    repo = PriceSnapshotRepository(session)
    for d, c in rows:
        repo.save_if_new(
            symbol=symbol, obs_date=d, close=c, source="tiingo", fetched_at=_FETCHED
        )
    session.commit()


def test_get_marks_returns_latest_and_prior(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        _seed(session, "AAPL", [(date(2026, 6, 3), 192.0), (date(2026, 6, 4), 195.0)])
        marks = DbPriceProvider(session).get_marks(["AAPL"])
        assert marks == {"AAPL": PriceMark(latest_close=195.0, prior_close=192.0)}


def test_get_marks_omits_symbol_with_one_close(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        _seed(session, "MSFT", [(date(2026, 6, 4), 410.0)])
        assert DbPriceProvider(session).get_marks(["MSFT"]) == {}


def test_get_marks_uppercases_and_dedupes_symbols(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        _seed(session, "AAPL", [(date(2026, 6, 3), 192.0), (date(2026, 6, 4), 195.0)])
        marks = DbPriceProvider(session).get_marks(["aapl", "AAPL", ""])
        assert set(marks) == {"AAPL"}
