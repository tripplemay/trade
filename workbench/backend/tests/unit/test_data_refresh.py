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
from typing import Any

import pytest

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.data_refresh import cli as refresh_cli
from workbench_api.data_refresh.refresh import (
    CN_HK_UNIVERSE,
    ETF_UNIVERSE,
    FUNDAMENTALS_HEADER,
    PRICES_HEADER,
    RefreshSummary,
    currency_for_symbol,
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


def _companyfacts(ticker: str) -> dict[str, Any]:
    """Minimal live-shape SEC companyfacts that synthesises exactly one quarter
    (2024Q3). ``filed`` is 2024-12-31 to match the fake price bar's date so the
    MarketCap close resolves (the ratio math itself is covered exhaustively by
    test_backfill_fundamentals.py; here we verify the refresh WIRING)."""

    def entry(val: float) -> dict[str, Any]:
        return {
            "end": "2024-09-30",
            "val": val,
            "filed": "2024-12-31",
            "fy": 2024,
            "fp": "Q3",
            "form": "10-Q",
            "accn": "0000000000-24-000001",
        }

    def usd(val: float) -> dict[str, Any]:
        return {"units": {"USD": [entry(val)]}}

    def shares(val: float) -> dict[str, Any]:
        return {"units": {"shares": [entry(val)]}}

    return {
        "cik": 111,
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": usd(1_000_000.0),
                "StockholdersEquity": usd(5_000_000.0),
                "Revenues": usd(10_000_000.0),
                "CostOfGoodsAndServicesSold": usd(6_000_000.0),
                "NetCashProvidedByUsedInOperatingActivities": usd(2_000_000.0),
                "PaymentsToAcquirePropertyPlantAndEquipment": usd(500_000.0),
                "LongTermDebt": usd(3_000_000.0),
                "Assets": usd(20_000_000.0),
                "CashAndCashEquivalentsAtCarryingValue": usd(1_000_000.0),
                "OperatingIncomeLoss": usd(2_500_000.0),
                "DepreciationDepletionAndAmortization": usd(400_000.0),
            },
            "dei": {"CommonStockSharesOutstanding": shares(1_000_000.0)},
        },
    }


class _FakePrices:
    def __init__(self, fail: set[str] | None = None) -> None:
        self.fail = fail or set()

    def fetch_daily_bars(self, ticker: str, from_date: date, to_date: date) -> list[PriceBar]:
        if ticker in self.fail:
            raise RuntimeError(f"boom {ticker}")
        return [_bar(ticker)]


class _FakeFundamentals:
    """Fake SEC loader matching the live interface refresh now uses:
    ``ticker_cik_map`` (synthetic → CIK None) + ``fetch_raw_companyfacts``."""

    def __init__(self, synthetic: set[str] | None = None, fail: set[str] | None = None) -> None:
        self.synthetic = synthetic or set()
        self.fail = fail or set()

    @property
    def ticker_cik_map(self) -> dict[str, int | None]:
        out: dict[str, int | None] = {ticker: 111 for ticker in equity_universe()}
        for ticker in self.synthetic:
            out[ticker] = None
        return out

    def fetch_raw_companyfacts(self, ticker: str) -> dict[str, Any]:
        if ticker in self.fail:
            raise RuntimeError(f"boom {ticker}")
        return _companyfacts(ticker)


class _FakeCnHk:
    """Fake CN/HK akshare-backed loader (no network); 1 bar per requested ticker."""

    def __init__(self, fail: set[str] | None = None) -> None:
        self.fail = fail or set()

    def fetch_daily_bars(self, ticker: str, from_date: date, to_date: date) -> list[PriceBar]:
        if ticker in self.fail:
            raise RuntimeError(f"boom {ticker}")
        return [_bar(ticker)]


def _run(
    tmp_path: Path,
    *,
    prices_loader: _FakePrices | None = None,
    fundamentals_loader: _FakeFundamentals | None = None,
    cn_hk_prices_loader: _FakeCnHk | None = None,
) -> RefreshSummary:
    return run_refresh(
        data_root=tmp_path,
        from_date=_FROM,
        to_date=_TO,
        prices_loader=prices_loader or _FakePrices(),
        fundamentals_loader=fundamentals_loader or _FakeFundamentals(),
        cn_hk_prices_loader=cn_hk_prices_loader,
    )


# --- universe ---


def test_price_universe_is_etfs_plus_equities_sorted_unique() -> None:
    universe = price_universe()
    assert set(ETF_UNIVERSE).issubset(set(universe))
    assert set(equity_universe()).issubset(set(universe))
    assert list(universe) == sorted(set(universe))  # sorted + de-duplicated
    assert len(universe) == len(set(universe))


def test_etf_universe_includes_hk_china_phase1_etfs() -> None:
    """BL-B011-S2 F001 — the HK-China satellite Phase 1 ETFs are priced by
    the refresh pipeline so the hk_china loader resolves real data."""

    assert {"MCHI", "FXI", "KWEB", "ASHR"}.issubset(set(ETF_UNIVERSE))


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


# --- B062 F002: A-share + HK rows + US-zero-regression ---


def test_cn_hk_none_is_us_only_backward_compat(tmp_path: Path) -> None:
    summary = _run(tmp_path)  # no cn_hk loader
    assert summary.cn_hk_symbols == 0
    assert summary.cn_hk_rows == 0
    assert summary.price_rows == len(price_universe())


def test_cn_hk_rows_appended_without_touching_us_rows(tmp_path: Path) -> None:
    # US-only baseline.
    base = _run(tmp_path / "us")
    with Path(base.prices_path).open() as handle:
        us_rows = list(csv.reader(handle))
    # US + CN/HK.
    both = _run(tmp_path / "both", cn_hk_prices_loader=_FakeCnHk())
    with Path(both.prices_path).open() as handle:
        both_rows = list(csv.reader(handle))

    # ★US-zero-regression: the header + every US row is byte-identical and in the
    # same position; CN/HK are strictly appended after.
    assert both_rows[: len(us_rows)] == us_rows
    assert both.price_rows == base.price_rows  # US count unchanged
    assert both.cn_hk_symbols == len(CN_HK_UNIVERSE)
    assert both.cn_hk_rows == len(CN_HK_UNIVERSE)
    appended_tickers = {row[1] for row in both_rows[len(us_rows):]}
    assert appended_tickers == set(CN_HK_UNIVERSE)
    # Schema unchanged — still the exact 8-column trade schema (no currency col).
    assert both_rows[0] == PRICES_HEADER


def test_cn_hk_fetch_failure_counted_not_fatal(tmp_path: Path) -> None:
    summary = _run(tmp_path, cn_hk_prices_loader=_FakeCnHk(fail={"0700.HK"}))
    assert summary.errors >= 1
    assert summary.cn_hk_rows == len(CN_HK_UNIVERSE) - 1
    # US rows are unaffected by a CN/HK failure.
    assert summary.price_rows == len(price_universe())


def test_currency_for_symbol_derives_from_ticker() -> None:
    assert currency_for_symbol("AAPL") == "USD"
    assert currency_for_symbol("600519.SH") == "CNY"
    assert currency_for_symbol("0700.HK") == "HKD"


def test_cn_hk_universe_is_ashare_plus_hk() -> None:
    hk = {s for s in CN_HK_UNIVERSE if s.endswith(".HK")}
    cn = {s for s in CN_HK_UNIVERSE if s.endswith((".SH", ".SZ"))}
    assert hk and cn  # both markets represented
    assert hk | cn == set(CN_HK_UNIVERSE)  # nothing else


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
        loader_factory=lambda: (_FakePrices(), _FakeFundamentals(), _FakeCnHk()),
        today=date(2024, 12, 31),
    )
    assert summary.price_rows > 0
    assert summary.fundamental_rows > 0
    assert summary.cn_hk_rows == len(CN_HK_UNIVERSE)  # B062 F002 wiring
    assert Path(summary.prices_path).exists()
    assert Path(summary.fundamentals_path).exists()


def test_cli_default_data_root_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_DATA_ROOT", "/var/lib/workbench/data")
    args = refresh_cli.parse_args(["fetch"])
    assert str(args.data_root) == "/var/lib/workbench/data"
