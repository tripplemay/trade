"""B045 F001 — real-data refresh CLI + unified CSV writer.

Covers run_refresh writing the two unified CSVs in the EXACT schema the trade
loaders read (asserted against trade's UNIFIED_REQUIRED_COLUMNS /
UNIFIED_FUNDAMENTALS_REQUIRED_COLUMNS), per-symbol failure resilience,
synthetic-ticker skip, the universe composition, and the CLI wiring.

Loaders are faked (no network / secret); the real Tiingo + SEC EDGAR loaders
are exercised at L2 on the VM. Tests assert schema/wiring, not market values
(v0.9.21 fixture-vs-real signal).
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from workbench_api.data.fundamentals_loader import FundamentalsRow
from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.data_refresh import cli as refresh_cli
from workbench_api.data_refresh.refresh import (
    ETF_UNIVERSE,
    FUNDAMENTALS_HEADER,
    PRICES_HEADER,
    RefreshSummary,
    equity_universe,
    price_universe,
    run_refresh,
)

_FROM = date(2023, 1, 1)
_TO = date(2024, 12, 31)


def _bar(ticker: str) -> PriceBar:
    return PriceBar(
        ticker=ticker,
        bar_date=date(2024, 12, 31),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        adj_close=100.5,
        volume=1000,
    )


def _fund(ticker: str) -> FundamentalsRow:
    return FundamentalsRow(
        report_date=date(2024, 11, 1),
        ticker=ticker,
        fiscal_quarter="2024Q3",
        fiscal_quarter_end=date(2024, 9, 30),
        roe=0.25,
        gross_margin=0.40,
        fcf_yield=0.05,
        debt_to_assets=0.30,
        pe=20.0,
        pb=5.0,
        ev_ebitda=12.0,
        earnings_yield=0.05,
    )


class _FakePrices:
    def __init__(self, fail: set[str] | None = None) -> None:
        self.fail = fail or set()

    def fetch_daily_bars(self, ticker: str, from_date: date, to_date: date) -> list[PriceBar]:
        if ticker in self.fail:
            raise RuntimeError(f"boom {ticker}")
        return [_bar(ticker)]


class _FakeFundamentals:
    def __init__(self, synthetic: set[str] | None = None) -> None:
        self.synthetic = synthetic or set()

    def fetch_quarterly_fundamentals(
        self, ticker: str, from_date: date, to_date: date, sector: str | None = None
    ) -> list[FundamentalsRow]:
        if ticker in self.synthetic:
            raise ValueError(f"synthetic ticker has no SEC filing: {ticker}")
        return [_fund(ticker)]


def _run(
    tmp_path: Path,
    *,
    prices_loader: _FakePrices | None = None,
    fundamentals_loader: _FakeFundamentals | None = None,
) -> RefreshSummary:
    return run_refresh(
        data_root=tmp_path,
        from_date=_FROM,
        to_date=_TO,
        prices_loader=prices_loader or _FakePrices(),
        fundamentals_loader=fundamentals_loader or _FakeFundamentals(),
    )


# --- universe ---


def test_price_universe_is_etfs_plus_equities_sorted_unique() -> None:
    universe = price_universe()
    assert set(ETF_UNIVERSE).issubset(set(universe))
    assert set(equity_universe()).issubset(set(universe))
    assert list(universe) == sorted(set(universe))  # sorted + de-duplicated
    assert len(universe) == len(set(universe))


# --- prices CSV ---


def test_prices_csv_written_with_exact_trade_schema(tmp_path: Path) -> None:
    summary = _run(tmp_path)
    path = Path(summary.prices_path)
    assert path.exists()
    with path.open() as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == PRICES_HEADER
    # Schema-compat with the trade loader's required columns.
    from trade.data.loader import UNIFIED_REQUIRED_COLUMNS  # type: ignore[import-untyped]

    assert UNIFIED_REQUIRED_COLUMNS.issubset(set(rows[0]))
    assert summary.price_rows == len(price_universe())  # 1 bar per symbol
    # A sample data row: date ISO + ticker present.
    assert rows[1][0] == "2024-12-31"


def test_price_fetch_failure_is_counted_not_fatal(tmp_path: Path) -> None:
    failing = next(iter(price_universe()))
    summary = _run(tmp_path, prices_loader=_FakePrices(fail={failing}))
    assert summary.errors >= 1
    # The other symbols still wrote rows.
    assert summary.price_rows == len(price_universe()) - 1
    assert Path(summary.prices_path).exists()


# --- fundamentals CSV ---


def test_fundamentals_csv_written_with_exact_trade_schema(tmp_path: Path) -> None:
    summary = _run(tmp_path)
    path = Path(summary.fundamentals_path)
    assert path.exists()
    with path.open() as handle:
        rows = list(csv.reader(handle))
    from trade.data.loader import (
        UNIFIED_FUNDAMENTALS_REQUIRED_COLUMNS,
    )

    # Exact header + order match the trade loader's required columns.
    assert rows[0] == FUNDAMENTALS_HEADER
    assert tuple(rows[0]) == tuple(UNIFIED_FUNDAMENTALS_REQUIRED_COLUMNS)
    # Fundamentals are fetched for equities only (not ETFs).
    assert summary.fundamental_symbols == len(equity_universe())
    assert summary.fundamental_rows == len(equity_universe())


def test_synthetic_ticker_fundamentals_skipped_not_error(tmp_path: Path) -> None:
    # A synthetic ticker raises ValueError in the loader → skipped, not an error.
    one_equity = next(iter(equity_universe()))
    summary = _run(tmp_path, fundamentals_loader=_FakeFundamentals(synthetic={one_equity}))
    assert summary.errors == 0
    assert summary.fundamental_rows == len(equity_universe()) - 1


def test_etfs_have_no_fundamentals_rows(tmp_path: Path) -> None:
    summary = _run(tmp_path)
    with Path(summary.fundamentals_path).open() as handle:
        rows = list(csv.reader(handle))
    tickers = {r[1] for r in rows[1:]}
    assert tickers.isdisjoint(set(ETF_UNIVERSE))  # no ETF fundamentals


# --- CSV layout + CLI wiring ---


def test_csv_layout_matches_trade_loader_relpaths(tmp_path: Path) -> None:
    summary = _run(tmp_path)
    prices_expected = tmp_path / "snapshots" / "prices" / "unified" / "prices_daily.csv"
    assert Path(summary.prices_path) == prices_expected
    assert (
        Path(summary.fundamentals_path)
        == tmp_path / "snapshots" / "fundamentals" / "unified" / "fundamentals.csv"
    )


def test_cli_fetch_main_writes_both_csvs(tmp_path: Path) -> None:
    args = refresh_cli.parse_args(["fetch", "--data-root", str(tmp_path), "--lookback-days", "400"])
    summary = refresh_cli.fetch_main(
        args,
        loader_factory=lambda: (_FakePrices(), _FakeFundamentals()),
        today=date(2024, 12, 31),
    )
    assert summary.price_rows > 0
    assert summary.fundamental_rows > 0
    assert Path(summary.prices_path).exists()
    assert Path(summary.fundamentals_path).exists()


def test_cli_default_data_root_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_DATA_ROOT", "/var/lib/workbench/data")
    args = refresh_cli.parse_args(["fetch"])
    assert str(args.data_root) == "/var/lib/workbench/data"
