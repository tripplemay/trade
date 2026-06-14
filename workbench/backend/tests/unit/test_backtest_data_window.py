"""B047-OPS2 F001 — data-coverage window: computation + repo + cli constant.

Covers the L2/L4 backend pieces:
- ``compute_data_window`` derives data_start/data_end/first_usable from the CSV,
  clamps a too-short refresh, and returns ``None`` for missing / empty CSVs.
- ``BacktestDataWindowRepository`` upserts the singleton coverage row.
- ``DEFAULT_LOOKBACK_DAYS`` is the L4 deep-backfill 5-year value (1825).
"""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.data_refresh import cli as refresh_cli
from workbench_api.data_refresh.refresh import PRICES_HEADER
from workbench_api.data_refresh.window import (
    FIRST_USABLE_LOOKBACK_DAYS,
    compute_data_window,
)
from workbench_api.db.engine import get_engine
from workbench_api.db.models.backtest_data_window import SINGLETON_ID
from workbench_api.db.repositories.backtest_data_window import (
    BacktestDataWindowRepository,
)


def _write_prices(path: Path, dates: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(PRICES_HEADER)
        for d in dates:
            writer.writerow([d, "SPY", 1.0, 1.0, 1.0, 1.0, 1.0, 100])


def test_compute_data_window_min_max_and_first_usable(tmp_path: Path) -> None:
    path = tmp_path / "prices_daily.csv"
    # Out-of-order rows + a 5-year span so first_usable is data_start + ~10 months.
    _write_prices(path, ["2024-03-15", "2021-06-01", "2026-06-08", "2023-01-02"])

    window = compute_data_window(path)

    assert window is not None
    assert window.data_start == date(2021, 6, 1)
    assert window.data_end == date(2026, 6, 8)
    assert window.first_usable_signal_date == date(2021, 6, 1) + timedelta(
        days=FIRST_USABLE_LOOKBACK_DAYS
    )
    # first_usable sits strictly inside the coverage band.
    assert window.data_start < window.first_usable_signal_date < window.data_end


def test_compute_data_window_clamps_short_refresh(tmp_path: Path) -> None:
    """A refresh shorter than the lookback floor clamps first_usable to data_end
    so the window stays internally consistent (start ≤ first_usable ≤ end)."""

    path = tmp_path / "prices_daily.csv"
    _write_prices(path, ["2026-01-01", "2026-02-01"])  # ~1 month only

    window = compute_data_window(path)

    assert window is not None
    assert window.first_usable_signal_date == window.data_end


def test_compute_data_window_missing_file_returns_none(tmp_path: Path) -> None:
    assert compute_data_window(tmp_path / "nope.csv") is None


def test_compute_data_window_header_only_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "prices_daily.csv"
    _write_prices(path, [])
    assert compute_data_window(path) is None


def test_repo_upsert_is_singleton(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = BacktestDataWindowRepository(session)
        assert repo.get_window() is None

        repo.upsert_window(
            data_start=date(2021, 6, 1),
            data_end=date(2026, 6, 8),
            first_usable_signal_date=date(2022, 4, 1),
            updated_at=datetime(2026, 6, 9, tzinfo=UTC),
        )
        session.commit()

        # A second upsert replaces the singleton — never appends a second row.
        repo.upsert_window(
            data_start=date(2021, 7, 1),
            data_end=date(2026, 6, 9),
            first_usable_signal_date=date(2022, 5, 1),
            updated_at=datetime(2026, 6, 10, tzinfo=UTC),
        )
        session.commit()

        assert repo.count() == 1
        row = repo.get_window()
        assert row is not None
        assert row.id == SINGLETON_ID
        assert row.data_start == date(2021, 7, 1)
        assert row.data_end == date(2026, 6, 9)
        assert row.first_usable_signal_date == date(2022, 5, 1)


def test_cli_default_lookback_is_five_years() -> None:
    """L4 deep backfill — the daily timer fetches ~5 years (was 730)."""

    assert refresh_cli.DEFAULT_LOOKBACK_DAYS == 1825


class _FakePrices:
    """Returns two bars (a span) for any requested symbol."""

    def fetch_daily_bars(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[PriceBar]:
        def bar(d: date) -> PriceBar:
            return PriceBar(
                ticker=ticker,
                bar_date=d,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                adj_close=100.5,
                volume=1000,
            )

        return [bar(date(2021, 6, 1)), bar(date(2026, 6, 8))]


class _FakeFundamentals:
    """No real CIKs → every equity is skipped (no fundamentals, no error)."""

    @property
    def ticker_cik_map(self) -> dict[str, int | None]:
        return {}

    def fetch_raw_companyfacts(self, ticker: str) -> dict[str, object]:  # pragma: no cover
        raise AssertionError("no real CIK should be fetched in this fake")


def test_cli_main_persists_window(
    initialised_db: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end L2 glue: the data-refresh entrypoint writes the CSV AND upserts
    the coverage window the request path exposes."""

    # B062 F002 — _build_loaders now returns a 3rd CN/HK loader; reuse the
    # offline _FakePrices fake for it (returns bars for any ticker, no network).
    monkeypatch.setattr(
        refresh_cli,
        "_build_loaders",
        lambda: (_FakePrices(), _FakeFundamentals(), _FakePrices()),
    )
    rc = refresh_cli.main(
        ["fetch", "--data-root", str(tmp_path), "--lookback-days", "400"]
    )
    assert rc == 0

    with Session(get_engine()) as session:
        window = BacktestDataWindowRepository(session).get_window()
        assert window is not None
        assert window.data_start == date(2021, 6, 1)
        assert window.data_end == date(2026, 6, 8)
        assert window.data_start < window.first_usable_signal_date <= window.data_end
