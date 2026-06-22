"""B074 F001 — A-share unified-CSV → price_snapshot sync.

Pins that ``sync_cn_closes_from_csv`` reads ONLY the A-share (``.SH`` / ``.SZ``)
rows from the unified prices CSV, writes their recent closes into
``price_snapshot`` (idempotent, source ``unified_csv``), makes them markable
through the SAME ``DbPriceProvider`` the paper engine uses, ignores the US rows
(those are the Tiingo CLI's job — US-zero-regression), and no-ops gracefully when
the CSV is absent (local / CI).
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.price_snapshot import PriceSnapshotRepository
from workbench_api.prices.cn_snapshot_sync import (
    CN_SNAPSHOT_SOURCE,
    is_a_share,
    read_recent_cn_closes,
    sync_cn_closes_from_csv,
)
from workbench_api.services.prices_provider import DbPriceProvider

_HEADER = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]


def _write_csv(path: Path, rows: list[tuple[str, str, float]]) -> None:
    """Write a unified-shape prices CSV from ``(date, ticker, close)`` rows."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_HEADER)
        for d, ticker, close in rows:
            writer.writerow([d, ticker, close, close, close, close, close, 1000])


def _csv_with_ashares_and_us(tmp_path: Path) -> Path:
    path = tmp_path / "prices_daily.csv"
    _write_csv(
        path,
        [
            ("2026-06-17", "600519.SH", 1500.0),
            ("2026-06-18", "600519.SH", 1520.0),
            ("2026-06-17", "000858.SZ", 140.0),
            ("2026-06-18", "000858.SZ", 142.0),
            # US rows must be IGNORED — Tiingo owns those (US-zero-regression).
            ("2026-06-17", "AAPL", 195.0),
            ("2026-06-18", "AAPL", 197.0),
        ],
    )
    return path


def _session() -> Session:
    return Session(get_engine())


def test_sync_persists_ashare_closes_and_ignores_us(
    initialised_db: str, tmp_path: Path
) -> None:
    path = _csv_with_ashares_and_us(tmp_path)
    with _session() as session:
        summary = sync_cn_closes_from_csv(session, prices_path=path)

    # Two A-shares × two closes; the US ticker is not synced here.
    assert summary.symbols == 2
    assert summary.saved == 4
    assert summary.touched == ("000858.SZ", "600519.SH")

    with _session() as session:
        repo = PriceSnapshotRepository(session)
        # A-share closes landed with the unified_csv provenance label.
        rows = repo.latest_two_by_symbol("600519.SH")
        assert [float(r.close) for r in rows] == [1520.0, 1500.0]
        assert {r.source for r in rows} == {CN_SNAPSHOT_SOURCE}
        # The US ticker was NOT touched by the A-share sync.
        assert repo.latest_two_by_symbol("AAPL") == []
        # Both A-shares are now markable through the paper mark source.
        marks = DbPriceProvider(session).get_marks(["600519.SH", "000858.SZ"])
        assert set(marks) == {"600519.SH", "000858.SZ"}
        assert marks["600519.SH"].latest_close == 1520.0


def test_sync_is_idempotent(initialised_db: str, tmp_path: Path) -> None:
    path = _csv_with_ashares_and_us(tmp_path)
    with _session() as session:
        first = sync_cn_closes_from_csv(session, prices_path=path)
    assert first.saved == 4

    with _session() as session:
        again = sync_cn_closes_from_csv(session, prices_path=path)
    # Re-run writes nothing new (idempotent by (symbol, obs_date)).
    assert again.saved == 0
    assert again.symbols == 2
    with _session() as session:
        assert PriceSnapshotRepository(session).count() == 4


def test_sync_missing_file_is_graceful_noop(
    initialised_db: str, tmp_path: Path
) -> None:
    with _session() as session:
        summary = sync_cn_closes_from_csv(
            session, prices_path=tmp_path / "does-not-exist.csv"
        )
    assert summary == type(summary)(symbols=0, saved=0, rows_seen=0, touched=())
    with _session() as session:
        assert PriceSnapshotRepository(session).count() == 0


def test_read_recent_keeps_two_most_recent_per_symbol(tmp_path: Path) -> None:
    path = tmp_path / "prices_daily.csv"
    _write_csv(
        path,
        [
            ("2026-06-15", "600519.SH", 1400.0),
            ("2026-06-16", "600519.SH", 1450.0),
            ("2026-06-17", "600519.SH", 1500.0),
            ("2026-06-18", "600519.SH", 1520.0),
        ],
    )
    closes = read_recent_cn_closes(path, recent=2)
    # Only the two newest dates survive, newest first.
    assert closes["600519.SH"] == [
        (date(2026, 6, 18), 1520.0),
        (date(2026, 6, 17), 1500.0),
    ]


def test_single_close_symbol_is_touched_but_unmarkable(
    initialised_db: str, tmp_path: Path
) -> None:
    path = tmp_path / "prices_daily.csv"
    _write_csv(path, [("2026-06-18", "600519.SH", 1520.0)])  # only ONE close
    with _session() as session:
        summary = sync_cn_closes_from_csv(session, prices_path=path)
    assert summary.touched == ("600519.SH",)
    with _session() as session:
        # One close → not markable (the paper engine needs latest + prior).
        assert DbPriceProvider(session).get_marks(["600519.SH"]) == {}


@pytest.mark.parametrize(
    ("ticker", "expected"),
    [
        ("600519.SH", True),
        ("000858.SZ", True),
        ("688981.SH", True),
        ("AAPL", False),
        ("SPY", False),
        ("CASH", False),  # the cn_attack cash pseudo-symbol is NOT an A-share
        ("0700.HK", False),  # HK is not a mainland A-share
        ("", False),
        ("not a ticker", False),
    ],
)
def test_is_a_share(ticker: str, expected: bool) -> None:
    assert is_a_share(ticker) is expected
