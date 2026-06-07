"""B048 F001 — PriceHistoryRepository.

Pins the idempotent ``save_if_new`` by ``(symbol, obs_date)`` and the two
reads the risk layer's NAV-history reconstruction (F003) depends on:
``close_on_or_before`` (mark a snapshot date, tolerating gaps) and
``closes_by_symbol_since`` (a per-symbol close series).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.price_history import PriceHistoryRepository

_FETCHED = datetime(2026, 6, 7, tzinfo=UTC)


def _seed(repo: PriceHistoryRepository, symbol: str, rows: list[tuple[date, float]]) -> None:
    for obs_date, close in rows:
        repo.save_if_new(
            symbol=symbol, obs_date=obs_date, close=close,
            source="b045_unified_csv", fetched_at=_FETCHED,
        )


def test_save_if_new_inserts_then_dedupes(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = PriceHistoryRepository(session)
        row = repo.save_if_new(
            symbol="AAPL", obs_date=date(2026, 6, 4), close=195.0,
            source="b045_unified_csv", fetched_at=_FETCHED,
        )
        assert row is not None
        # Same (symbol, obs_date) → no duplicate, returns None.
        dup = repo.save_if_new(
            symbol="AAPL", obs_date=date(2026, 6, 4), close=999.0,
            source="b045_unified_csv", fetched_at=_FETCHED,
        )
        assert dup is None
        session.commit()
        assert repo.count() == 1


def test_close_on_or_before_exact_date(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = PriceHistoryRepository(session)
        _seed(repo, "AAPL", [(date(2026, 6, 2), 190.0), (date(2026, 6, 4), 195.0)])
        session.commit()
        assert repo.close_on_or_before("AAPL", date(2026, 6, 4)) == 195.0


def test_close_on_or_before_falls_back_to_prior(initialised_db: str) -> None:
    """A valuation date on a non-trading day (no stored row) resolves to
    the most recent prior close — not None."""

    with Session(get_engine()) as session:
        repo = PriceHistoryRepository(session)
        _seed(repo, "AAPL", [(date(2026, 6, 2), 190.0), (date(2026, 6, 4), 195.0)])
        session.commit()
        # 2026-06-05 has no row → falls back to 2026-06-04's close.
        assert repo.close_on_or_before("AAPL", date(2026, 6, 5)) == 195.0
        # 2026-06-03 has no row → falls back to 2026-06-02's close.
        assert repo.close_on_or_before("AAPL", date(2026, 6, 3)) == 190.0


def test_close_on_or_before_returns_none_before_history(initialised_db: str) -> None:
    """No close at or before the as-of date → None (caller degrades, does
    not fabricate — v0.9.21)."""

    with Session(get_engine()) as session:
        repo = PriceHistoryRepository(session)
        _seed(repo, "AAPL", [(date(2026, 6, 4), 195.0)])
        session.commit()
        assert repo.close_on_or_before("AAPL", date(2026, 6, 1)) is None
        # Unknown symbol → None.
        assert repo.close_on_or_before("ZZZZ", date(2026, 6, 4)) is None


def test_closes_by_symbol_since_oldest_first(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = PriceHistoryRepository(session)
        _seed(
            repo,
            "AAPL",
            [
                (date(2026, 6, 1), 188.0),
                (date(2026, 6, 2), 190.0),
                (date(2026, 6, 3), 192.0),
                (date(2026, 6, 4), 195.0),
            ],
        )
        # A second symbol must not leak into AAPL's series.
        _seed(repo, "MSFT", [(date(2026, 6, 3), 410.0)])
        session.commit()
        series = repo.closes_by_symbol_since("AAPL", date(2026, 6, 2))
        assert series == [
            (date(2026, 6, 2), 190.0),
            (date(2026, 6, 3), 192.0),
            (date(2026, 6, 4), 195.0),
        ]


def test_closes_by_symbol_since_empty_when_no_rows(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = PriceHistoryRepository(session)
        _seed(repo, "AAPL", [(date(2026, 6, 4), 195.0)])
        session.commit()
        assert repo.closes_by_symbol_since("AAPL", date(2026, 6, 5)) == []
